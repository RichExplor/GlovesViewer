# -*- coding: utf-8 -*-
"""
关节独立旋转控制器 — 基于 GLB 骨骼树的手部关节正运动学计算

功能:
1. 每个关节可独立设置欧拉角旋转 (X=弯曲/伸展, Y=外展/内收, Z=扭转)
2. 从根到叶递推计算世界变换矩阵（支持多根骨骼森林）
3. 使用累积旋转正确传播关节旋转变换
4. 支持蒙皮变形（顶点随骨骼运动）
5. 提供 T-Pose 重置
6. 输出关节调试信息

运动学算法:
  对每条手指链(根Meta→末端Dist), 逐节点递推:
    pos[child]   = pos[parent] + cumR[parent] @ offset
    cumR[child]  = cumR[parent] @ R(child_angles)
    world_matrix = T(pos) @ R(cumR)
  其中 offset = child.mesh_center - parent.mesh_center (T-Pose 中的偏移)
  cumR 为从根到当前骨骼的累积旋转矩阵

  弯曲方向约定:
    X轴正旋转(修改符号) = 手指向掌心弯曲 (flexion)
    Y轴正旋转 = 外展 (abduction)
    Z轴正旋转 = 扭转 (twist)
"""
import numpy as np
from core.glb_loader import (
    GLBLoader, BoneNode, FINGER_GROUPS, FINGER_JOINTS,
    CARPAL_BONES, CONTROLLABLE_JOINTS, JOINT_CN_LABELS,
)


def _euler_to_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    """
    欧拉角(度) -> 旋转矩阵 (X->Y->Z 旋转顺序)

    弯曲方向说明:
      在该 GLB 手部模型坐标系中，手指主要沿 +Y 方向伸展，
      掌心面向 +Z 方向（朝向观察者），掌背面向 -Z 方向。
      使用标准右手坐标系 X 旋转矩阵，正 rx 使 +Y 转向 +Z，
      即手指指尖朝 +Z（掌心方向）弯曲 = flexion。

    Returns:
        4x4 齐次变换矩阵
    """
    rx = np.radians(rx_deg)
    ry = np.radians(ry_deg)
    rz = np.radians(rz_deg)

    # X轴旋转（弯曲/伸展）— 标准旋转矩阵：正值=向掌心弯曲
    cx, sx = np.cos(rx), np.sin(rx)
    Rx = np.array([
        [1,  0,   0,  0],
        [0,  cx, -sx, 0],  # 标准：-sx
        [0,  sx,  cx, 0],  # 标准：+sx
        [0,  0,   0,  1],
    ], dtype=np.float64)

    # Y轴旋转（外展/内收）
    cy, sy = np.cos(ry), np.sin(ry)
    Ry = np.array([
        [cy,  0, -sy, 0],
        [0,   1,  0,  0],
        [sy,  0,  cy, 0],
        [0,   0,  0,  1],
    ], dtype=np.float64)

    # Z轴旋转（扭转）
    cz, sz = np.cos(rz), np.sin(rz)
    Rz = np.array([
        [cz, -sz, 0, 0],
        [sz,  cz, 0, 0],
        [0,   0,  1, 0],
        [0,   0,  0, 1],
    ], dtype=np.float64)

    return Rx @ Ry @ Rz


def _rotation_only(angles: np.ndarray) -> np.ndarray:
    """从欧拉角获取3x3旋转矩阵（不含齐次坐标）"""
    return _euler_to_matrix(angles[0], angles[1], angles[2])[:3, :3]


def _translation_matrix(dx, dy, dz) -> np.ndarray:
    """创建4x4平移矩阵"""
    m = np.eye(4, dtype=np.float64)
    m[0, 3] = dx
    m[1, 3] = dy
    m[2, 3] = dz
    return m


class JointController:
    """
    手部关节独立旋转控制器

    使用方法:
        controller = JointController(loader)
        controller.set_joint_rotation('Index_Prox', rx=30)
        controller.update()
        lines = controller.get_skeleton_lines()
    """

    def __init__(self, loader: GLBLoader):
        self.loader = loader
        # 关节旋转角度存储: semantic_name -> (rx, ry, rz) 度
        self._joint_angles: dict[str, np.ndarray] = {}
        # 初始化所有骨骼角度为0
        for bone in loader.bones:
            self._joint_angles[bone.semantic_name] = np.array([0.0, 0.0, 0.0])
        # 为可控关节也初始化
        for sname in CONTROLLABLE_JOINTS:
            if sname not in self._joint_angles:
                self._joint_angles[sname] = np.array([0.0, 0.0, 0.0])
        # 缓存累积旋转和位置
        self._cum_rotations: dict[str, np.ndarray] = {}
        self._positions: dict[str, np.ndarray] = {}

    # ───────────────────── 公开接口 ─────────────────────
    def set_joint_rotation(self, semantic_name: str,
                           rx: float | None = None,
                           ry: float | None = None,
                           rz: float | None = None):
        """设置单个关节的旋转角度（度）"""
        if semantic_name not in self._joint_angles:
            # 尝试忽略大小写匹配
            for key in self._joint_angles:
                if key.lower() == semantic_name.lower():
                    semantic_name = key
                    break
            else:
                print(f"[JointController] 未知关节: {semantic_name}")
                return

        angles = self._joint_angles[semantic_name]
        if rx is not None:
            angles[0] = rx
        if ry is not None:
            angles[1] = ry
        if rz is not None:
            angles[2] = rz

    def get_joint_rotation(self, semantic_name: str) -> np.ndarray:
        """获取关节当前旋转角度 (rx, ry, rz) 度"""
        return self._joint_angles.get(semantic_name, np.zeros(3)).copy()

    def set_finger_bend(self, finger: str, bend_angle: float):
        """
        便捷方法: 设置整根手指的弯曲度（0~180度）
        按比例分配到该手指各关节

        参数:
            finger: 手指键名 ('thumb', 'index', 'middle', 'ring', 'pinky')
            bend_angle: 弯曲角度 0~180°

        旋转约定:
            X轴(rx)正值 = 向掌心弯曲
            Y轴(ry)正值 = 外展（远离中指方向）
        """
        joints = FINGER_JOINTS.get(finger, [])
        if not joints:
            return

        bend_angle = max(0.0, min(180.0, bend_angle))

        if finger == 'thumb':
            # 拇指: 掌骨不动，近节和远节向掌心内弯曲
            # ry正值 = 拇指向掌心内收（经实测验证：+X方向拇指，ry正使+X→+Z即内收）
            self.set_joint_rotation('Thumb_Meta', rx=0.0, ry=0.0, rz=0.0)

            # 拇指2关节: 50% + 50%
            ratios = [0.50, 0.50]
            max_angles = [90.0, 80.0]
            for i, jname in enumerate(joints):
                joint_angle = min(bend_angle * ratios[i], max_angles[i])
                if i == 0:
                    # 拇指近节: rx=弯曲 + ry=内收（向掌心方向弯曲）
                    adduction = min(bend_angle * 0.5, 45.0)
                    self.set_joint_rotation(jname, rx=joint_angle, ry=adduction)
                else:
                    # 拇指远节: 弯曲 + 轻微内收
                    adduction = min(bend_angle * 0.2, 20.0)
                    self.set_joint_rotation(jname, rx=joint_angle, ry=adduction)
        else:
            # 四指3关节: 40% + 35% + 25%
            ratios = [0.40, 0.35, 0.25]
            max_angles = [90.0, 100.0, 80.0]

            # 各手指掌指关节的外展角度
            spread_ry = {
                'index':  -2.0,   # 食指轻微内收
                'middle':  0.0,   # 中指无外展
                'ring':    3.0,   # 无名指轻微外展
                'pinky':   8.0,   # 小指外展较大
            }

            for i, jname in enumerate(joints):
                joint_angle = min(bend_angle * ratios[i], max_angles[i])
                if i == 0:
                    # 掌指关节：弯曲 + 外展
                    self.set_joint_rotation(jname, rx=joint_angle,
                                            ry=spread_ry.get(finger, 0.0))
                else:
                    # 近指间/远指间关节：仅弯曲
                    self.set_joint_rotation(jname, rx=joint_angle)

    def reset_to_tpose(self):
        """重置所有关节到 T-Pose"""
        for key in self._joint_angles:
            self._joint_angles[key] = np.array([0.0, 0.0, 0.0])
        self.loader.reset_to_tpose()
        self._cum_rotations.clear()
        self._positions.clear()

    def update(self):
        """
        递推更新所有骨骼的世界变换矩阵

        采用正确的正运动学(FK)算法:
          1. 识别所有根骨骼（parent_index < 0）
          2. 从每个根出发，深度优先遍历整棵树
          3. 对每个骨骼:
             - 根骨骼: pos = mesh_center, cumR = R(own_angles)
             - 子骨骼: pos = pos_parent + cumR_parent @ offset
                       cumR = cumR_parent @ R(own_angles)
          4. world_matrix = T(pos) @ extend(cumR)

        这确保了:
          - 关节旋转正确累积（多级关节连续弯曲）
          - 偏移向量在父骨骼旋转后的坐标系下表达
          - 所有手指链条被正确处理（不遗漏任何根骨骼）
        """
        processed = set()

        def _update_bone(bone: BoneNode,
                          parent_pos: np.ndarray | None,
                          parent_cumR: np.ndarray | None):
            """递归更新单根骨骼及其所有子节点"""
            if bone.index in processed:
                return
            processed.add(bone.index)

            # 该骨骼自身的欧拉角旋转
            angles = self._joint_angles.get(bone.semantic_name, np.zeros(3))
            R_own = _rotation_only(angles)

            if parent_pos is None:
                # 根骨骼：位置 = T-Pose mesh_center，旋转 = 自身角度
                pos = bone.mesh_center.copy()
                cumR = R_own.copy()
            else:
                # 子骨骼：用父骨骼的累积旋转旋转偏移向量
                offset = bone.mesh_center - self.loader.bones[bone.parent_index].mesh_center
                pos = parent_pos + parent_cumR @ offset
                cumR = parent_cumR @ R_own

            # 缓存
            self._positions[bone.semantic_name] = pos
            self._cum_rotations[bone.semantic_name] = cumR

            # 构建4x4齐次变换矩阵
            T = _translation_matrix(pos[0], pos[1], pos[2])
            R4 = np.eye(4, dtype=np.float64)
            R4[:3, :3] = cumR
            bone.world_matrix = T @ R4

            # 递归处理子节点
            for child_idx in bone.children_indices:
                if 0 <= child_idx < len(self.loader.bones):
                    _update_bone(self.loader.bones[child_idx], pos, cumR)

        # 从所有根骨骼出发（处理多根骨骼森林）
        for bone in self.loader.bones:
            if bone.parent_index < 0:
                _update_bone(bone, parent_pos=None, parent_cumR=None)

    def get_skeleton_lines(self) -> list[tuple[np.ndarray, np.ndarray, str]]:
        """
        获取骨骼连线数据（用于3D渲染骨架线段）

        Returns:
            list of (start_pos_3d, end_pos_3d, semantic_name)
        """
        lines = []
        for bone in self.loader.bones:
            if bone.parent_index >= 0:
                parent = self.loader.bones[bone.parent_index]
                start = parent.world_matrix[:3, 3]
                end = bone.world_matrix[:3, 3]
                lines.append((start.copy(), end.copy(), bone.semantic_name))
        return lines

    def get_joint_positions(self) -> dict[str, np.ndarray]:
        """获取所有关节的世界坐标"""
        positions = {}
        for bone in self.loader.bones:
            positions[bone.semantic_name] = bone.world_matrix[:3, 3].copy()
        return positions

    def get_deformed_vertices(self) -> np.ndarray | None:
        """
        基于骨骼运动计算变形后的顶点位置

        每个骨骼mesh的顶点随骨骼的world_matrix变换移动。
        使用简化策略: 每个骨骼mesh的顶点整体跟随骨骼中心偏移+旋转。

        Returns:
            变形后的顶点坐标 (N, 3)
        """
        if self.loader.vertices is None:
            return None

        result = self.loader.vertices.copy()
        tpose = self.loader  # 别名简写

        for bone in self.loader.bones:
            rng = tpose.bone_mesh_ranges.get(bone.semantic_name)
            if rng is None:
                continue
            start_idx, end_idx = rng
            if start_idx >= end_idx:
                continue

            # T-Pose 中的骨骼中心
            tpose_center = bone.mesh_center
            # 当前世界矩阵中的骨骼中心
            current_center = bone.world_matrix[:3, 3]

            # 计算旋转差异
            R_current = bone.world_matrix[:3, :3]
            R_tpose = bone.t_pose_matrix[:3, :3]

            # 对每个顶点: 先减去tpose中心，旋转到新姿态，再加新中心
            verts_slice = result[start_idx:end_idx]
            centered = verts_slice - tpose_center
            rotated = (R_current @ centered.T).T
            result[start_idx:end_idx] = rotated + current_center

        return result

    def print_debug_info(self):
        """输出关节调试信息"""
        print("\n" + "=" * 70)
        print("  关节独立旋转控制器 — 调试信息")
        print("=" * 70)
        for sname in CONTROLLABLE_JOINTS:
            angles = self._joint_angles.get(sname, np.zeros(3))
            bone = self.loader.bone_by_semantic.get(sname)
            cn = JOINT_CN_LABELS.get(sname, sname)
            if bone:
                pos = bone.world_matrix[:3, 3]
                print(f"  {sname:20s} ({cn:8s})  "
                      f"旋转=[{angles[0]:+7.1f}, {angles[1]:+7.1f}, {angles[2]:+7.1f}]°  "
                      f"位置=[{pos[0]:+.4f}, {pos[1]:+.4f}, {pos[2]:+.4f}]")
            else:
                print(f"  {sname:20s} ({cn:8s})  "
                      f"旋转=[{angles[0]:+7.1f}, {angles[1]:+7.1f}, {angles[2]:+7.1f}]°  "
                      f"(骨骼未找到)")
        print("=" * 70)
