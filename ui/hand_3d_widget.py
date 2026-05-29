# -*- coding: utf-8 -*-
"""
手部3D骨骼渲染组件 — 基于pyqtgraph.opengl的实时手部模型

渲染元素:
  - 手掌轮廓线段 (灰色)
  - 5组手指骨骼线段 (各手指对应颜色)
  - 关节球体 (橙色半透明)
  - 指尖球体 (红色半透明)
  - 坐标轴指示器
  - 地面网格
"""
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph.opengl as gl

from core.hand_kinematics import HandKinematics, FINGER_KEYS
from ui.widgets import FINGER_COLORS


class Hand3DWidget(gl.GLViewWidget):
    """手部3D骨骼渲染组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundColor('#1a1d24')
        self.setCameraPosition(distance=18, elevation=25, azimuth=-60)

        self.kinematics = HandKinematics()

        # 存储所有渲染对象
        self.bone_items = {}      # 手指骨骼线段
        self.joint_items = []     # 关节球体
        self.palm_items = []      # 手掌轮廓线段
        self.tip_items = []       # 指尖球体

        self._init_scene()
        # 初始渲染展开手掌
        self.update_hand({f: 0.0 for f in FINGER_KEYS})

    def _init_scene(self):
        """初始化3D场景"""
        # 地面网格
        grid = gl.GLGridItem()
        grid.setSize(20, 20, 1)
        grid.setSpacing(1, 1, 1)
        grid.setDepthValue(10)
        self.addItem(grid)

        # 坐标轴
        axis_data = [
            (np.array([[0,0,0],[3,0,0]]), (1, 0.3, 0.3, 1)),  # X - 红
            (np.array([[0,0,0],[0,3,0]]), (0.3, 1, 0.3, 1)),  # Y - 绿
            (np.array([[0,0,0],[0,0,3]]), (0.3, 0.3, 1, 1)),  # Z - 蓝
        ]
        for pos, color in axis_data:
            item = gl.GLLinePlotItem(pos=pos, color=color, width=2, antialias=True)
            self.addItem(item)

        # 创建手掌轮廓
        self._create_palm()

        # 创建5根手指的骨骼线段和关节球
        self._create_fingers()

    def _create_palm(self):
        """创建手掌轮廓线段"""
        palm_lines = self.kinematics.get_palm_outline()
        for start, end in palm_lines:
            pos = np.array([start, end])
            item = gl.GLLinePlotItem(
                pos=pos,
                color=(0.5, 0.5, 0.5, 0.6),
                width=3,
                antialias=True
            )
            self.addItem(item)
            self.palm_items.append(item)

    def _create_fingers(self):
        """创建5根手指的骨骼线段和关节球体"""
        for finger in FINGER_KEYS:
            color_hex = FINGER_COLORS.get(finger, '#ffffff')
            color = self._hex_to_rgba(color_hex, alpha=0.9)

            # 骨骼线段 — 使用连续线模式(mode='line_strip')而非独立线段
            bone_item = gl.GLLinePlotItem(
                pos=np.array([[0,0,0],[0,1,0]]),
                color=color,
                width=4,
                antialias=True,
                mode='line_strip'
            )
            self.addItem(bone_item)
            self.bone_items[finger] = bone_item

        # 创建关节球体（预分配最大数量）
        # 拇指: 4个关节点(含根部), 中间2个关节球
        # 四指: 5个关节点(含根部), 中间3个关节球
        # 总关节数: 2 + 3*4 = 14
        total_joints = 2 + 3 * 4  # 14
        total_tips = 5

        # 关节球
        joint_mesh = gl.MeshData.sphere(rows=8, cols=8, radius=0.15)
        for _ in range(total_joints):
            item = gl.GLMeshItem(
                meshdata=joint_mesh,
                smooth=True,
                color=(1.0, 0.6, 0.2, 0.8),
                shader='shaded',
                glOptions='translucent'
            )
            item.setVisible(False)
            self.addItem(item)
            self.joint_items.append(item)

        # 指尖球
        tip_mesh = gl.MeshData.sphere(rows=8, cols=8, radius=0.12)
        for _ in range(total_tips):
            item = gl.GLMeshItem(
                meshdata=tip_mesh,
                smooth=True,
                color=(0.9, 0.2, 0.2, 0.9),
                shader='shaded',
                glOptions='translucent'
            )
            item.setVisible(False)
            self.addItem(item)
            self.tip_items.append(item)

    def update_hand(self, angles: dict):
        """
        根据手指弯曲度更新3D手部模型

        Args:
            angles: {thumb: 45.0, index: 30.0, ...}
        """
        result = self.kinematics.compute(angles)
        joints = result['joints']

        # 更新骨骼线段 — 使用line_strip模式，直接传入所有关节点
        for finger in FINGER_KEYS:
            finger_joints = joints[finger]
            if not finger_joints:
                continue

            # 将所有关节坐标组成连续路径
            pos_array = np.array(finger_joints)
            self.bone_items[finger].setData(pos=pos_array)

        # 更新手掌轮廓
        palm_lines = self.kinematics.get_palm_outline()
        for i, (start, end) in enumerate(palm_lines):
            if i < len(self.palm_items):
                self.palm_items[i].setData(pos=np.array([start, end]))

        # 更新关节球位置
        joint_idx = 0
        for finger in FINGER_KEYS:
            finger_joints = joints[finger]
            # 跳过第一个关节（手掌根部）和最后一个（指尖），只显示中间关节
            for j in range(1, len(finger_joints) - 1):
                if joint_idx < len(self.joint_items):
                    pos = finger_joints[j]
                    self.joint_items[joint_idx].resetTransform()
                    self.joint_items[joint_idx].translate(pos[0], pos[1], pos[2])
                    self.joint_items[joint_idx].setVisible(True)
                    joint_idx += 1

        # 隐藏多余的关节球
        while joint_idx < len(self.joint_items):
            self.joint_items[joint_idx].setVisible(False)
            joint_idx += 1

        # 更新指尖球位置
        tip_idx = 0
        for finger in FINGER_KEYS:
            finger_joints = joints[finger]
            if tip_idx < len(self.tip_items):
                tip_pos = finger_joints[-1]
                self.tip_items[tip_idx].resetTransform()
                self.tip_items[tip_idx].translate(tip_pos[0], tip_pos[1], tip_pos[2])
                self.tip_items[tip_idx].setVisible(True)
                tip_idx += 1

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple:
        """将十六进制颜色转换为RGBA元组"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b, alpha)
