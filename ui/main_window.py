# -*- coding: utf-8 -*-
"""
主窗口静态UI布局类 — 不包含任何业务逻辑

三栏布局:
左栏(270px): 串口连接控制 + 数据源选择 + 录制控制 + 角度仪表盘 + 原始数据流
中栏(弹性): 3D手部骨骼模型渲染区
右栏(弹性): 6通道(5指+手背)实时时序曲线
"""
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import pyqtgraph.opengl as gl

from ui.hand_3d_widget import Hand3DWidget
from ui.widgets import AngleGaugeWidget, FingerSliderGroup, FINGER_KEYS, FINGER_LABELS, FINGER_COLORS
from core.frame_parser import ALL_KEYS


class Ui_GlovesViewer(object):
    """纯粹的界面布局类，不包含任何串口、计算等业务逻辑"""

    def setupUi(self, MainWindow):
        MainWindow.setWindowTitle("Gloves Hanwei Viewer v1.0")
        MainWindow.resize(1400, 800)

        MainWindow.setStyleSheet("""
        QMainWindow { background-color: #16181c; }
        QGroupBox { color: #ffffff; font-size: 12px; font-weight: bold; border: 1px solid #2d3139; border-radius: 6px; margin-top: 12px; padding-top: 12px; background-color: #1e222b; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 3px; }
        QLabel { color: #abb2bf; font-family: 'Segoe UI', Arial; }
        QPushButton { background-color: #2c313c; color: #ffffff; border: 1px solid #3e4451; border-radius: 4px; padding: 6px; min-height: 18px; font-weight: bold; }
        QPushButton:hover { background-color: #3e4451; border-color: #4b5263; }
        QPushButton:disabled { background-color: #1c1e22; color: #5c6370; border-color: #2d3139; }
        QComboBox { background-color: #181a1f; color: #ffffff; border: 1px solid #3e4451; border-radius: 3px; padding: 3px 5px; }
        QComboBox:disabled { background-color: #111317; color: #5c6370; border-color: #2d3139; }
        QListWidget { background-color: #111317; color: #a6e22e; border: 1px solid #2d3139; font-family: 'Consolas'; font-size: 11px; border-radius: 4px; }
        QStatusBar { background-color: #1e222b; color: #abb2bf; border-top: 1px solid #2d3139; }
        QCheckBox { color: #ffffff; font-weight: bold; font-family: 'Consolas'; font-size: 11px; }
        QCheckBox::indicator { width: 13px; height: 13px; }
        QRadioButton { color: #abb2bf; font-size: 11px; }
        QSlider::groove:horizontal { background: #2d3139; height: 6px; border-radius: 3px; }
        QSlider::handle:horizontal { background: #61afef; width: 14px; margin: -4px 0; border-radius: 7px; }
        """)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, MainWindow)
        MainWindow.setCentralWidget(self.main_splitter)

        # ================= 1. 左侧面板 =================
        self.left_widget = QtWidgets.QWidget()
        self.left_widget.setFixedWidth(270)
        self.left_layout = QtWidgets.QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(10, 5, 5, 10)

        # --- 数据源选择 ---
        self.source_box = QtWidgets.QGroupBox("数据源")
        self.source_vbox = QtWidgets.QVBoxLayout(self.source_box)
        self.rb_serial = QtWidgets.QRadioButton("串口连接")
        self.rb_sim_sine = QtWidgets.QRadioButton("模拟 - 正弦波")
        self.rb_sim_manual = QtWidgets.QRadioButton("模拟 - 手动控制")
        self.source_vbox.addWidget(self.rb_serial)
        self.source_vbox.addWidget(self.rb_sim_sine)
        self.source_vbox.addWidget(self.rb_sim_manual)
        self.left_layout.addWidget(self.source_box)

        # --- 串口连接 ---
        self.port_box = QtWidgets.QGroupBox("串口连接")
        self.port_grid = QtWidgets.QGridLayout(self.port_box)
        self.port_grid.addWidget(QtWidgets.QLabel("端口"), 0, 0)
        self.cb_port = QtWidgets.QComboBox()
        self.port_grid.addWidget(self.cb_port, 0, 1)
        self.btn_refresh_port = QtWidgets.QPushButton("刷新")
        self.btn_refresh_port.setStyleSheet("background-color: #17a2b8; color: white; font-size: 11px;")
        self.port_grid.addWidget(self.btn_refresh_port, 1, 0)
        self.port_grid.addWidget(QtWidgets.QLabel("波特率"), 2, 0)
        self.cb_baud = QtWidgets.QComboBox()
        self.cb_baud.addItems(["9600", "115200", "921600"])
        self.cb_baud.setCurrentText("115200")
        self.port_grid.addWidget(self.cb_baud, 2, 1)
        self.btn_connect = QtWidgets.QPushButton("连接")
        self.btn_connect.setStyleSheet("background-color: #28a745; color: white; font-size: 12px;")
        self.port_grid.addWidget(self.btn_connect, 3, 0, 1, 2)
        self.left_layout.addWidget(self.port_box)

        # --- 录制 ---
        self.record_box = QtWidgets.QGroupBox("数据录制")
        self.record_grid = QtWidgets.QGridLayout(self.record_box)
        self.record_grid.addWidget(QtWidgets.QLabel("格式"), 0, 0)
        self.cb_format = QtWidgets.QComboBox()
        self.cb_format.addItems(["CSV", "JSON"])
        self.record_grid.addWidget(self.cb_format, 0, 1)
        self.btn_start_record = QtWidgets.QPushButton("开始录制")
        self.btn_start_record.setStyleSheet("background-color: #17a2b8; color: white; font-size: 11px;")
        self.btn_start_record.setEnabled(False)
        self.record_grid.addWidget(self.btn_start_record, 1, 0)
        self.btn_stop_record = QtWidgets.QPushButton("停止录制")
        self.btn_stop_record.setStyleSheet("background-color: #dc3545; color: white; font-size: 11px;")
        self.btn_stop_record.setEnabled(False)
        self.record_grid.addWidget(self.btn_stop_record, 1, 1)
        self.left_layout.addWidget(self.record_box)

        # --- 角度仪表盘（6通道：5指+手背）---
        self.gauge_box = QtWidgets.QGroupBox("角度仪表")
        self.gauge_hbox = QtWidgets.QHBoxLayout(self.gauge_box)
        self.gauge_hbox.setSpacing(2)
        self.gauge_hbox.setContentsMargins(6, 12, 6, 8)
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
        self.raw_box = QtWidgets.QGroupBox("原始数据流")
        self.raw_vbox = QtWidgets.QVBoxLayout(self.raw_box)
        self.txt_raw_stream = QtWidgets.QListWidget()
        self.txt_raw_stream.setFixedHeight(100)
        self.raw_vbox.addWidget(self.txt_raw_stream)
        self.left_layout.addWidget(self.raw_box, stretch=1)

        self.main_splitter.addWidget(self.left_widget)

        # ================= 2. 中间面板 =================
        self.center_widget = QtWidgets.QWidget()
        self.center_layout = QtWidgets.QVBoxLayout(self.center_widget)
        self.center_layout.setContentsMargins(5, 5, 5, 10)

        self.scene_box = QtWidgets.QGroupBox("3D 手部骨骼模型")
        self.scene_vbox = QtWidgets.QVBoxLayout(self.scene_box)
        self.scene_vbox.setContentsMargins(4, 12, 4, 4)

        self.gl_view = Hand3DWidget()
        self.scene_vbox.addWidget(self.gl_view, stretch=1)

        self.center_layout.addWidget(self.scene_box)
        self.main_splitter.addWidget(self.center_widget)

        # ================= 3. 右侧面板 =================
        self.right_widget = QtWidgets.QWidget()
        self.right_layout = QtWidgets.QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(5, 5, 10, 10)

        self.wave_box = QtWidgets.QGroupBox("实时弯曲度曲线")
        self.wave_vbox = QtWidgets.QVBoxLayout(self.wave_box)
        self.wave_vbox.setSpacing(6)

        pg.setConfigOption('background', '#1a1d24')
        pg.setConfigOption('foreground', '#ffffff')

        self.plot_fingers = {}
        self.curves = {}
        self.checkboxes = {}

        for key in ALL_KEYS:
            color = FINGER_COLORS[key]
            label = FINGER_LABELS[key]

            h_layout = QtWidgets.QHBoxLayout()

            plot_w = pg.PlotWidget(
                title=f"<span style='color: {color}; font-weight: bold;'>{label} (°)</span>"
            )
            plot_w.showGrid(x=True, y=True, alpha=0.15)
            plot_w.setYRange(0, 180)
            plot_w.getAxis('bottom').setLabel('Time', color='#ffffff')
            plot_w.setMaximumHeight(100)

            curve = plot_w.plot(pen=pg.mkPen(color, width=1.5))
            self.curves[key] = curve
            self.plot_fingers[key] = plot_w

            h_layout.addWidget(plot_w, stretch=6)
            self.wave_vbox.addLayout(h_layout)

        self.right_layout.addWidget(self.wave_box)
        self.main_splitter.addWidget(self.right_widget)

        # 分割器比例: 左栏固定宽度, 中栏3D:右栏曲线 = 3:1
        self.right_widget.setMaximumWidth(320)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setStretchFactor(2, 1)

        # ================= 状态栏 =================
        self.status_bar = QtWidgets.QStatusBar(MainWindow)
        MainWindow.setStatusBar(self.status_bar)
        self.lbl_status_hz = QtWidgets.QLabel("数据率 (Hz): 0")
        self.lbl_status_drop = QtWidgets.QLabel("丢包率 (%): 0.0")
        self.lbl_status_indicator = QtWidgets.QLabel("连接状态: 未连接")
        self.lbl_status_source = QtWidgets.QLabel("数据源: 串口")
        self.status_bar.addPermanentWidget(self.lbl_status_hz, 1)
        self.status_bar.addPermanentWidget(self.lbl_status_drop, 1)
        self.status_bar.addPermanentWidget(self.lbl_status_source, 1)
        self.status_bar.addPermanentWidget(self.lbl_status_indicator, 1)
