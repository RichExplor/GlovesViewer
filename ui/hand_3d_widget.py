# -*- coding: utf-8 -*-
"""
手部3D骨骼渲染组件 — 基于pyqtgraph.opengl的实时手部模型

美化渲染元素:
- 手掌半透明面片 (暖灰色半透明三角网格)
- 手掌轮廓线段 (亮灰色粗线)
- 5组手指骨骼粗线段 (各手指对应颜色，宽度6)
- 关节球体 (手指对应颜色，更大更光滑)
- 指尖球体 (亮色发光效果，颜色匹配手指)
- 坐标轴指示器 (带端点球)
- 地面网格 (淡色)
- 手掌连接弧线 (拇指到食指)
- 手腕标记 (底部圆柱)
"""
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph.opengl as gl
from pyqtgraph.opengl import MeshData

from core.hand_kinematics import HandKinematics, FINGER_KEYS
from ui.widgets import FINGER_COLORS


class Hand3DWidget(gl.GLViewWidget):
    """手部3D骨骼渲染组件 — 美化版"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundColor('#1a1d24')
        # 相机: 正面稍偏上看竖立的手(手指朝Z+方向)
        self.setCameraPosition(distance=18, elevation=15, azimuth=-45)

        self.kinematics = HandKinematics()

        # 存储所有渲染对象
        self.bone_items = {}        # 手指骨骼线段(粗线)
        self.joint_items = []       # 关节球体
        self.tip_items = []         # 指尖球体
        self.palm_line_items = []   # 手掌轮廓线段
        self.palm_mesh_item = None  # 手掌面片
        self.palm_arc_item = None   # 拇指到食指弧线
        self.wrist_item = None      # 手腕标记

        self._init_scene()
        # 初始渲染展开手掌
        self.update_hand({f: 0.0 for f in FINGER_KEYS})

    def _init_scene(self):
        """初始化3D场景"""
        # 地面网格 — 更淡更优雅
        grid = gl.GLGridItem()
        grid.setSize(20, 20, 1)
        grid.setSpacing(1, 1, 1)
        grid.setDepthValue(10)
        grid.setColor((255, 255, 255, 25))  # 非常淡的白色
        self.addItem(grid)

        # 坐标轴 — 带端点球标记
        axis_data = [
            (np.array([[0,0,0],[3,0,0]]), (1, 0.3, 0.3, 0.8)),   # X - 红(横向)
            (np.array([[0,0,0],[0,3,0]]), (0.3, 1, 0.3, 0.8)),   # Y - 绿(前后)
            (np.array([[0,0,0],[0,0,3]]), (0.3, 0.3, 1, 0.8)),   # Z - 蓝(向上=手指方向)
        ]
        for pos, color in axis_data:
            # 轴线
            item = gl.GLLinePlotItem(pos=pos, color=color, width=2, antialias=True)
            self.addItem(item)
            # 轴端球标记
            arrow_mesh = MeshData.sphere(rows=6, cols=6, radius=0.1)
            arrow_item = gl.GLMeshItem(
                meshdata=arrow_mesh,
                smooth=True,
                color=color,
                shader='shaded',
                glOptions='translucent'
            )
            arrow_item.translate(*pos[1])
            self.addItem(arrow_item)

        # 创建手掌面片
        self._create_palm_mesh()

        # 创建手掌轮廓线
        self._create_palm()

        # 创建拇指到食指弧线
        self._create_palm_arc()

        # 创建手腕标记
        self._create_wrist()

        # 创建5根手指的骨骼线段和关节球
        self._create_fingers()

    def _create_palm_mesh(self):
        """创建手掌半透明面片"""
        vertices, faces, face_colors = self.kinematics.get_palm_mesh_data()
        md = MeshData(vertexes=vertices, faces=faces, faceColors=face_colors)
        self.palm_mesh_item = gl.GLMeshItem(
            meshdata=md,
            smooth=True,
            shader='shaded',
            glOptions='translucent'
        )
        self.addItem(self.palm_mesh_item)

    def _create_palm(self):
        """创建手掌轮廓线段 — 更粗更亮"""
        palm_lines = self.kinematics.get_palm_outline()
        for start, end in palm_lines:
            pos = np.array([start, end])
            item = gl.GLLinePlotItem(
                pos=pos,
                color=(0.6, 0.63, 0.7, 0.7),
                width=4,
                antialias=True
            )
            self.addItem(item)
            self.palm_line_items.append(item)

    def _create_palm_arc(self):
        """创建拇指到食指的弧形连接线"""
        thumb_base = np.array([2.0, 0.5, 0.0])
        index_base = np.array([1.2, 0.0, 0.0])
        # 生成弧线上的多个点
        n_points = 10
        t_values = np.linspace(0, 1, n_points)
        arc_points = []
        for t in t_values:
            p = (1 - t) * thumb_base + t * index_base
            # 添加弧形偏移(向外弯曲)
            p[1] += 0.3 * np.sin(np.pi * t)  # Y方向隆起(手背方向)
            p[2] -= 0.5 * np.sin(np.pi * t)  # Z方向下弯(手腕方向)
            arc_points.append(p)
        pos = np.array(arc_points)
        self.palm_arc_item = gl.GLLinePlotItem(
            pos=pos,
            color=(0.55, 0.58, 0.65, 0.6),
            width=3.5,
            antialias=True,
            mode='line_strip'
        )
        self.addItem(self.palm_arc_item)

    def _create_wrist(self):
        """创建手腕标记 — 底部球体(手腕方向=Z负方向)"""
        wrist_mesh = MeshData.sphere(rows=8, cols=12, radius=0.3)
        self.wrist_item = gl.GLMeshItem(
            meshdata=wrist_mesh,
            smooth=True,
            color=(0.4, 0.43, 0.5, 0.6),
            shader='shaded',
            glOptions='translucent'
        )
        self.wrist_item.translate(0, 0, -1.0)
        self.addItem(self.wrist_item)

    def _create_fingers(self):
        """创建5根手指的骨骼线段和关节球体"""
        for finger in FINGER_KEYS:
            color_hex = FINGER_COLORS.get(finger, '#ffffff')
            color = self._hex_to_rgba(color_hex, alpha=0.95)

            # 骨骼线段 — 更粗的连续线
            bone_item = gl.GLLinePlotItem(
                pos=np.array([[0,0,0],[0,1,0]]),
                color=color,
                width=6,
                antialias=True,
                mode='line_strip'
            )
            self.addItem(bone_item)
            self.bone_items[finger] = bone_item

        # 关节球体 — 更大更光滑，颜色匹配手指
        for finger in FINGER_KEYS:
            color_hex = FINGER_COLORS.get(finger, '#ffffff')
            rgba = self._hex_to_rgba(color_hex, alpha=0.9)
            n_joints = 2 if finger == 'thumb' else 3
            for _ in range(n_joints):
                joint_mesh = MeshData.sphere(rows=12, cols=12, radius=0.22)
                item = gl.GLMeshItem(
                    meshdata=joint_mesh,
                    smooth=True,
                    color=rgba,
                    shader='shaded',
                    glOptions='translucent'
                )
                item.setVisible(False)
                self.addItem(item)
                self.joint_items.append(item)

        # 指尖球 — 更大、更亮、颜色匹配手指
        for finger in FINGER_KEYS:
            color_hex = FINGER_COLORS.get(finger, '#ffffff')
            # 指尖颜色更亮(提亮20%)
            rgba = self._hex_to_rgba(color_hex, alpha=1.0)
            rgba = (
                min(rgba[0] + 0.2, 1.0),
                min(rgba[1] + 0.2, 1.0),
                min(rgba[2] + 0.2, 1.0),
                1.0
            )

            tip_mesh = MeshData.sphere(rows=12, cols=12, radius=0.18)
            item = gl.GLMeshItem(
                meshdata=tip_mesh,
                smooth=True,
                color=rgba,
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

        # 更新骨骼线段 — 使用line_strip模式
        for finger in FINGER_KEYS:
            finger_joints = joints[finger]
            if not finger_joints:
                continue
            pos_array = np.array(finger_joints)
            self.bone_items[finger].setData(pos=pos_array)

        # 更新手掌轮廓
        palm_lines = self.kinematics.get_palm_outline()
        for i, (start, end) in enumerate(palm_lines):
            if i < len(self.palm_line_items):
                self.palm_line_items[i].setData(pos=np.array([start, end]))

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
