# -*- coding: utf-8 -*-
"""
自定义UI组件 — 角度仪表盘、手指滑条控制器
"""
import math
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

# 手指对应颜色（包含手背）— 更鲜明现代的配色
FINGER_COLORS = {
    'thumb': '#f87171',   # 红
    'index': '#4ade80',   # 绿
    'middle': '#fbbf24',  # 黄
    'ring': '#60a5fa',    # 蓝
    'pinky': '#c084fc',   # 紫
    'palm': '#2dd4bf',    # 青
}

# 仪表盘中用到的暗色背景弧线
_BG_ARC_COLOR = "#1e2230"
_TICK_COLOR = "#2d3348"


class AngleGaugeWidget(QtWidgets.QWidget):
    """单个手指角度仪表盘，显示手指名称+角度值+弧形进度条 — 高级渐变版"""

    def __init__(self, finger_name: str, parent=None):
        super().__init__(parent)
        self.finger_name = finger_name
        self.angle = 0.0
        self.color = QtGui.QColor(FINGER_COLORS.get(finger_name, '#ffffff'))
        self.setFixedSize(52, 80)

    def set_angle(self, angle: float):
        self.angle = max(0.0, min(180.0, angle))
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2 + 10
        radius = self.width() / 2 - 5

        # === 背景弧线（带细微刻度）===
        painter.setPen(QtGui.QPen(QtGui.QColor(_BG_ARC_COLOR), 5, cap=QtCore.Qt.RoundCap))
        painter.setBrush(QtCore.Qt.NoBrush)
        rect = QtCore.QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
        painter.drawArc(rect, 180 * 16, -180 * 16)

        # === 刻度线（3条）===
        painter.setPen(QtGui.QPen(QtGui.QColor(_TICK_COLOR), 1))
        for frac in [0.25, 0.5, 0.75]:
            angle_rad = math.radians(180.0 * (1.0 - frac))
            inner = radius - 6
            outer = radius + 2
            x1 = cx + inner * math.cos(angle_rad)
            y1 = cy - inner * math.sin(angle_rad)
            x2 = cx + outer * math.cos(angle_rad)
            y2 = cy - outer * math.sin(angle_rad)
            painter.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))

        # === 进度弧线（渐变色）===
        span = int((self.angle / 180.0) * 180 * 16)
        if span > 0:
            # 创建弧线渐变
            gradient = QtGui.QConicalGradient(cx, cy, 180)
            gradient.setColorAt(0.0, self.color.darker(130))
            gradient.setColorAt(0.5, self.color)
            gradient.setColorAt(1.0, self.color.lighter(120))
            pen = QtGui.QPen(gradient, 5, cap=QtCore.Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, 180 * 16, -span)

        # === 末端指示点 ===
        if self.angle > 0:
            end_angle_rad = math.radians(180.0 * (1.0 - self.angle / 180.0))
            dot_x = cx + radius * math.cos(end_angle_rad)
            dot_y = cy - radius * math.sin(end_angle_rad)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(self.color.lighter(140)))
            painter.drawEllipse(QtCore.QPointF(dot_x, dot_y), 3, 3)

        # === 角度数值 ===
        painter.setPen(QtGui.QColor("#f1f5f9"))
        painter.setFont(QtGui.QFont("Consolas", 10, QtGui.QFont.Bold))
        text_rect = QtCore.QRectF(cx - radius, cy - 6, 2 * radius, 18)
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, f"{self.angle:.0f}°")

        # === 手指名称（顶部居中）===
        painter.setPen(QtGui.QColor("#475569"))
        painter.setFont(QtGui.QFont("Microsoft YaHei", 7, QtGui.QFont.Bold))
        label = FINGER_LABELS.get(self.finger_name, self.finger_name)
        painter.drawText(QtCore.QRect(0, 0, self.width(), 18), QtCore.Qt.AlignCenter, label)

        painter.end()


class FingerSliderGroup(QtWidgets.QGroupBox):
    """5根手指的滑条控制器组，用于模拟手动模式"""

    angle_changed = QtCore.pyqtSignal(str, float)  # finger_name, angle

    def __init__(self, parent=None):
        super().__init__("🎛️ 手动控制", parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 20, 10, 10)

        self.sliders = {}
        self.value_labels = {}

        for finger in FINGER_KEYS:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(6)

            label = QtWidgets.QLabel(FINGER_LABELS[finger])
            label.setFixedWidth(40)
            label.setStyleSheet(
                f"color: {FINGER_COLORS[finger]}; font-weight: bold; font-size: 11px;"
            )

            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 1800)  # 0.1°精度
            slider.setValue(0)
            slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: #1e2230; height: 4px; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {FINGER_COLORS[finger]}; width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {FINGER_COLORS[finger]}; border: 2px solid #ffffff;
            }}
            QSlider::sub-page:horizontal {{
                background: {FINGER_COLORS[finger]}; border-radius: 2px;
                opacity: 0.7;
            }}
            """)

            val_label = QtWidgets.QLabel("0.0°")
            val_label.setFixedWidth(48)
            val_label.setStyleSheet(
                "color: #94a3b8; font-family: Consolas; font-size: 10px;"
            )

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
