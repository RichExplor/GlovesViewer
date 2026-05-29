# -*- coding: utf-8 -*-
"""
GlovesViewer 主程序入口 — 主窗口控制器与信号槽绑定

业务逻辑:
  1. 数据源切换（BLE / 模拟正弦 / 模拟手动）
  2. BLE设备扫描、连接、断开
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

from core.ble_thread import BLEThread
from core.simulator import SimulatorThread
from core.frame_parser import FINGER_KEYS
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
        self.ble_thread = BLEThread()
        self.sim_thread = SimulatorThread()
        self.data_source = 'sim_sine'  # 默认使用模拟模式，方便无硬件调试
        self.is_connected = False
        self.is_simulating = False

        # 3. 曲线数据缓冲
        self.max_points = 300
        self.plot_data = {f: [] for f in FINGER_KEYS}

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

    # ==================== 信号槽绑定 ====================
    def _bind_signals(self):
        # 数据源切换
        self.ui.rb_ble.toggled.connect(lambda checked: self._on_source_changed('ble') if checked else None)
        self.ui.rb_sim_sine.toggled.connect(lambda checked: self._on_source_changed('sim_sine') if checked else None)
        self.ui.rb_sim_manual.toggled.connect(lambda checked: self._on_source_changed('sim_manual') if checked else None)

        # BLE控制
        self.ui.btn_scan.clicked.connect(self._scan_devices)
        self.ui.btn_connect.clicked.connect(self._toggle_connection)

        # BLE线程信号
        self.ble_thread.device_found.connect(self._on_device_found)
        self.ble_thread.data_received.connect(self._update_hand_data)
        self.ble_thread.log_received.connect(self._show_log)
        self.ble_thread.connection_changed.connect(self._on_connection_changed)
        self.ble_thread.scan_finished.connect(self._on_scan_finished)

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
            self._disconnect_ble()
        if self.is_simulating:
            self._stop_simulator()

        self.data_source = source
        self._update_source_ui()

        # 非BLE模式自动启动模拟器
        if source != 'ble':
            self._start_simulator()

    def _update_source_ui(self):
        """根据数据源更新UI可见性"""
        is_ble = self.data_source == 'ble'
        is_manual = self.data_source == 'sim_manual'

        self.ui.ble_box.setVisible(is_ble)
        self.ui.slider_group.setVisible(is_manual)

        source_label = {
            'ble': 'BLE',
            'sim_sine': '模拟-正弦',
            'sim_manual': '模拟-手动',
        }
        self.ui.lbl_status_source.setText(f"数据源: {source_label[self.data_source]}")

        # 录制按钮状态
        if not is_ble:
            self.ui.btn_start_record.setEnabled(True)
        elif not self.is_connected:
            self.ui.btn_start_record.setEnabled(False)

    # ==================== BLE操作 ====================
    def _scan_devices(self):
        self.ui.cb_device.clear()
        self.ui.btn_scan.setEnabled(False)
        self.ui.btn_scan.setText("扫描中...")
        if not self.ble_thread.isRunning():
            self.ble_thread.start()
        self.ble_thread.scan_devices()

    def _on_device_found(self, name, address):
        self.ui.cb_device.addItem(f"{name} [{address}]", address)

    def _on_scan_finished(self):
        self.ui.btn_scan.setEnabled(True)
        self.ui.btn_scan.setText("扫描")
        if self.ui.cb_device.count() == 0:
            self.ui.cb_device.addItem("未发现设备")

    def _toggle_connection(self):
        if self.is_connected:
            self._disconnect_ble()
        else:
            self._connect_ble()

    def _connect_ble(self):
        if self.ui.cb_device.count() == 0:
            self._show_log("请先扫描设备")
            return
        address = self.ui.cb_device.currentData()
        if not address:
            self._show_log("请选择有效设备")
            return

        if not self.ble_thread.isRunning():
            self.ble_thread.start()

        self.ui.btn_connect.setText("连接中...")
        self.ui.btn_connect.setEnabled(False)
        self.ble_thread.connect_device(address)

    def _disconnect_ble(self):
        self.ble_thread.disconnect_device()

    def _on_connection_changed(self, connected):
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

        # 更新3D手部模型
        self.ui.gl_view.update_hand(angles)

        # 更新角度仪表盘
        for finger in FINGER_KEYS:
            if finger in angles:
                self.ui.gauges[finger].set_angle(angles[finger])

        # 更新实时曲线
        for finger in FINGER_KEYS:
            if finger in angles:
                self.plot_data[finger].append(angles[finger])
                if len(self.plot_data[finger]) > self.max_points:
                    self.plot_data[finger].pop(0)
                self.ui.curves[finger].setData(self.plot_data[finger])

        # 更新原始数据流
        raw_str = "  ".join([f"{FINGER_LABELS[f]}:{angles.get(f, 0):.1f}°" for f in FINGER_KEYS])
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
            headers = ['Timestamp'] + [f'{f}_angle' for f in FINGER_KEYS]

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
        row = [f"{time.time():.4f}"] + [f"{angles.get(f, 0.0):.1f}" for f in FINGER_KEYS]
        try:
            if self.record_format == 'csv':
                self.record_writer.writerow(row)
            else:
                self.record_file.write(json.dumps(dict(zip(
                    ['Timestamp'] + [f'{f}_angle' for f in FINGER_KEYS], row
                ))) + '\n')
        except Exception:
            pass

    # ==================== 状态栏 ====================
    def _calculate_hz(self):
        hz = self.data_count
        self.data_count = 0
        self.ui.lbl_status_hz.setText(f"数据率 (Hz): {hz}")

        if self.data_source == 'ble' and self.ble_thread.isRunning():
            total = self.ble_thread.packet_count + self.ble_thread.drop_count
            drop_rate = (self.ble_thread.drop_count / total * 100) if total > 0 else 0.0
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
            self._disconnect_ble()
        self.ble_thread.stop()
        event.accept()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = GlovesViewer()
    viewer.show()
    sys.exit(app.exec())
