# -*- coding: utf-8 -*-
"""
GLB 手部骨骼模型加载器 — 解析 bones_of_the_hand.glb 的骨骼树与网格

核心策略:
  该GLB模型中骨骼节点的局部变换矩阵全部为单位矩阵,
  真正的视觉位置存储在每个骨骼关联的几何体(mesh)顶点中.
  因此本加载器从mesh中心提取骨骼位置, 并重建解剖学层级树.

骨骼层级 (重建后的逻辑树):
  Wrist_Root (Radius+Ulna)
  ├── Carpal_Hamate  ─── Ring_Meta → Ring_Prox → Ring_Mid → Ring_Dist
  ├── Carpal_Capitate ─── Middle_Meta → Middle_Prox → Middle_Mid → Middle_Dist
  ├── Carpal_Trapezium ─── Thumb_Meta → Thumb_Prox → Thumb_Dist (拇指无中节)
  ├── Carpal_Trapezoid ─── Index_Meta → Index_Prox → Index_Mid → Index_Dist
  ├── Carpal_Scaphoid
  ├── Carpal_Lunate
  ├── Carpal_Pisiform
  ├── Carpal_Triquetral ─── Pinky_Meta → Pinky_Prox → Pinky_Mid → Pinky_Dist
"""
import os
import re
import numpy as np


# ── 原始 GLB 骨骼名(清洗后) -> 简化语义名 ──
HAND_BONE_MAPPING = {
    "Retopo_Radius":                  "Carpal_Radius",
    "Retopo_Ulna":                    "Wrist_Root",
    "Retopo_Hamate":                  "Carpal_Hamate",
    "Retopo_Lunate":                  "Carpal_Lunate",
    "Retopo_Pisiform":                "Carpal_Pisiform",
    "Retopo_Scaphoid":                "Carpal_Scaphoid",
    "Retopo_Trapezium":               "Carpal_Trapezium",
    "Retopo_Trapezoid":               "Carpal_Trapezoid",
    "Retopo_Triquetral":              "Carpal_Triquetral",
    "Retopo_Capitate":                "Carpal_Capitate",
    "Retopo_1st Metacarpal_5":          "Thumb_Meta",
    "Retopo_2nd Metacarpal_9":          "Index_Meta",
    "Retopo_3rd Metacarpal_13":          "Middle_Meta",
    "Retopo_4th Metacarpal_17":          "Ring_Meta",
    "Retopo_5th Metacarpal_21":          "Pinky_Meta",
    "Retopo_1st Proximal Phalanx_7":    "Thumb_Prox",
    "Retopo_2nd Proximal Phalanx_11":    "Index_Prox",
    "Retopo_3rd Proximal Phalanx_15":    "Middle_Prox",
    "Retopo_4th Proximal Phalanx_19":    "Ring_Prox",
    "Retopo_5th Proximal Phalanx_22":    "Pinky_Prox",

    "Retopo_1st Middle Plalanx_6":      "Index_Mid",
    "Retopo_2nd Middle Plalanx_10":      "Middle_Mid",
    "Retopo_3rd Middle Plalanx_14":      "Ring_Mid",
    "Retopo_4th Middle Plalanx_18":      "Pinky_Mid",

    "Retopo_1st Distal Plalanx_4":      "Thumb_Dist",
    "Retopo_2nd Distal Plalanx_8":      "Index_Dist",
    "Retopo_3rd Distal Plalanx_12":      "Middle_Dist",
    "Retopo_4th Distal Plalanx_16":      "Ring_Dist",
    "Retopo_5th Distal Plalanx_20":      "Pinky_Dist",
}


def clean_bone_name(raw_name: str) -> str:
    """清洗骨骼名称：去除尾部下划线数字后缀，并纠正拼写错误"""
    if not raw_name:
        return ""
    # cleaned = re.sub(r'_\d+$', '', raw_name.strip())
    # cleaned = cleaned.replace("Plalanx", "Phalanx")
    cleaned = raw_name
    return cleaned


# ── 手指分组 (反映GLB模型实际骨骼) ──
# 注意: 拇指(1st)缺少 Middle Phalanx, 小指有 Mid
FINGER_GROUPS = {
    'thumb':  ['Thumb_Meta', 'Thumb_Prox', 'Thumb_Dist'],
    'index':  ['Index_Meta', 'Index_Prox', 'Index_Mid', 'Index_Dist'],
    'middle': ['Middle_Meta', 'Middle_Prox', 'Middle_Mid', 'Middle_Dist'],
    'ring':   ['Ring_Meta', 'Ring_Prox', 'Ring_Mid', 'Ring_Dist'],
    'pinky':  ['Pinky_Meta', 'Pinky_Prox', 'Pinky_Mid', 'Pinky_Dist'],
}

CARPAL_BONES = [
    'Carpal_Hamate', 'Carpal_Lunate', 'Carpal_Pisiform', 'Carpal_Capitate',
    'Carpal_Scaphoid', 'Carpal_Trapezium', 'Carpal_Trapezoid', 'Carpal_Triquetral',
]

# 每个手指的可控关节（不含掌骨Meta，掌骨通常不动）
FINGER_JOINTS = {
    'thumb':  ['Thumb_Prox', 'Thumb_Dist'],  # 拇指无Mid
    'index':  ['Index_Prox', 'Index_Mid', 'Index_Dist'],
    'middle': ['Middle_Prox', 'Middle_Mid', 'Middle_Dist'],
    'ring':   ['Ring_Prox', 'Ring_Mid', 'Ring_Dist'],
    'pinky':  ['Pinky_Prox', 'Pinky_Mid', 'Pinky_Dist'],
}

# 所有可控关节列表（仅五指，不含手腕和腕骨）
CONTROLLABLE_JOINTS = (
    FINGER_GROUPS['thumb'] + FINGER_GROUPS['index'] +
    FINGER_GROUPS['middle'] + FINGER_GROUPS['ring'] +
    FINGER_GROUPS['pinky']
)

# 中文标签
JOINT_CN_LABELS = {
    'Wrist_Root':       '腕根(尺骨)',   'Carpal_Radius':   '桡骨',
    'Carpal_Hamate':    '钩骨',         'Carpal_Lunate':    '月骨',
    'Carpal_Pisiform':  '豌豆骨',       'Carpal_Capitate':  '头状骨',
    'Carpal_Scaphoid':  '舟骨',         'Carpal_Trapezium': '大多角骨',
    'Carpal_Trapezoid': '小多角骨',     'Carpal_Triquetral':'三角骨',
    'Thumb_Meta':  '拇掌骨', 'Index_Meta':  '食掌骨', 'Middle_Meta': '中掌骨',
    'Ring_Meta':   '无名掌骨', 'Pinky_Meta':  '小掌骨',
    'Thumb_Prox':  '拇近节', 'Index_Prox':  '食近节', 'Middle_Prox': '中近节',
    'Ring_Prox':   '无名近节', 'Pinky_Prox':  '小近节',
    'Index_Mid':   '食中节', 'Middle_Mid':  '中中节',
    'Ring_Mid':    '无名中节', 'Pinky_Mid':   '小中节',
    'Thumb_Dist':  '拇远节', 'Index_Dist':  '食远节', 'Middle_Dist': '中远节',
    'Ring_Dist':   '无名远节', 'Pinky_Dist':  '小远节',
}

# ── 解剖学逻辑层级 (子 -> 父) ──
# 用于重建骨骼控制树, 腕骨连掌骨, 掌骨连指骨
_LOGICAL_PARENT = {
    # 腕骨直接挂在 Wrist_Root 下
    'Carpal_Hamate':    'Wrist_Root',
    'Carpal_Lunate':    'Wrist_Root',
    'Carpal_Pisiform':  'Wrist_Root',
    'Carpal_Capitate':  'Wrist_Root',
    'Carpal_Scaphoid':  'Wrist_Root',
    'Carpal_Trapezium': 'Wrist_Root',
    'Carpal_Trapezoid': 'Wrist_Root',
    'Carpal_Triquetral':'Wrist_Root',
    'Carpal_Radius':    'Wrist_Root',
    # 拇指: Trapezium -> Metacarpal -> Prox -> Dist (无Mid)
    'Thumb_Meta': 'Carpal_Trapezium',
    'Thumb_Prox': 'Thumb_Meta',
    'Thumb_Dist': 'Thumb_Prox',
    # 食指: Trapezoid -> Metacarpal -> Prox -> Mid -> Dist
    'Index_Meta': 'Carpal_Trapezoid',
    'Index_Prox': 'Index_Meta',
    'Index_Mid':  'Index_Prox',
    'Index_Dist': 'Index_Mid',
    # 中指: Capitate -> Metacarpal -> Prox -> Mid -> Dist
    'Middle_Meta': 'Carpal_Capitate',
    'Middle_Prox': 'Middle_Meta',
    'Middle_Mid':  'Middle_Prox',
    'Middle_Dist': 'Middle_Mid',
    # 无名指: Hamate -> Metacarpal -> Prox -> Mid -> Dist
    'Ring_Meta': 'Carpal_Hamate',
    'Ring_Prox': 'Ring_Meta',
    'Ring_Mid':  'Ring_Prox',
    'Ring_Dist': 'Ring_Mid',
    # 小指: Triquetral -> Metacarpal -> Prox -> Mid -> Dist
    'Pinky_Meta': 'Carpal_Triquetral',
    'Pinky_Prox': 'Pinky_Meta',
    'Pinky_Mid':  'Pinky_Prox',
    'Pinky_Dist': 'Pinky_Mid',
}


class BoneNode:
    """单个骨骼节点"""
    __slots__ = ('name', 'semantic_name', 'index', 'parent_index',
                 'children_indices', 'mesh_center', 'mesh_extent',
                 't_pose_matrix', 'local_matrix', 'world_matrix',
                 'rotation_euler', 'geometry_name')

    def __init__(self, name: str, index: int, parent_index: int = -1):
        self.name = name
        cleaned_name = clean_bone_name(name)
        self.semantic_name = HAND_BONE_MAPPING.get(cleaned_name, cleaned_name)
        self.index = index
        self.parent_index = parent_index
        self.children_indices = []
        # mesh 几何数据
        self.mesh_center = np.zeros(3, dtype=np.float64)
        self.mesh_extent = np.zeros(3, dtype=np.float64)
        self.geometry_name = None
        # 变换矩阵 (4x4)
        self.t_pose_matrix = np.eye(4, dtype=np.float64)
        self.local_matrix = np.eye(4, dtype=np.float64)
        self.world_matrix = np.eye(4, dtype=np.float64)
        # 当前旋转角 (度)
        self.rotation_euler = np.array([0.0, 0.0, 0.0])


class GLBLoader:
    """GLB 手部骨骼模型加载器"""

    # ── 模型姿态归一化参数 ──
    # 原始GLB模型为平躺姿态(手指沿+Y方向)，需要旋转为竖立姿态(手指沿+Z方向)
    # 同时缩放到适合网格显示的大小
    _NORMALIZE_SCALE = 0.28       # 缩放因子，使骨骼在网格(0.5)范围内
    _NORMALIZE_ROT_X = 90.0      # 绕X轴旋转度数(Y→Z竖立)

    def __init__(self):
        self.bones: list[BoneNode] = []
        self.bone_by_semantic: dict[str, BoneNode] = {}
        self.bone_by_index: dict[int, BoneNode] = {}
        self.vertices = None
        self.faces = None
        self.root_bone: BoneNode | None = None
        self.bone_mesh_ranges: dict[str, tuple] = {}
        self._world_scale = 1.0
        self._world_offset = np.zeros(3)

    def load(self, filepath: str) -> bool:
        if not os.path.isfile(filepath):
            print(f"[GLBLoader] 文件不存在: {filepath}")
            return False
        try:
            success = self._load_with_trimesh(filepath)
            if success:
                # 加载完成后，对模型整体进行归一化（旋转竖立+缩放）
                self._normalize_model()
            return success
        except Exception as e:
            print(f"[GLBLoader] trimesh 加载失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _load_with_trimesh(self, filepath: str) -> bool:
        import trimesh
        scene = trimesh.load(filepath, force='scene')
        graph = scene.graph

        # 1. 获取所有节点
        all_nodes = list(graph.nodes)

        # 2. 获取父子关系
        parents = graph.transforms.parents

        # 3. 获取边列表
        edgelist = graph.to_edgelist()

        # 4. 构建 骨骼原始名 -> 几何体名 映射
        bone_to_geom = {}
        for edge in edgelist:
            parent, child = edge[0], edge[1]
            data = edge[2] if len(edge) > 2 else {}
            geometry = data.get('geometry', None)
            if geometry and parent.startswith('Retopo_'):
                cleaned = clean_bone_name(parent)
                if cleaned in HAND_BONE_MAPPING:
                    bone_to_geom[parent] = geometry

        # 5. 获取世界变换矩阵 (Retopo_Radius 节点)
        base_frame = graph.base_frame
        radius_world = np.eye(4, dtype=np.float64)
        for node_name in all_nodes:
            cleaned = clean_bone_name(node_name)
            if cleaned == 'Retopo_Radius':
                try:
                    res = graph.get(frame_to=node_name, frame_from=base_frame)
                    if isinstance(res, tuple) and len(res) > 0:
                        m = np.array(res[0], dtype=np.float64)
                        if m.shape == (4, 4):
                            radius_world = m
                except Exception:
                    pass
                break

        self._world_scale = radius_world[0, 0]
        self._world_offset = radius_world[:3, 3].copy()

        # 6. 筛选骨骼节点
        bone_raw_names_ordered = []
        for node_name in all_nodes:
            cleaned = clean_bone_name(node_name)
            if cleaned in HAND_BONE_MAPPING:
                bone_raw_names_ordered.append(node_name)

        node_order = {name: i for i, name in enumerate(all_nodes)}
        bone_raw_names_ordered.sort(key=lambda n: node_order.get(n, 999))

        # 7. 构建 BoneNode 列表
        self.bones = []
        self.bone_by_semantic = {}
        self.bone_by_index = {}
        name_to_idx = {}

        for i, raw_name in enumerate(bone_raw_names_ordered):
            cleaned = clean_bone_name(raw_name)
            semantic = HAND_BONE_MAPPING[cleaned]

            bone = BoneNode(name=raw_name, index=i, parent_index=-1)
            bone.geometry_name = bone_to_geom.get(raw_name)

            # 从 mesh 获取中心位置
            if bone.geometry_name and bone.geometry_name in scene.geometry:
                geom = scene.geometry[bone.geometry_name]
                if hasattr(geom, 'vertices') and len(geom.vertices) > 0:
                    verts = np.array(geom.vertices, dtype=np.float64)
                    center_local = verts.mean(axis=0)
                    extent = verts.max(axis=0) - verts.min(axis=0)
                    c_h = np.array([center_local[0], center_local[1],
                                    center_local[2], 1.0])
                    world_center = radius_world @ c_h
                    bone.mesh_center = world_center[:3]
                    bone.mesh_extent = extent * self._world_scale

            self.bones.append(bone)
            self.bone_by_semantic[semantic] = bone
            self.bone_by_index[i] = bone
            name_to_idx[semantic] = i

        # 8. 重建逻辑层级
        for bone in self.bones:
            parent_semantic = _LOGICAL_PARENT.get(bone.semantic_name)
            if parent_semantic and parent_semantic in name_to_idx:
                bone.parent_index = name_to_idx[parent_semantic]

        # 9. 构建子节点索引
        for bone in self.bones:
            if 0 <= bone.parent_index < len(self.bones):
                self.bones[bone.parent_index].children_indices.append(bone.index)

        # 10. 查找根节点
        for bone in self.bones:
            if bone.parent_index < 0:
                self.root_bone = bone
                break

        # 11. 构建 T-Pose 变换矩阵
        self._build_tpose_matrices()

        # 12. 提取合并几何体
        self._extract_meshes_trimesh(scene)

        print(f"[GLBLoader] 加载成功: {len(self.bones)} 骨骼, "
              f"{len(self.vertices) if self.vertices is not None else 0} 顶点")

        return len(self.bones) > 0

    def _normalize_model(self):
        """
        对模型整体进行归一化：旋转为竖立姿态 + 缩放到合适大小

        原始GLB模型: 手平躺在XY平面，手指沿+Y方向伸展，掌心朝+Z
        目标姿态:   手指沿+Z方向（竖立），掌心朝+Y（面向观察者）
        变换:      绕X轴旋转-90° (Y→Z, Z→-Y)，然后缩放
        """
        import math

        scale = self._NORMALIZE_SCALE
        rx = math.radians(self._NORMALIZE_ROT_X)
        cx, sx = math.cos(rx), math.sin(rx)

        # 旋转矩阵: 绕X轴旋转
        R = np.array([
            [1,  0,   0],
            [0,  cx, -sx],
            [0,  sx,  cx],
        ], dtype=np.float64)

        # 组合变换: 先旋转后缩放
        T = R * scale  # 3x3

        # 1. 变换所有骨骼的 mesh_center
        for bone in self.bones:
            bone.mesh_center = T @ bone.mesh_center
            # extent 也缩放（不需要旋转，仅缩放）
            bone.mesh_extent = bone.mesh_extent * scale

        # 2. 变换合并的 vertices
        if self.vertices is not None:
            self.vertices = (T @ self.vertices.T).T

        # 3. 重建 T-Pose 矩阵
        self._build_tpose_matrices()

        print(f"[GLBLoader] 模型归一化: 绕X轴旋转{self._NORMALIZE_ROT_X}°, "
              f"缩放{scale:.3f}")

    def _build_tpose_matrices(self):
        """构建 T-Pose 世界变换矩阵"""
        for bone in self.bones:
            mat = np.eye(4, dtype=np.float64)
            mat[:3, 3] = bone.mesh_center
            bone.t_pose_matrix = mat.copy()
            bone.world_matrix = mat.copy()

    def _extract_meshes_trimesh(self, scene):
        """提取并合并所有几何体"""
        all_verts, all_faces = [], []
        offset = 0
        for bone in self.bones:
            if bone.geometry_name and bone.geometry_name in scene.geometry:
                geom = scene.geometry[bone.geometry_name]
                if hasattr(geom, 'vertices') and len(geom.vertices) > 0:
                    verts_local = np.array(geom.vertices, dtype=np.float32)
                    n_v = len(verts_local)
                    # 用 Retopo_Radius 的世界变换缩放+偏移
                    verts_world = verts_local * self._world_scale + self._world_offset

                    if hasattr(geom, 'faces') and len(geom.faces) > 0:
                        faces = np.array(geom.faces, dtype=np.uint32) + offset
                        self.bone_mesh_ranges[bone.semantic_name] = (
                            offset, offset + n_v
                        )
                        all_verts.append(verts_world)
                        all_faces.append(faces)
                        offset += n_v

        if all_verts:
            self.vertices = np.vstack(all_verts).astype(np.float32)
            self.faces = np.vstack(all_faces).astype(np.uint32)

    def reset_to_tpose(self):
        """重置所有骨骼到 T-Pose"""
        for bone in self.bones:
            bone.world_matrix = bone.t_pose_matrix.copy()
            bone.local_matrix = np.eye(4, dtype=np.float64)
            bone.rotation_euler = np.array([0.0, 0.0, 0.0])

    def print_debug_info(self):
        """输出骨骼调试信息"""
        print("\n" + "=" * 70)
        print(f"  骨骼总数: {len(self.bones)}")
        if self.vertices is not None:
            print(f"  顶点数:   {len(self.vertices)}")
        if self.faces is not None:
            print(f"  面片数:   {len(self.faces)}")
        if self.root_bone is not None:
            print("\n  骨骼层级树:")
            self._print_bone_tree(self.root_bone, indent=0)
        print("\n  各骨骼世界位置:")
        for bone in self.bones:
            pos = bone.mesh_center
            cn = JOINT_CN_LABELS.get(bone.semantic_name, "")
            cn_str = f" ({cn})" if cn else ""
            print(f"    {bone.semantic_name:20s}{cn_str:12s}"
                  f"  pos=[{pos[0]:+.4f}, {pos[1]:+.4f}, {pos[2]:+.4f}]"
                  f"  extent=[{bone.mesh_extent[0]:.4f}, {bone.mesh_extent[1]:.4f}, {bone.mesh_extent[2]:.4f}]")
        print("=" * 70)

    def _print_bone_tree(self, bone: BoneNode, indent: int):
        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        cn = JOINT_CN_LABELS.get(bone.semantic_name, "")
        cn_str = f" ({cn})" if cn else ""
        pos = bone.mesh_center
        print(f"{prefix}{bone.semantic_name}{cn_str}"
              f"  [{pos[0]:+.4f}, {pos[1]:+.4f}, {pos[2]:+.4f}]")
        for child_idx in bone.children_indices:
            if 0 <= child_idx < len(self.bones):
                self._print_bone_tree(self.bones[child_idx], indent + 1)
