# -*- coding: utf-8 -*-
"""
GlovesViewer 主程序入口 — 主窗口控制器与信号槽绑定

业务逻辑:
1. 自动加载本地 bones_of_the_hand.glb 手部骨骼模型
2. 数据源切换（串口 / 模拟正弦 / 模拟手动）
3. 串口设备扫描、连接、断开
4. 模拟器启停控制
5. 数据接收 -> 3D模型更新 + 曲线更新 + 仪表盘更新
6. GLB 关节独立旋转控制 (滑块 -> 3D模型)
7. T-Pose 重置 + 骨骼调试信息输出
8. 数据录制（CSV/JSON）
9. 状态栏刷新
"""
import sys
import os
import csv
import json
import time
from datetime import datetime

from PyQt5 import QtWidgets, QtCore, QtGui

from core.serial_thread import GloveSerialThread
from core.simulator import SimulatorThread
from core.frame_parser import FINGER_KEYS, ALL_KEYS
from ui.main_window import Ui_GlovesViewer
from ui.widgets import FINGER_LABELS

# ── 状态栏样式常量（与 main_window.py 的 APP_STYLE 匹配）──
_STATUS_BASE = (
    "padding: 2px 12px; font-family: 'Consolas'; font-size: 11px;"
)
_STATUS_CONNECTED = _STATUS_BASE + "color: #4ade80; font-weight: bold;"
_STATUS_DISCONNECTED = _STATUS_BASE + "color: #ef4444; font-weight: bold;"
_STATUS_SIMULATING = _STATUS_BASE + "color: #fbbf24; font-weight: bold;"

# ── GLB 模型默认路径 ──
_DEFAULT_GLB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'model', 'bones_of_the_hand.glb'
)


class GlovesViewer(QtWidgets.QMainWindow):
    """数据手套上位机主窗口"""

    def __init__(self, glb_path: str = ''):
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

        # 6. GLB 模型加载
        self._glb_path = glb_path or _DEFAULT_GLB_PATH
        self._model_loaded = False

        # 7. 绑定信号槽
        self._bind_signals()

        # 8. 定时器
        self.hz_timer = QtCore.QTimer()
        self.hz_timer.timeout.connect(self._calculate_hz)
        self.hz_timer.start(1000)

        # 额外：合并高频数据更新以避免主线程被频繁 UI 更新阻塞
        self._latest_angles = None
        self._ui_update_timer = QtCore.QTimer()
        self._ui_update_timer.timeout.connect(self._flush_hand_data)
        self._ui_update_timer.start(33)  # ~30 FPS 更新 UI

        # 9. 初始状态 — 设置默认数据源为模拟正弦
        self.ui.rb_sim_sine.setChecked(True)
        self._update_source_ui()

        # 10. 刷新串口列表
        self._refresh_ports()

        # 11. 自动加载 GLB 模型
        self._load_glb_model()

    # ==================== GLB 模型加载 ====================
    def _load_glb_model(self):
        """自动加载本地 bones_of_the_hand.glb"""
        if not os.path.isfile(self._glb_path):
            msg = f"❌ GLB 文件不存在: {self._glb_path}"
            self.ui.lbl_model_status.setText(msg)
            self.ui.lbl_model_status.setStyleSheet(
                "color: #ef4444; font-size: 11px; padding: 2px 6px; "
                "background-color: #151823; border-radius: 4px;"
            )
            self.ui.lbl_status_model.setText("🦴 模型: 加载失败")
            self.ui.lbl_status_model.setStyleSheet(
                "padding: 2px 12px; font-family: 'Consolas'; font-size: 11px; color: #ef4444;"
            )
            return

        self.ui.lbl_model_status.setText("⏳ 正在加载 GLB 模型...")
        self.ui.lbl_model_status.setStyleSheet(
            "color: #fbbf24; font-size: 11px; padding: 2px 6px; "
            "background-color: #151823; border-radius: 4px;"
        )

        # 使用 QTimer 延迟加载，让 UI 先显示出来
        QtCore.QTimer.singleShot(100, self._do_load_glb)

    def _do_load_glb(self):
        """执行 GLB 模型加载"""
        success = self.ui.gl_view.load_model(self._glb_path)

        if success:
            n_bones = len(self.ui.gl_view.loader.bones)
            n_verts = len(self.ui.gl_view.loader.vertices) if self.ui.gl_view.loader.vertices is not None else 0
            msg = f"✅ 模型加载成功 — 骨骼:{n_bones} 顶点:{n_verts}"
            self.ui.lbl_model_status.setText(msg)
            self.ui.lbl_model_status.setStyleSheet(
                "color: #4ade80; font-size: 11px; padding: 2px 6px; "
                "background-color: #151823; border-radius: 4px;"
            )
            self.ui.lbl_status_model.setText(f"🦴 模型: {n_bones}骨骼")
            self.ui.lbl_status_model.setStyleSheet(
                "padding: 2px 12px; font-family: 'Consolas'; font-size: 11px; color: #4ade80;"
            )
            self._model_loaded = True

            # 在控制台输出骨骼调试信息
            self.ui.gl_view.loader.print_debug_info()
        else:
            self.ui.lbl_model_status.setText("❌ 模型加载失败，请检查文件格式")
            self.ui.lbl_model_status.setStyleSheet(
                "color: #ef4444; font-size: 11px; padding: 2px 6px; "
                "background-color: #151823; border-radius: 4px;"
            )
            self.ui.lbl_status_model.setText("🦴 模型: 加载失败")
            self.ui.lbl_status_model.setStyleSheet(
                "padding: 2px 12px; font-family: 'Consolas'; font-size: 11px; color: #ef4444;"
            )

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

        # 手动滑条（原有5指弯曲度滑条）
        self.ui.slider_group.angle_changed.connect(self._on_manual_angle)

        # 关节独立控制滑块信号
        # 关节独立控制面板已移除，相关信号连接已移除

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
            'serial': '🔌 串口',
            'sim_sine': '🌊 模拟-正弦',
            'sim_manual': '🎛️ 模拟-手动',
        }
        self.ui.lbl_status_source.setText(f"📡 数据源: {source_label[self.data_source]}")

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

        self.ui.btn_connect.setText("⏳ 连接中...")
        self.ui.btn_connect.setEnabled(False)

        success = self.serial_thread.connect_serial(port, baudrate)
        if not success:
            self.ui.btn_connect.setText("⚡ 连接")
            self.ui.btn_connect.setEnabled(True)

    def _disconnect_serial(self):
        """断开串口连接"""
        self.serial_thread.disconnect_serial()

    def _on_connection_changed(self, connected):
        """串口连接状态变更回调"""
        self.is_connected = connected
        if connected:
            self.ui.btn_connect.setText("🔌 断开")
            self.ui.btn_connect.setStyleSheet(
                "background-color: #dc2626; color: white; border-radius: 6px; "
                "font-weight: bold; font-size: 13px; padding: 8px;"
            )
            self.ui.btn_connect.setEnabled(True)
            self.ui.lbl_status_indicator.setText("🟢 连接状态: 已连接")
            self.ui.lbl_status_indicator.setStyleSheet(_STATUS_CONNECTED)
            self.ui.btn_start_record.setEnabled(True)
        else:
            self.ui.btn_connect.setText("⚡ 连接")
            self.ui.btn_connect.setStyleSheet(
                "background-color: #16a34a; color: white; border-radius: 6px; "
                "font-weight: bold; font-size: 13px; padding: 8px;"
            )
            self.ui.btn_connect.setEnabled(True)
            self.ui.lbl_status_indicator.setText("🔴 连接状态: 未连接")
            self.ui.lbl_status_indicator.setStyleSheet(_STATUS_DISCONNECTED)
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
        self.ui.lbl_status_indicator.setText("🟡 连接状态: 模拟中")
        self.ui.lbl_status_indicator.setStyleSheet(_STATUS_SIMULATING)
        self.ui.btn_start_record.setEnabled(True)

    def _stop_simulator(self):
        if not self.is_simulating:
            return
        self.sim_thread.stop_sim()
        self.is_simulating = False
        self.ui.lbl_status_indicator.setText("🔴 连接状态: 未连接")
        self.ui.lbl_status_indicator.setStyleSheet(_STATUS_DISCONNECTED)
        self.ui.btn_start_record.setEnabled(False)
        self.ui.btn_stop_record.setEnabled(False)

    def _on_manual_angle(self, finger, angle):
        """手动模式下滑条角度变化"""
        if self.is_simulating and self.sim_thread.mode == 'manual':
            self.sim_thread.set_manual_angle(finger, angle)

    # ==================== 关节独立控制 ====================
    def _on_joint_rotation(self, joint_name: str, rx: float, ry: float, rz: float):
        """关节独立旋转滑块变化"""
        self.ui.gl_view.update_joint_rotation(joint_name, rx, ry, rz)

    def _on_reset_tpose(self):
        """重置到 T-Pose"""
        self.ui.gl_view.reset_tpose()
        self._show_log("✅ 已重置到 T-Pose")

    def _on_debug_info(self):
        """输出骨骼调试信息"""
        if self._model_loaded and self.ui.gl_view.controller is not None:
            self.ui.gl_view.controller.print_debug_info()
            self._show_log("🐛 骨骼调试信息已输出到控制台")
        else:
            self._show_log("⚠️ 模型未加载，无法输出调试信息")

    # ==================== 数据更新 ====================
    def _update_hand_data(self, angles):
        """接收线程将最新数据存入缓冲，由定时器在主线程合并更新UI以减小卡顿"""
        self.data_count += 1
        # 只保留最新一帧数据，避免频繁 UI 更新
        self._latest_angles = angles

    def _flush_hand_data(self):
        """以较低频率（由定时器驱动）刷新 UI"""
        angles = self._latest_angles
        if angles is None:
            return
        self._latest_angles = None

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

        # 录制（以flush 频率写入，避免频繁磁盘 I/O）
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
            self.ui.btn_start_record.setStyleSheet(
                "background-color: #11535e; color: #475569; "
                "border-radius: 6px; font-size: 11px;"
            )
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
        self.ui.btn_start_record.setStyleSheet(
            "background-color: #0e7490; color: white; "
            "border-radius: 6px; font-size: 11px;"
        )
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
        self.ui.lbl_status_hz.setText(f"⏱ 数据率 (Hz): {hz}")

        if self.data_source == 'serial' and self.serial_thread.is_connected:
            total = self.serial_thread.packet_count + self.serial_thread.drop_count
            drop_rate = (self.serial_thread.drop_count / total * 100) if total > 0 else 0.0
            self.ui.lbl_status_drop.setText(f"⚠ 丢包率 (%): {drop_rate:.1f}")
        else:
            self.ui.lbl_status_drop.setText("⚠ 丢包率 (%): 0.0")

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


def _find_glb_path() -> str:
    """查找 GLB 模型文件路径"""
    # 1. 命令行参数
    for i, arg in enumerate(sys.argv):
        if arg == '--glb' and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.endswith('.glb'):
            return arg

    # 2. 默认路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'model', 'bones_of_the_hand.glb')


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    # 设置全局字体
    font = QtGui.QFont("Segoe UI", 10)
    app.setFont(font)

    glb_path = _find_glb_path()
    viewer = GlovesViewer(glb_path=glb_path)
    viewer.show()
    sys.exit(app.exec())
