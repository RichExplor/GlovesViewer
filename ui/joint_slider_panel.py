# -*- coding: utf-8 -*-
"""
手部关节独立滑块控制面板 — 每个手指关节可单独调节旋转角度

布局:
- 按手指分组（拇指、食指、中指、无名指、小指）
- 每个关节3个滑块: X轴(弯曲/伸展) / Y轴(外展/内收) / Z轴(扭转)
- 每组有折叠/展开按钮
- 底部: T-Pose 重置按钮 + 骨骼调试信息输出按钮
"""
from PyQt5 import QtWidgets, QtCore, QtGui

from core.glb_loader import (
    FINGER_JOINTS, FINGER_GROUPS, JOINT_CN_LABELS, CONTROLLABLE_JOINTS,
)
from ui.widgets import FINGER_COLORS


# 手指颜色 (与widgets.py保持一致)
_FINGER_RGBA_CSS = {
    'thumb':  FINGER_COLORS['thumb'],   # '#f87171'
    'index':  FINGER_COLORS['index'],   # '#4ade80'
    'middle': FINGER_COLORS['middle'],  # '#fbbf24'
    'ring':   FINGER_COLORS['ring'],    # '#60a5fa'
    'pinky':  FINGER_COLORS['pinky'],   # '#c084fc'
}

# 旋转轴中英文标签
_AXIS_LABELS = {
    'rx': '弯曲',    # 绕X轴
    'ry': '外展',    # 绕Y轴
    'rz': '扭转',    # 绕Z轴
}

# 旋转轴范围 (度)
_AXIS_RANGES = {
    'rx': (-90, 90),    # 弯曲 -90° ~ +90°
    'ry': (-45, 45),    # 外展 -45° ~ +45°
    'rz': (-45, 45),    # 扭转 -45° ~ +45°
}

_AXIS_COLORS = {
    'rx': '#ef4444',   # 红
    'ry': '#22c55e',   # 绿
    'rz': '#3b82f6',   # 蓝
}


class JointSliderPanel(QtWidgets.QWidget):
    """
    手部关节独立滑块控制面板

    信号:
        joint_rotation_changed(str, float, float, float)
            — (semantic_name, rx, ry, rz) 度
        reset_tpose_requested()
            — 请求重置到T-Pose
        debug_info_requested()
            — 请求输出骨骼调试信息
    """
    joint_rotation_changed = QtCore.pyqtSignal(str, float, float, float)
    reset_tpose_requested = QtCore.pyqtSignal()
    debug_info_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sliders: dict[str, dict[str, dict[str, QtWidgets.QSlider]]] = {}
        self._value_labels: dict[str, dict[str, dict[str, QtWidgets.QLabel]]] = {}
        self._joint_rows: dict[str, QtWidgets.QWidget] = {}
        self._init_ui()

    def _init_ui(self):
        """构建UI布局"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 标题
        title = QtWidgets.QLabel("🖐️ 关节独立控制")
        title.setStyleSheet(
            "color: #f8fafc; font-size: 14px; font-weight: bold; "
            "padding: 4px 0px;"
        )
        main_layout.addWidget(title)

        # 按手指分组的滚动区域
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: #0a0c12; }"
            "QScrollBar::handle:vertical { background: #2d3348; border-radius: 3px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )

        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(2, 2, 2, 2)
        scroll_layout.setSpacing(2)

        # 为每根手指创建分组
        finger_names = ['thumb', 'index', 'middle', 'ring', 'pinky']
        finger_cn = {
            'thumb': '拇指', 'index': '食指',
            'middle': '中指', 'ring': '无名指', 'pinky': '小指',
        }

        for finger in finger_names:
            joints = FINGER_JOINTS.get(finger, [])
            if not joints:
                continue
            color = _FINGER_RGBA_CSS.get(finger, '#ffffff')
            group = self._create_finger_group(finger, joints, color, finger_cn[finger])
            scroll_layout.addWidget(group)

        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        # 底部按钮栏
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_reset = QtWidgets.QPushButton("🔄 T-Pose 重置")
        self.btn_reset.setStyleSheet(
            "QPushButton { background-color: #1e2230; color: #e2e8f0; "
            "border: 1px solid #3b82f6; border-radius: 6px; "
            "padding: 6px 12px; font-weight: bold; font-size: 11px; }"
            "QPushButton:hover { background-color: #3b82f6; color: white; }"
        )
        self.btn_reset.clicked.connect(self._on_reset)

        self.btn_debug = QtWidgets.QPushButton("🐛 调试信息")
        self.btn_debug.setStyleSheet(
            "QPushButton { background-color: #1e2230; color: #e2e8f0; "
            "border: 1px solid #fbbf24; border-radius: 6px; "
            "padding: 6px 12px; font-weight: bold; font-size: 11px; }"
            "QPushButton:hover { background-color: #fbbf24; color: #1e2230; }"
        )
        self.btn_debug.clicked.connect(self.debug_info_requested.emit)

        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_debug)
        main_layout.addLayout(btn_layout)

    def _create_finger_group(self, finger: str, joints: list,
                             color: str, finger_cn: str) -> QtWidgets.QGroupBox:
        """
        创建单根手指的关节控制分组

        Args:
            finger: 手指键名 ('thumb', 'index', ...)
            joints: 该手指的关节语义名列表
            color: 手指颜色 (CSS hex)
            finger_cn: 手指中文名
        """
        group = QtWidgets.QGroupBox()
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {color}; font-size: 12px; font-weight: bold;
                border: 1px solid #1e2230; border-radius: 6px;
                margin-top: 14px; padding: 8px 4px 4px 4px;
                background-color: #151823;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                left: 8px; padding: 1px 6px;
                background-color: #151823; border: 1px solid #1e2230;
                border-radius: 3px;
            }}
        """)
        group.setTitle(f"  {finger_cn}")

        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(3)
        layout.setContentsMargins(6, 16, 6, 4)

        self._sliders[finger] = {}
        self._value_labels[finger] = {}

        for jname in joints:
            cn = JOINT_CN_LABELS.get(jname, jname)
            row_widget = self._create_joint_row(finger, jname, cn, color)
            layout.addWidget(row_widget)
            self._joint_rows[jname] = row_widget

        return group

    def _create_joint_row(self, finger: str, joint_name: str,
                          joint_cn: str, finger_color: str) -> QtWidgets.QWidget:
        """
        创建单个关节的3轴旋转滑块行

        每个关节一行，包含: 关节名 + 3个紧凑滑块(X/Y/Z)
        """
        widget = QtWidgets.QWidget()
        vlayout = QtWidgets.QVBoxLayout(widget)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.setSpacing(1)

        # 关节名称标签
        name_label = QtWidgets.QLabel(f"  {joint_cn} ({joint_name})")
        name_label.setStyleSheet(
            f"color: {finger_color}; font-size: 10px; font-weight: bold; "
            f"padding: 1px 0px;"
        )
        vlayout.addWidget(name_label)

        # 三个旋转轴滑块
        self._sliders[finger][joint_name] = {}
        self._value_labels[finger][joint_name] = {}

        for axis_key, axis_label in _AXIS_LABELS.items():
            axis_range = _AXIS_RANGES[axis_key]
            axis_color = _AXIS_COLORS[axis_key]

            row = QtWidgets.QHBoxLayout()
            row.setSpacing(3)
            row.setContentsMargins(8, 0, 4, 0)

            # 轴标签
            lbl = QtWidgets.QLabel(f"{axis_label}")
            lbl.setFixedWidth(26)
            lbl.setStyleSheet(
                f"color: {axis_color}; font-size: 9px; font-weight: bold;"
            )
            row.addWidget(lbl)

            # 滑块
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setMinimum(axis_range[0] * 10)  # 0.1° 精度
            slider.setMaximum(axis_range[1] * 10)
            slider.setValue(0)
            slider.setStyleSheet(f"""
                QSlider::groove:horizontal {{
                    background: #1e2230; height: 3px; border-radius: 1px;
                }}
                QSlider::handle:horizontal {{
                    background: {axis_color}; width: 10px; height: 10px;
                    margin: -4px 0; border-radius: 5px;
                }}
                QSlider::sub-page:horizontal {{
                    background: {axis_color}; border-radius: 1px; opacity: 0.6;
                }}
            """)
            slider.valueChanged.connect(
                lambda v, f=finger, j=joint_name: self._on_slider_changed(f, j)
            )
            row.addWidget(slider, stretch=1)
            self._sliders[finger][joint_name][axis_key] = slider

            # 数值标签
            val_label = QtWidgets.QLabel("0.0°")
            val_label.setFixedWidth(40)
            val_label.setStyleSheet(
                f"color: {axis_color}; font-family: Consolas; font-size: 9px;"
            )
            row.addWidget(val_label)
            self._value_labels[finger][joint_name][axis_key] = val_label

            vlayout.addLayout(row)

        # 分隔线
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet("color: #1e223088; max-height: 1px;")
        vlayout.addWidget(sep)

        return widget

    # ───────────────────── 槽函数 ─────────────────────
    def _on_slider_changed(self, finger: str, joint_name: str):
        """某个滑块值变化时，发射该关节的3轴旋转角度"""
        sliders = self._sliders[finger][joint_name]
        labels = self._value_labels[finger][joint_name]

        rx = sliders['rx'].value() / 10.0
        ry = sliders['ry'].value() / 10.0
        rz = sliders['rz'].value() / 10.0

        labels['rx'].setText(f"{rx:+.1f}°")
        labels['ry'].setText(f"{ry:+.1f}°")
        labels['rz'].setText(f"{rz:+.1f}°")

        self.joint_rotation_changed.emit(joint_name, rx, ry, rz)

    def _on_reset(self):
        """重置所有滑块到0"""
        for finger, joints in self._sliders.items():
            for jname, axes in joints.items():
                for axis_key, slider in axes.items():
                    slider.blockSignals(True)
                    slider.setValue(0)
                    slider.blockSignals(False)
                    self._value_labels[finger][jname][axis_key].setText("0.0°")

        self.reset_tpose_requested.emit()

    def set_joint_values(self, joint_name: str, rx: float, ry: float, rz: float):
        """
        程序化设置关节滑块值（不触发信号）

        Args:
            joint_name: 语义骨骼名
            rx, ry, rz: 旋转角度（度）
        """
        for finger, joints in self._sliders.items():
            if joint_name in joints:
                axes = joints[joint_name]
                labels = self._value_labels[finger][joint_name]
                values = {'rx': rx, 'ry': ry, 'rz': rz}
                for axis_key, val in values.items():
                    slider = axes[axis_key]
                    slider.blockSignals(True)
                    slider.setValue(int(val * 10))
                    slider.blockSignals(False)
                    labels[axis_key].setText(f"{val:+.1f}°")
                break

    def reset_all_sliders(self):
        """重置所有滑块到0（带信号）"""
        self._on_reset()
