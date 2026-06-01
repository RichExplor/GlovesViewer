# -*- coding: utf-8 -*-
"""
模拟数据模式 — 无需真实硬件即可测试3D模型渲染

提供两种模拟模式:
1. 正弦波模式: 每根手指以不同频率和相位做正弦弯曲运动
2. 手动滑条模式: 用户通过UI滑条手动控制每根手指弯曲度
"""
import time
import math
from PyQt5 import QtCore

from core.frame_parser import FINGER_KEYS, ALL_KEYS


class SimulatorThread(QtCore.QThread):
    """模拟数据线程，以50Hz频率生成模拟手指弯曲度数据"""
    data_received = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._mode = 'sine'  # 'sine' 或 'manual'
        self._manual_angles = {f: 0.0 for f in FINGER_KEYS}
        self._start_time = 0.0

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        self._mode = value

    def set_manual_angle(self, finger: str, angle: float):
        """设置手动模式下某根手指的角度"""
        self._manual_angles[finger] = max(0.0, min(180.0, angle))

    def start_sim(self):
        self._running = True
        self._start_time = time.time()
        self.start()

    def stop_sim(self):
        self._running = False
        self.wait(1000)

    def run(self):
        """线程主循环，50Hz生成模拟数据"""
        while self._running:
            if self._mode == 'sine':
                t = time.time() - self._start_time
                angles = self._generate_sine_data(t)
            else:
                angles = dict(self._manual_angles)
                # 手动模式下手背默认为0
                angles['palm'] = 0.0

            self.data_received.emit(angles)
            self.msleep(20)  # 50Hz

    def _generate_sine_data(self, t: float) -> dict:
        """
        生成正弦波模拟数据

        每根手指有不同的频率和相位，模拟自然的抓握动作
        手背(palm)也生成模拟数据
        """
        angles = {}
        params = {
            # (振幅, 中心值, 频率Hz, 初相位)
            'thumb': (40.0, 50.0, 0.3, 0.0),
            'index': (35.0, 45.0, 0.4, 0.5),
            'middle': (45.0, 55.0, 0.35, 1.0),
            'ring': (30.0, 40.0, 0.5, 1.5),
            'pinky': (25.0, 35.0, 0.45, 2.0),
            'palm': (20.0, 30.0, 0.25, 0.8),
        }
        for key, (amp, center, freq, phase) in params.items():
            value = center + amp * math.sin(2 * math.pi * freq * t + phase)
            angles[key] = max(0.0, min(180.0, value))

        return angles
