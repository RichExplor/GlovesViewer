# -*- coding: utf-8 -*-
"""
GLB 手部 3D 渲染组件 — 基于骨骼树的实时手部骨骼模型

高级渲染元素:
- GLB 手部骨骼网格 (按骨骼分组的三角面片, 手指对应颜色, 半透明着色)
- 骨骼骨架连线 (各手指对应颜色, 粗线, 圆头)
- 关节球体 (手指对应颜色, 光滑着色)
- 坐标轴指示器 (带端点球)
- 地面网格 (淡色, 大范围)
- T-Pose / 当前姿态切换
"""
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph.opengl as gl
from pyqtgraph.opengl import MeshData
from pyqtgraph import Vector as pgVector

from core.glb_loader import (
    GLBLoader, FINGER_GROUPS, CARPAL_BONES, JOINT_CN_LABELS,
    FINGER_JOINTS, _LOGICAL_PARENT,
)
from core.joint_controller import JointController
from ui.widgets import FINGER_COLORS


# 手指对应颜色 (RGBA 0~1)
_FINGER_RGBA = {
    'thumb': (1.0, 0.2, 0.2, 0.95),
    'index': (0.1, 0.9, 0.3, 0.95),
    'middle': (1.0, 0.8, 0.0, 0.95),
    'ring': (0.2, 0.6, 1.0, 0.95),
    'pinky': (0.8, 0.4, 1.0, 0.95),
}

# 腕骨颜色
_CARPAL_RGBA = (0.55, 0.60, 0.70, 0.85)

# 根骨骼颜色
_ROOT_RGBA = (0.70, 0.70, 0.75, 0.85)

# 桡骨颜色
_RADIUS_RGBA = (0.60, 0.55, 0.65, 0.70)

# 网格面片颜色 (additional alpha for faces)
_MESH_FACE_ALPHA = 0.35


def _bone_to_finger(semantic_name: str) -> str | None:
    """根据语义骨骼名判断所属手指"""
    for finger, bones in FINGER_GROUPS.items():
        if semantic_name in bones:
            return finger
    if semantic_name in CARPAL_BONES:
        return 'carpal'
    if semantic_name == 'Wrist_Root':
        return 'wrist'
    if semantic_name == 'Carpal_Radius':
        return 'radius'
    return None


def _get_bone_color(semantic_name: str) -> tuple:
    """获取骨骼对应的颜色"""
    finger = _bone_to_finger(semantic_name)
    if finger and finger in _FINGER_RGBA:
        return _FINGER_RGBA[finger]
    if finger == 'carpal':
        return _CARPAL_RGBA
    if finger == 'wrist':
        return _ROOT_RGBA
    if finger == 'radius':
        return _RADIUS_RGBA
    return _ROOT_RGBA


class GLBHandWidget(gl.GLViewWidget):
    """GLB 手部 3D 渲染组件 — 骨骼网格 + 骨架"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundColor('#f0f0f0')
        self.setCameraPosition(distance=0.8, elevation=25, azimuth=45)

        # 加载器 & 控制器
        self.loader = GLBLoader()
        self.controller: JointController | None = None
        self._loaded = False

        # 渲染对象缓存
        self._bone_line_items: list = []          # 骨骼线段
        self._joint_sphere_items: list = []       # 关节球 (item)
        self._joint_name_list: list[str] = []     # 关节名列表(与球体对应)
        self._mesh_items: list = []               # 每个骨骼一个mesh item
        self._bone_mesh_names: list[str] = []     # 对应骨骼语义名

        # 初始化场景固定元素
        self._init_scene()

    # ───────────────────── 初始化 ─────────────────────
    def _init_scene(self):
        """初始化3D场景（地面、坐标轴）"""
        # 地面网格
        grid = gl.GLGridItem()
        grid.setSize(0.5, 0.5, 1)
        grid.setSpacing(0.05, 0.05, 1)
        grid.setDepthValue(10)
        grid.setColor((255, 255, 255, 15))
        self.addItem(grid)

        # 坐标轴
        # self._add_axis_indicator()

    def _add_axis_indicator(self):
        """添加坐标轴指示器"""
        axis_len = 0.08
        axes = [
            ([0, 0, 0], [axis_len, 0, 0], (1.0, 0.3, 0.3, 0.6), 'X'),
            ([0, 0, 0], [0, axis_len, 0], (0.3, 1.0, 0.3, 0.6), 'Y'),
            ([0, 0, 0], [0, 0, axis_len], (0.4, 0.6, 1.0, 0.6), 'Z'),
        ]
        for start, end, color, _ in axes:
            pos = np.array([start, end], dtype=np.float32)
            item = gl.GLLinePlotItem(pos=pos, color=color, width=2.0, antialias=True)
            self.addItem(item)
            # 端点球
            tip = MeshData.sphere(rows=6, cols=6, radius=axis_len * 0.06)
            tip_item = gl.GLMeshItem(
                meshdata=tip, smooth=True,
                color=color, shader='shaded', glOptions='translucent'
            )
            tip_item.translate(*end)
            self.addItem(tip_item)

    # ───────────────────── 加载模型 ─────────────────────
    def load_model(self, filepath: str) -> bool:
        """
        加载 GLB 手部模型

        Returns:
            是否加载成功
        """
        success = self.loader.load(filepath)
        if not success:
            print(f"[GLBHandWidget] 模型加载失败: {filepath}")
            return False

        # 创建控制器
        self.controller = JointController(self.loader)
        self._loaded = True

        # 自动调节相机到模型中心
        self._fit_camera()

        # 创建渲染对象
        self._create_bone_skeleton()
        self._create_joint_spheres()
        self._create_bone_meshes()

        # 输出调试信息
        self.loader.print_debug_info()

        # 首次更新
        self.controller.update()
        self._refresh_skeleton_display()

        return True

    def _fit_camera(self):
        """根据模型包围盒调整相机"""
        if self.loader.vertices is not None and len(self.loader.vertices) > 0:
            vmin = self.loader.vertices.min(axis=0)
            vmax = self.loader.vertices.max(axis=0)
            center = (vmin + vmax) / 2.0
            extent = np.linalg.norm(vmax - vmin)
            dist = max(extent * 1.5, 0.6)
            self.setCameraPosition(distance=dist, elevation=25, azimuth=45)
            self.opts['center'] = pgVector(float(center[0]), float(center[1]), float(center[2]))

    # ───────────────────── 创建渲染对象 ─────────────────────
    def _create_bone_skeleton(self):
        """创建骨骼连线"""
        if not self._loaded:
            return
        for bone in self.loader.bones:
            if bone.parent_index >= 0:
                color = _get_bone_color(bone.semantic_name)
                item = gl.GLLinePlotItem(
                    pos=np.array([[0, 0, 0], [0, 0, 0]], dtype=np.float32),
                    color=color,
                    width=4.0,
                    antialias=True,
                    mode='lines'
                )
                item.setVisible(False)
                self.addItem(item)
                self._bone_line_items.append(item)

    def _create_joint_spheres(self):
        """创建关节球体"""
        if not self._loaded:
            return
        self._joint_sphere_items = []
        self._joint_name_list = []

        for bone in self.loader.bones:
            color = _get_bone_color(bone.semantic_name)
            # 尺寸根据骨骼类型调整
            is_tip = bone.semantic_name.endswith('_Dist')
            if _bone_to_finger(bone.semantic_name) in _FINGER_RGBA:
                radius = 0.004 if is_tip else 0.0025
                if is_tip:
                    color = (min(color[0]+0.2, 1), min(color[1]+0.2, 1),
                             min(color[2]+0.2, 1), 1.0)
            elif _bone_to_finger(bone.semantic_name) == 'carpal':
                radius = 0.002
            else:
                radius = 0.003

            sphere_mesh = MeshData.sphere(rows=10, cols=12, radius=radius)
            item = gl.GLMeshItem(
                meshdata=sphere_mesh, smooth=True,
                color=color, shader='shaded', glOptions='translucent'
            )
            item.setVisible(False)
            self.addItem(item)
            self._joint_sphere_items.append(item)
            self._joint_name_list.append(bone.semantic_name)

    def _create_bone_meshes(self):
        """为每个骨骼创建独立的mesh渲染项 (按骨骼分组着色)"""
        if not self._loaded:
            return
        self._mesh_items = []
        self._bone_mesh_names = []

        for bone in self.loader.bones:
            rng = self.loader.bone_mesh_ranges.get(bone.semantic_name)
            if rng is None or self.loader.vertices is None:
                continue
            start_idx, end_idx = rng
            if start_idx >= end_idx:
                continue

            # 获取该骨骼的顶点
            verts = self.loader.vertices[start_idx:end_idx].copy()
            if verts is None or len(verts) == 0:
                continue

            # 计算该骨骼的局部面索引
            # 从全局 faces 中筛选出该骨骼范围内的面
            faces_global = self.loader.faces
            mask = (
                (faces_global >= start_idx) & (faces_global < end_idx)
            ).all(axis=1)
            local_faces = faces_global[mask] - start_idx

            if len(local_faces) == 0:
                continue

            # 按手指颜色着色
            bone_color = _get_bone_color(bone.semantic_name)
            n_faces = len(local_faces)
            face_colors = np.zeros((n_faces, 4), dtype=np.float32)
            face_colors[:, 0] = bone_color[0]
            face_colors[:, 1] = bone_color[1]
            face_colors[:, 2] = bone_color[2]
            face_colors[:, 3] = _MESH_FACE_ALPHA

            try:
                md = MeshData(
                    vertexes=verts.astype(np.float32),
                    faces=local_faces.astype(np.uint32),
                    faceColors=face_colors
                )
                mesh_item = gl.GLMeshItem(
                    meshdata=md,
                    smooth=True,
                    shader='shaded',
                    glOptions='translucent'
                )
                self.addItem(mesh_item)
                self._mesh_items.append(mesh_item)
                self._bone_mesh_names.append(bone.semantic_name)
            except Exception as e:
                # 某些几何体可能有不兼容的面，跳过
                print(f"[GLBHandWidget] 创建mesh失败 ({bone.semantic_name}): {e}")

    # ───────────────────── 渲染更新 ─────────────────────
    def update_hand_from_angles(self, angles: dict):
        """
        从5指弯曲度更新手部模型（兼容原有接口）

        Args:
            angles: {thumb: 45.0, index: 30.0, ...}
        """
        if self.controller is None:
            return
        for finger, bend_angle in angles.items():
            self.controller.set_finger_bend(finger, bend_angle)
        self._do_update()

    def update_joint_rotation(self, semantic_name: str,
                              rx: float | None = None,
                              ry: float | None = None,
                              rz: float | None = None):
        """
        更新单个关节旋转角度并刷新显示

        Args:
            semantic_name: 语义骨骼名 (如 'Index_Prox')
            rx, ry, rz: 绕X/Y/Z轴旋转角度（度）
        """
        if self.controller is None:
            return
        self.controller.set_joint_rotation(semantic_name, rx, ry, rz)
        self._do_update()

    def reset_tpose(self):
        """重置到 T-Pose"""
        if self.controller is None:
            return
        self.controller.reset_to_tpose()
        self._do_update()

    def _do_update(self):
        """执行运动学更新并刷新3D显示"""
        if self.controller is None:
            return
        self.controller.update()
        self._refresh_skeleton_display()

    def _refresh_skeleton_display(self):
        """刷新骨骼线和关节球位置"""
        if self.controller is None:
            return

        # 1. 更新骨骼线
        lines = self.controller.get_skeleton_lines()
        for i, (start, end, sname) in enumerate(lines):
            if i < len(self._bone_line_items):
                pos = np.array([start, end], dtype=np.float32)
                self._bone_line_items[i].setData(pos=pos)
                self._bone_line_items[i].setVisible(True)
        # 隐藏多余线段
        for i in range(len(lines), len(self._bone_line_items)):
            self._bone_line_items[i].setVisible(False)

        # 2. 更新关节球位置
        positions = self.controller.get_joint_positions()
        for i, sname in enumerate(self._joint_name_list):
            if i < len(self._joint_sphere_items):
                pos = positions.get(sname)
                if pos is not None:
                    self._joint_sphere_items[i].resetTransform()
                    self._joint_sphere_items[i].translate(
                        float(pos[0]), float(pos[1]), float(pos[2]))
                    self._joint_sphere_items[i].setVisible(True)
                else:
                    self._joint_sphere_items[i].setVisible(False)

        # 3. 更新网格面片顶点（蒙皮变形）
        if self._mesh_items and self.controller is not None:
            deformed = self.controller.get_deformed_vertices()
            if deformed is not None:
                self._update_mesh_vertices(deformed)

    def _update_mesh_vertices(self, new_verts: np.ndarray):
        """更新每个骨骼mesh的顶点位置"""
        for i, semantic_name in enumerate(self._bone_mesh_names):
            rng = self.loader.bone_mesh_ranges.get(semantic_name)
            if rng is None:
                continue
            start_idx, end_idx = rng
            if start_idx >= end_idx:
                continue

            verts = new_verts[start_idx:end_idx].astype(np.float32)
            if len(verts) == 0:
                continue

            # 获取该骨骼的局部面索引
            faces_global = self.loader.faces
            mask = (
                (faces_global >= start_idx) & (faces_global < end_idx)
            ).all(axis=1)
            local_faces = faces_global[mask] - start_idx

            if len(local_faces) == 0:
                continue

            # 重建 MeshData (pyqtgraph 不支持直接更新顶点)
            bone_color = _get_bone_color(semantic_name)
            n_faces = len(local_faces)
            face_colors = np.zeros((n_faces, 4), dtype=np.float32)
            face_colors[:, 0] = bone_color[0]
            face_colors[:, 1] = bone_color[1]
            face_colors[:, 2] = bone_color[2]
            face_colors[:, 3] = _MESH_FACE_ALPHA

            try:
                md = MeshData(
                    vertexes=verts,
                    faces=local_faces.astype(np.uint32),
                    faceColors=face_colors
                )
                self._mesh_items[i].setMeshData(meshdata=md)
            except Exception:
                pass

    # ───────────────────── 兼容原接口 ─────────────────────
    def update_hand(self, angles: dict):
        """兼容原有 Hand3DWidget 接口"""
        self.update_hand_from_angles(angles)

    def get_loaded_bone_names(self) -> list[str]:
        """获取已加载的所有骨骼语义名"""
        return [b.semantic_name for b in self.loader.bones]
