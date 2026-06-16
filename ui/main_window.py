# -*- coding: utf-8 -*-
"""
主窗口静态UI布局类 — 不包含任何业务逻辑

三栏布局:
左栏(280px): 串口连接控制 + 数据源选择 + 录制控制 + 角度仪表盘 + 原始数据流
中栏(弹性): 3D手部骨骼模型渲染区
右栏(弹性): 6通道(5指+手背)实时时序曲线
"""
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import pyqtgraph.opengl as gl

from ui.hand_3d_widget import Hand3DWidget
from ui.widgets import AngleGaugeWidget, FingerSliderGroup, FINGER_KEYS, FINGER_LABELS, FINGER_COLORS
from core.frame_parser import ALL_KEYS


# ============ 应用级样式表 ============
APP_STYLE = """
/* ── 全局 ── */
QMainWindow {
    background-color: #0a0c12;
}

/* ── 分割器手柄 ── */
QSplitter::handle {
    background: #1e2230;
}
QSplitter::handle:hover {
    background: #3b82f6;
}

/* ── GroupBox ── */
QGroupBox {
    color: #f8fafc;
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #1e2230;
    border-radius: 8px;
    margin-top: 16px;
    padding: 14px 8px 8px 8px;
    background-color: #151823;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 2px 8px;
    background-color: #151823;
    border: 1px solid #1e2230;
    border-radius: 4px;
}

/* ── Label ── */
QLabel {
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Microsoft YaHei', Arial;
    font-size: 12px;
}
QLabel#section_header {
    color: #f8fafc;
    font-size: 12px;
    font-weight: bold;
    padding: 4px 0px;
}

/* ── PushButton ── */
QPushButton {
    background-color: #1e2230;
    color: #e2e8f0;
    border: 1px solid #3b82f6;
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 20px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3b82f6;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #2563eb;
}
QPushButton:disabled {
    background-color: #0d0f17;
    color: #3e4451;
    border-color: #161a26;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #0d0f17;
    color: #e2e8f0;
    border: 1px solid #1e2230;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 22px;
    font-size: 11px;
}
QComboBox:hover {
    border-color: #3b82f6;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #64748b;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #151823;
    color: #e2e8f0;
    border: 1px solid #1e2230;
    border-radius: 4px;
    selection-background-color: #1e3a5f;
    selection-color: #ffffff;
    outline: none;
}
QComboBox:disabled {
    background-color: #0a0c12;
    color: #3e4451;
    border-color: #12141c;
}

/* ── ListWidget ── */
QListWidget {
    background-color: #0a0c12;
    color: #a3e635;
    border: 1px solid #1e2230;
    border-radius: 6px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 10px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 2px 4px;
    border-radius: 2px;
}
QListWidget::item:selected {
    background-color: #1e3a5f;
}

/* ── StatusBar ── */
QStatusBar {
    background-color: #0d0f17;
    color: #64748b;
    border-top: 1px solid #1e2230;
    font-size: 11px;
    padding: 2px 8px;
}

/* ── CheckBox ── */
QCheckBox {
    color: #e2e8f0;
    font-weight: bold;
    font-family: 'Segoe UI', Arial;
    font-size: 11px;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #2d3348;
    background-color: #0d0f17;
}
QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

/* ── RadioButton ── */
QRadioButton {
    color: #e2e8f0;
    font-size: 11px;
    spacing: 6px;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid #2d3348;
    background-color: #0d0f17;
}
QRadioButton::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

/* ── Slider ── */
QSlider::groove:horizontal {
    background: #1e2230;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #3b82f6;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #60a5fa;
}
QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 2px;
}

/* ── ScrollBar ── */
QScrollBar:vertical {
    background: #0a0c12;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2d3348;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #3b82f6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
"""


class Ui_GlovesViewer(object):
    """纯粹的界面布局类，不包含任何串口、计算等业务逻辑"""

    def setupUi(self, MainWindow):
        MainWindow.setWindowTitle("Gloves Hanwei Viewer v1.0")
        MainWindow.resize(1440, 860)

        # 设置窗口图标（如果存在）
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logo.png')
        if os.path.exists(icon_path):
            MainWindow.setWindowIcon(QtGui.QIcon(icon_path))

        MainWindow.setStyleSheet(APP_STYLE)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, MainWindow)
        self.main_splitter.setHandleWidth(2)
        self.main_splitter.setObjectName("mainSplitter")
        MainWindow.setCentralWidget(self.main_splitter)

        # ================= 1. 左侧面板 =================
        self.left_widget = QtWidgets.QWidget()
        self.left_layout = QtWidgets.QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 12, 0, 12)
        self.left_layout.setSpacing(10)

        # --- 数据源选择 ---
        self.source_box = QtWidgets.QGroupBox("📡 数据源")
        self.source_vbox = QtWidgets.QVBoxLayout(self.source_box)
        self.source_vbox.setSpacing(6)
        self.rb_serial = QtWidgets.QRadioButton("🔌 串口连接")
        self.rb_sim_sine = QtWidgets.QRadioButton("🌊 模拟 - 正弦波")
        self.rb_sim_manual = QtWidgets.QRadioButton("🎛️ 模拟 - 手动控制")
        self.source_vbox.addWidget(self.rb_serial)
        self.source_vbox.addWidget(self.rb_sim_sine)
        self.source_vbox.addWidget(self.rb_sim_manual)
        self.left_layout.addWidget(self.source_box)

        # --- 串口连接 ---
        self.port_box = QtWidgets.QGroupBox("🔗 串口连接")
        self.port_grid = QtWidgets.QGridLayout(self.port_box)
        self.port_grid.setSpacing(8)
        self.port_grid.setContentsMargins(10, 18, 10, 10)

        lbl_port = QtWidgets.QLabel("端口")
        lbl_port.setStyleSheet("font-weight: bold;")
        self.port_grid.addWidget(lbl_port, 0, 0)
        self.cb_port = QtWidgets.QComboBox()
        self.port_grid.addWidget(self.cb_port, 0, 1)

        self.btn_refresh_port = QtWidgets.QPushButton("🔄 刷新")
        self.btn_refresh_port.setStyleSheet(
            "background-color: #3b82f6; color: white; font-size: 11px; border-radius: 6px;"
        )
        self.port_grid.addWidget(self.btn_refresh_port, 1, 0)

        lbl_baud = QtWidgets.QLabel("波特率")
        lbl_baud.setStyleSheet("font-weight: bold;")
        self.port_grid.addWidget(lbl_baud, 2, 0)
        self.cb_baud = QtWidgets.QComboBox()
        self.cb_baud.addItems(["9600", "115200", "921600"])
        self.cb_baud.setCurrentText("115200")
        self.port_grid.addWidget(self.cb_baud, 2, 1)

        self.btn_connect = QtWidgets.QPushButton("⚡ 连接")
        self.btn_connect.setStyleSheet(
            "background-color: #16a34a; color: white; font-size: 13px; "
            "font-weight: bold; border-radius: 6px; padding: 8px;"
        )
        self.port_grid.addWidget(self.btn_connect, 3, 0, 1, 2)
        self.left_layout.addWidget(self.port_box)

        # --- 录制 ---
        self.record_box = QtWidgets.QGroupBox("💾 数据录制")
        self.record_grid = QtWidgets.QGridLayout(self.record_box)
        self.record_grid.setSpacing(6)
        self.record_grid.setContentsMargins(10, 18, 10, 10)

        lbl_format = QtWidgets.QLabel("格式")
        lbl_format.setStyleSheet("font-weight: bold;")
        self.record_grid.addWidget(lbl_format, 0, 0)
        self.cb_format = QtWidgets.QComboBox()
        self.cb_format.addItems(["CSV", "JSON"])
        self.record_grid.addWidget(self.cb_format, 0, 1)

        self.btn_start_record = QtWidgets.QPushButton("⏺ 开始录制")
        self.btn_start_record.setStyleSheet(
            "background-color: #3b82f6; color: white; font-size: 11px; border-radius: 6px;"
        )
        self.btn_start_record.setEnabled(False)
        self.record_grid.addWidget(self.btn_start_record, 1, 0)

        self.btn_stop_record = QtWidgets.QPushButton("⏹ 停止录制")
        self.btn_stop_record.setStyleSheet(
            "background-color: #dc2626; color: white; font-size: 11px; border-radius: 6px;"
        )
        self.btn_stop_record.setEnabled(False)
        self.record_grid.addWidget(self.btn_stop_record, 1, 1)
        self.left_layout.addWidget(self.record_box)

        # --- 角度仪表盘（6通道：5指+手背）---
        self.gauge_box = QtWidgets.QGroupBox("📊 角度仪表")
        self.gauge_hbox = QtWidgets.QHBoxLayout(self.gauge_box)
        self.gauge_hbox.setSpacing(2)
        self.gauge_hbox.setContentsMargins(6, 16, 6, 8)
        self.gauges = {}
        for key in ALL_KEYS:
            gauge = AngleGaugeWidget(key)
            self.gauges[key] = gauge
            self.gauge_hbox.addWidget(gauge)
        self.left_layout.addWidget(self.gauge_box)

        # --- 手动控制滑条（默认隐藏）---
        self.slider_group = FingerSliderGroup()
        self.slider_group.setVisible(False)
        self.left_layout.addWidget(self.slider_group)

        # --- 原始数据流 ---
        self.lbl_raw_stream = QtWidgets.QLabel("📋 原始数据流")
        self.lbl_raw_stream.setObjectName("section_header")
        self.left_layout.addWidget(self.lbl_raw_stream)
        self.txt_raw_stream = QtWidgets.QListWidget()
        self.txt_raw_stream.setObjectName("txt_raw_stream")
        self.txt_raw_stream.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.left_layout.addWidget(self.txt_raw_stream, stretch=10)

        self.main_splitter.addWidget(self.left_widget)

        # ================= 2. 中间面板 =================
        self.center_widget = QtWidgets.QWidget()
        self.center_layout = QtWidgets.QVBoxLayout(self.center_widget)
        self.center_layout.setContentsMargins(4, 10, 4, 10)

        self.scene_box = QtWidgets.QGroupBox("🤚 3D 手部骨骼模型")
        self.scene_vbox = QtWidgets.QVBoxLayout(self.scene_box)
        self.scene_vbox.setContentsMargins(4, 16, 4, 4)
        self.scene_vbox.setSpacing(4)

        self.gl_view = Hand3DWidget()
        self.scene_vbox.addWidget(self.gl_view, stretch=1)

        self.center_layout.addWidget(self.scene_box)
        self.main_splitter.addWidget(self.center_widget)

        # ================= 3. 右侧面板 =================
        self.right_widget = QtWidgets.QWidget()
        self.right_layout = QtWidgets.QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(6, 10, 10, 10)
        self.right_layout.setSpacing(4)

        self.wave_box = QtWidgets.QGroupBox("📈 实时弯曲度曲线")
        self.wave_vbox = QtWidgets.QVBoxLayout(self.wave_box)
        self.wave_vbox.setSpacing(8)
        self.wave_vbox.setContentsMargins(8, 20, 8, 8)

        pg.setConfigOption('background', '#0a0c12')
        pg.setConfigOption('foreground', '#e2e8f0')
        pg.setConfigOption('antialias', True)

        self.plot_fingers = {}
        self.curves = {}
        self.checkboxes = {}

        for key in ALL_KEYS:
            color = FINGER_COLORS[key]
            label = FINGER_LABELS[key]

            h_layout = QtWidgets.QHBoxLayout()
            h_layout.setSpacing(6)

            plot_w = pg.PlotWidget()
            plot_w.setTitle(
                f"<span style='color: {color}; font-weight: bold; font-size: 12px;'>{label} (°)</span>"
            )
            plot_w.showGrid(x=True, y=True, alpha=0.12)
            plot_w.setYRange(0, 180)
            plot_w.getAxis('bottom').setPen(pg.mkPen('#1e2230'))
            plot_w.getAxis('left').setPen(pg.mkPen('#1e2230'))
            plot_w.getAxis('bottom').setTextPen(pg.mkPen('#475569'))
            plot_w.getAxis('left').setTextPen(pg.mkPen('#475569'))
            plot_w.setMaximumHeight(130)
            plot_w.setMinimumHeight(80)

            curve = plot_w.plot(pen=pg.mkPen(color, width=2.5))
            self.curves[key] = curve
            self.plot_fingers[key] = plot_w

            h_layout.addWidget(plot_w, stretch=6)
            self.wave_vbox.addLayout(h_layout)

        self.right_layout.addWidget(self.wave_box)
        self.main_splitter.addWidget(self.right_widget)

        # 分割器比例: 左栏固定宽度, 中栏3D:右栏曲线 = 3:1
        self.right_widget.setMaximumWidth(340)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setStretchFactor(2, 1)

        # ================= 状态栏 =================
        self.status_bar = QtWidgets.QStatusBar(MainWindow)
        MainWindow.setStatusBar(self.status_bar)

        status_style_template = (
            "padding: 2px 12px; font-family: 'Consolas'; font-size: 11px; color: #64748b;"
        )

        self.lbl_status_hz = QtWidgets.QLabel("⏱ 数据率 (Hz): 0")
        self.lbl_status_hz.setStyleSheet(status_style_template + "color: #e2e8f0;")
        self.lbl_status_drop = QtWidgets.QLabel("⚠ 丢包率 (%): 0.0")
        self.lbl_status_drop.setStyleSheet(status_style_template + "color: #e2e8f0;")
        self.lbl_status_indicator = QtWidgets.QLabel("🔴 连接状态: 未连接")
        self.lbl_status_indicator.setStyleSheet(
            status_style_template + "color: #f87171; font-weight: bold;"
        )
        self.lbl_status_source = QtWidgets.QLabel("📡 数据源: 串口")
        self.lbl_status_source.setStyleSheet(status_style_template + "color: #e2e8f0;")

        # 添加分隔线效果
        sep1 = QtWidgets.QFrame()
        sep1.setFrameShape(QtWidgets.QFrame.VLine)
        sep1.setStyleSheet("color: #1e2230;")
        sep2 = QtWidgets.QFrame()
        sep2.setFrameShape(QtWidgets.QFrame.VLine)
        sep2.setStyleSheet("color: #1e2230;")
        sep3 = QtWidgets.QFrame()
        sep3.setFrameShape(QtWidgets.QFrame.VLine)
        sep3.setStyleSheet("color: #1e2230;")

        self.status_bar.addPermanentWidget(self.lbl_status_hz, 1)
        self.status_bar.addPermanentWidget(sep1)
        self.status_bar.addPermanentWidget(self.lbl_status_drop, 1)
        self.status_bar.addPermanentWidget(sep2)
        self.status_bar.addPermanentWidget(self.lbl_status_source, 1)
        self.status_bar.addPermanentWidget(sep3)
        self.status_bar.addPermanentWidget(self.lbl_status_indicator, 1)
