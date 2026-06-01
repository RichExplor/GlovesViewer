# -*- coding: utf-8 -*-
"""
GlovesViewer 主程序入口 — 主窗口控制器与信号槽绑定

业务逻辑:
1. 数据源切换（串口 / 模拟正弦 / 模拟手动）
2. 串口设备扫描、连接、断开
3. 模拟器启停控制
4. 数据接收 -> 3D模型更新 + 曲线更新 + 仪表盘更新
5. 数据录制（CSV/JSON）
6. 状态栏刷新
"""
import sys
import csv
import json
import time
from datetime import datetime

from PyQt5 import QtWidgets, QtCore

from core.serial_thread import GloveSerialThread
from core.simulator import SimulatorThread
from core.frame_parser import FINGER_KEYS, ALL_KEYS
from ui.main_window import Ui_GlovesViewer
from ui.widgets import FINGER_LABELS


class GlovesViewer(QtWidgets.QMainWindow):
    """数据手套上位机主窗口"""

    def __init__(self):
        super().__init__()
        # 1. 挂载静态UI
        self.ui = Ui_GlovesViewer()
        self.ui.setupUi(self)

        # 2. 初始化数据源
        self.serial_thread = GloveSerialThread()
        self.sim_thread = SimulatorThread()
        self.data_source = 'sim_sine'  # 默认使用模拟模式，方便无硬件调试
        self.is_connected = False
        self.is_simulating = False

        # 3. 曲线数据缓冲（6通道：5指+手背）
        self.max_points = 300
        self.plot_data = {k: [] for k in ALL_KEYS}

        # 4. 录制状态
        self.is_recording = False
        self.record_file = None
        self.record_writer = None
        self.record_format = "csv"

        # 5. 统计
        self.data_count = 0

        # 6. 绑定信号槽
        self._bind_signals()

        # 7. 定时器
        self.hz_timer = QtCore.QTimer()
        self.hz_timer.timeout.connect(self._calculate_hz)
        self.hz_timer.start(1000)

        # 8. 初始状态 — 设置默认数据源为模拟正弦
        self.ui.rb_sim_sine.setChecked(True)
        self._update_source_ui()

        # 9. 刷新串口列表
        self._refresh_ports()

    # ==================== 信号槽绑定 ====================
    def _bind_signals(self):
        # 数据源切换
        self.ui.rb_serial.toggled.connect(lambda checked: self._on_source_changed('serial') if checked else None)
        self.ui.rb_sim_sine.toggled.connect(lambda checked: self._on_source_changed('sim_sine') if checked else None)
        self.ui.rb_sim_manual.toggled.connect(lambda checked: self._on_source_changed('sim_manual') if checked else None)

        # 串口控制
        self.ui.btn_refresh_port.clicked.connect(self._refresh_ports)
        self.ui.btn_connect.clicked.connect(self._toggle_connection)

        # 串口线程信号
        self.serial_thread.data_received.connect(self._update_hand_data)
        self.serial_thread.log_received.connect(self._show_log)
        self.serial_thread.connection_changed.connect(self._on_connection_changed)

        # 模拟器信号
        self.sim_thread.data_received.connect(self._update_hand_data)

        # 手动滑条
        self.ui.slider_group.angle_changed.connect(self._on_manual_angle)

        # 录制
        self.ui.btn_start_record.clicked.connect(self._start_recording)
        self.ui.btn_stop_record.clicked.connect(self._stop_recording)

    # ==================== 数据源管理 ====================
    def _on_source_changed(self, source):
        # 停止当前数据源
        if self.is_connected:
            self._disconnect_serial()
        if self.is_simulating:
            self._stop_simulator()

        self.data_source = source
        self._update_source_ui()

        # 非串口模式自动启动模拟器
        if source != 'serial':
            self._start_simulator()

    def _update_source_ui(self):
        """根据数据源更新UI可见性"""
        is_serial = self.data_source == 'serial'
        is_manual = self.data_source == 'sim_manual'

        self.ui.port_box.setVisible(is_serial)
        self.ui.slider_group.setVisible(is_manual)

        source_label = {
            'serial': '串口',
            'sim_sine': '模拟-正弦',
            'sim_manual': '模拟-手动',
        }
        self.ui.lbl_status_source.setText(f"数据源: {source_label[self.data_source]}")

        # 录制按钮状态
        if not is_serial:
            self.ui.btn_start_record.setEnabled(True)
        elif not self.is_connected:
            self.ui.btn_start_record.setEnabled(False)

    # ==================== 串口操作 ====================
    def _refresh_ports(self):
        """刷新可用串口列表"""
        self.ui.cb_port.clear()
        ports = GloveSerialThread.list_available_ports()
        for device, desc in ports:
            self.ui.cb_port.addItem(f"{device} - {desc}", device)
        if self.ui.cb_port.count() == 0:
            self.ui.cb_port.addItem("/dev/ttyUSB0", "/dev/ttyUSB0")

    def _toggle_connection(self):
        """切换串口连接/断开"""
        if self.is_connected:
            self._disconnect_serial()
        else:
            self._connect_serial()

    def _connect_serial(self):
        """连接串口"""
        port = self.ui.cb_port.currentData()
        if not port:
            port = self.ui.cb_port.currentText()
        if not port:
            self._show_log("请先选择串口")
            return

        baudrate = int(self.ui.cb_baud.currentText())

        self.ui.btn_connect.setText("连接中...")
        self.ui.btn_connect.setEnabled(False)

        success = self.serial_thread.connect_serial(port, baudrate)
        if not success:
            self.ui.btn_connect.setText("连接")
            self.ui.btn_connect.setEnabled(True)

    def _disconnect_serial(self):
        """断开串口连接"""
        self.serial_thread.disconnect_serial()

    def _on_connection_changed(self, connected):
        """串口连接状态变更回调"""
        self.is_connected = connected
        if connected:
            self.ui.btn_connect.setText("断开")
            self.ui.btn_connect.setStyleSheet("background-color: #dc3545; color: white;")
            self.ui.btn_connect.setEnabled(True)
            self.ui.lbl_status_indicator.setText("连接状态: 已连接")
            self.ui.lbl_status_indicator.setStyleSheet("color: #55ff55;")
            self.ui.btn_start_record.setEnabled(True)
        else:
            self.ui.btn_connect.setText("连接")
            self.ui.btn_connect.setStyleSheet("background-color: #28a745; color: white;")
            self.ui.btn_connect.setEnabled(True)
            self.ui.lbl_status_indicator.setText("连接状态: 未连接")
            self.ui.lbl_status_indicator.setStyleSheet("color: #ff5555;")
            self.ui.btn_start_record.setEnabled(False)
            self.ui.btn_stop_record.setEnabled(False)

    # ==================== 模拟器操作 ====================
    def _start_simulator(self):
        if self.is_simulating:
            return

        if self.data_source == 'sim_sine':
            self.sim_thread.mode = 'sine'
        else:
            self.sim_thread.mode = 'manual'

        self.is_simulating = True
        self.sim_thread.start_sim()
        self.ui.lbl_status_indicator.setText("连接状态: 模拟中")
        self.ui.lbl_status_indicator.setStyleSheet("color: #e5c07b;")
        self.ui.btn_start_record.setEnabled(True)

    def _stop_simulator(self):
        if not self.is_simulating:
            return
        self.sim_thread.stop_sim()
        self.is_simulating = False
        self.ui.lbl_status_indicator.setText("连接状态: 未连接")
        self.ui.lbl_status_indicator.setStyleSheet("color: #ff5555;")
        self.ui.btn_start_record.setEnabled(False)
        self.ui.btn_stop_record.setEnabled(False)

    def _on_manual_angle(self, finger, angle):
        """手动模式下滑条角度变化"""
        if self.is_simulating and self.sim_thread.mode == 'manual':
            self.sim_thread.set_manual_angle(finger, angle)

    # ==================== 数据更新 ====================
    def _update_hand_data(self, angles):
        """核心数据更新方法 — 同时更新3D模型、曲线、仪表盘"""
        self.data_count += 1

        # 更新3D手部模型（仅5指，不含手背）
        self.ui.gl_view.update_hand(angles)

        # 更新角度仪表盘（6通道：5指+手背）
        for key in ALL_KEYS:
            if key in angles:
                self.ui.gauges[key].set_angle(angles[key])

        # 更新实时曲线（6通道）
        for key in ALL_KEYS:
            if key in angles:
                self.plot_data[key].append(angles[key])
                if len(self.plot_data[key]) > self.max_points:
                    self.plot_data[key].pop(0)
                self.ui.curves[key].setData(self.plot_data[key])

        # 更新原始数据流
        raw_str = " ".join([f"{FINGER_LABELS[k]}:{angles.get(k, 0):.0f}°" for k in ALL_KEYS])
        if self.ui.txt_raw_stream.count() > 15:
            self.ui.txt_raw_stream.takeItem(0)
        self.ui.txt_raw_stream.addItem(raw_str)
        self.ui.txt_raw_stream.scrollToBottom()

        # 录制
        if self.is_recording and self.record_file:
            self._write_record_row(angles)

    # ==================== 录制 ====================
    def _start_recording(self):
        if self.is_recording:
            return

        self.record_format = self.ui.cb_format.currentText().lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gloves_record_{timestamp}.{self.record_format}"

        try:
            self.record_file = open(filename, 'w', newline='', encoding='utf-8')
            headers = ['Timestamp'] + [f'{k}_angle' for k in ALL_KEYS]

            if self.record_format == 'csv':
                self.record_writer = csv.writer(self.record_file)
                self.record_writer.writerow(headers)
            else:
                self.record_file.write(json.dumps({'headers': headers}) + '\n')

            self.is_recording = True
            self.ui.btn_start_record.setEnabled(False)
            self.ui.btn_start_record.setStyleSheet("background-color: #11535e; color: #5c6370;")
            self.ui.btn_stop_record.setEnabled(True)
            self.ui.cb_format.setEnabled(False)
            self._show_log(f"录制已启动 -> {filename}")

        except Exception as e:
            self._show_log(f"创建文件失败: {str(e)}")

    def _stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        if self.record_file:
            self.record_file.close()
            self.record_file = None
            self.record_writer = None

        self.ui.btn_start_record.setEnabled(True)
        self.ui.btn_start_record.setStyleSheet("background-color: #17a2b8; color: white;")
        self.ui.btn_stop_record.setEnabled(False)
        self.ui.cb_format.setEnabled(True)
        self._show_log("数据已成功保存至本地。")

    def _write_record_row(self, angles):
        row = [f"{time.time():.4f}"] + [f"{angles.get(k, 0.0):.1f}" for k in ALL_KEYS]
        try:
            if self.record_format == 'csv':
                self.record_writer.writerow(row)
            else:
                self.record_file.write(json.dumps(dict(zip(
                    ['Timestamp'] + [f'{k}_angle' for k in ALL_KEYS], row
                ))) + '\n')
        except Exception:
            pass

    # ==================== 状态栏 ====================
    def _calculate_hz(self):
        hz = self.data_count
        self.data_count = 0
        self.ui.lbl_status_hz.setText(f"数据率 (Hz): {hz}")

        if self.data_source == 'serial' and self.serial_thread.is_connected:
            total = self.serial_thread.packet_count + self.serial_thread.drop_count
            drop_rate = (self.serial_thread.drop_count / total * 100) if total > 0 else 0.0
            self.ui.lbl_status_drop.setText(f"丢包率 (%): {drop_rate:.1f}")
        else:
            self.ui.lbl_status_drop.setText("丢包率 (%): 0.0")

    # ==================== 工具方法 ====================
    def _show_log(self, message):
        self.ui.status_bar.showMessage(message, 5000)

    # ==================== 窗口事件 ====================
    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        if self.is_recording:
            self._stop_recording()
        if self.is_simulating:
            self._stop_simulator()
        if self.is_connected:
            self._disconnect_serial()
        event.accept()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = GlovesViewer()
    viewer.show()
    sys.exit(app.exec())
