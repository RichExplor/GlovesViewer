# -*- coding: utf-8 -*-
"""
自定义UI组件 — 角度仪表盘、手指滑条控制器
"""
from PyQt5 import QtWidgets, QtCore, QtGui
from core.hand_kinematics import FINGER_KEYS

# 手指中英文映射（包含手背）
FINGER_LABELS = {
    'thumb': '拇指',
    'index': '食指',
    'middle': '中指',
    'ring': '无名指',
    'pinky': '小指',
    'palm': '手背',
}

# 手指对应颜色（包含手背）
FINGER_COLORS = {
    'thumb': '#e06c75',
    'index': '#98c379',
    'middle': '#e5c07b',
    'ring': '#61afef',
    'pinky': '#c678dd',
    'palm': '#56b6c2',
}


class AngleGaugeWidget(QtWidgets.QWidget):
    """单个手指角度仪表盘，显示手指名称+角度值+弧形进度条"""

    def __init__(self, finger_name: str, parent=None):
        super().__init__(parent)
        self.finger_name = finger_name
        self.angle = 0.0
        self.color = QtGui.QColor(FINGER_COLORS.get(finger_name, '#ffffff'))
        self.setFixedSize(48, 72)

    def set_angle(self, angle: float):
        self.angle = max(0.0, min(180.0, angle))
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2 + 8
        radius = self.width() / 2 - 4

        # 背景圆弧
        painter.setPen(QtGui.QPen(QtGui.QColor("#2d3139"), 4))
        painter.setBrush(QtCore.Qt.NoBrush)
        rect = QtCore.QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
        painter.drawArc(rect, 180 * 16, -180 * 16)

        # 进度圆弧
        span = int((self.angle / 180.0) * 180 * 16)
        painter.setPen(QtGui.QPen(self.color, 4, cap=QtCore.Qt.RoundCap))
        painter.drawArc(rect, 180 * 16, -span)

        # 角度数值
        painter.setPen(QtGui.QColor("#ffffff"))
        painter.setFont(QtGui.QFont("Consolas", 9, QtGui.QFont.Bold))
        painter.drawText(rect, QtCore.Qt.AlignCenter, f"{self.angle:.0f}°")

        # 手指名称
        painter.setPen(QtGui.QColor("#5c6370"))
        painter.setFont(QtGui.QFont("Segoe UI", 7, QtGui.QFont.Bold))
        label = FINGER_LABELS.get(self.finger_name, self.finger_name)
        painter.drawText(QtCore.QRect(0, 0, self.width(), 16), QtCore.Qt.AlignCenter, label)

        painter.end()


class FingerSliderGroup(QtWidgets.QGroupBox):
    """5根手指的滑条控制器组，用于模拟手动模式"""

    angle_changed = QtCore.pyqtSignal(str, float) # finger_name, angle

    def __init__(self, parent=None):
        super().__init__("手动控制", parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 12, 8, 8)

        self.sliders = {}
        self.value_labels = {}

        for finger in FINGER_KEYS:
            row = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(FINGER_LABELS[finger])
            label.setFixedWidth(36)
            label.setStyleSheet(f"color: {FINGER_COLORS[finger]}; font-weight: bold; font-size: 11px;")

            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 1800) # 0.1°精度
            slider.setValue(0)
            slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2d3139; height: 6px; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #61afef; width: 14px; margin: -4px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #61afef; border-radius: 3px;
            }
            """)

            val_label = QtWidgets.QLabel("0.0°")
            val_label.setFixedWidth(42)
            val_label.setStyleSheet("color: #abb2bf; font-family: Consolas; font-size: 10px;")

            slider.valueChanged.connect(
                lambda v, f=finger, vl=val_label: self._on_slider_changed(f, v, vl)
            )

            row.addWidget(label)
            row.addWidget(slider, stretch=1)
            row.addWidget(val_label)
            layout.addLayout(row)

            self.sliders[finger] = slider
            self.value_labels[finger] = val_label

    def _on_slider_changed(self, finger, value, val_label):
        angle = value / 10.0
        val_label.setText(f"{angle:.1f}°")
        self.angle_changed.emit(finger, angle)

    def set_enabled(self, enabled: bool):
        for slider in self.sliders.values():
            slider.setEnabled(enabled)

    def reset(self):
        for slider in self.sliders.values():
            slider.setValue(0)
