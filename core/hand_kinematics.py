# -*- coding: utf-8 -*-
"""
手部正运动学模型 — 根据5指弯曲度计算所有关节3D坐标

骨骼层级:
  手掌 -> 掌骨 -> 近节指骨 -> 中节指骨(拇指无) -> 远节指骨

每根手指只有1个弯曲度自由度(0°~180°)，按比例分配到各关节:
  拇指(2关节): 掌指50% + 指间50%
  其余四指(3关节): 掌指40% + 近指间35% + 远指间25%

关节最大弯曲限制:
  掌指关节(MCP): 90°
  近指间关节(PIP): 100°
  远指间关节(DIP): 80°

坐标系: X=横向(拇指侧为正), Y=手指伸展方向(向上), Z=手背方向
弯曲方向: 手指向掌心弯曲 = 绕局部X轴负方向旋转
"""
import numpy as np
from math import sin, cos, radians


FINGER_KEYS = ['thumb', 'index', 'middle', 'ring', 'pinky']

# 骨骼长度参数（相对单位）
BONE_LENGTHS = {
    'thumb':  [1.0, 1.2, 1.0],                          # 掌骨, 近节, 远节
    'index':  [1.6, 1.6, 1.2, 0.9],                     # 掌骨, 近节, 中节, 远节
    'middle': [1.6, 1.8, 1.4, 1.0],
    'ring':   [1.6, 1.7, 1.3, 0.9],
    'pinky':  [1.4, 1.3, 1.0, 0.8],
}

# 弯曲度分配比例
BEND_RATIOS = {
    'thumb':  [0.50, 0.50],                              # MCP, IP
    'index':  [0.40, 0.35, 0.25],                        # MCP, PIP, DIP
    'middle': [0.40, 0.35, 0.25],
    'ring':   [0.40, 0.35, 0.25],
    'pinky':  [0.40, 0.35, 0.25],
}

# 关节最大弯曲角度限制（度）
JOINT_MAX_ANGLE = {
    'thumb':  [90.0, 100.0],
    'index':  [90.0, 100.0, 80.0],
    'middle': [90.0, 100.0, 80.0],
    'ring':   [90.0, 100.0, 80.0],
    'pinky':  [90.0, 100.0, 80.0],
}

# 手指在手掌上的起始位置（X偏移, Y偏移, Z偏移）
# 坐标系: X=横向(拇指侧为正), Y=手指伸展方向, Z=手背方向
FINGER_BASES = {
    'thumb':  (2.0, 0.0, 0.5),     # 拇指在手掌侧面偏下
    'index':  (1.2, 0.0, 0.0),
    'middle': (0.4, 0.0, 0.0),
    'ring':   (-0.4, 0.0, 0.0),
    'pinky':  (-1.2, 0.0, 0.0),
}

# 拇指特殊起始方向（与手掌平面成约40°角，向外展开）
THUMB_BASE_ANGLE_X = 30.0  # 拇指初始X方向偏转角度（外展）


class HandKinematics:
    """手部正运动学计算引擎"""

    def __init__(self):
        self.palm_center = np.array([0.0, 0.0, 0.0])

    def compute(self, angles: dict) -> dict:
        """
        根据5指弯曲度计算所有关节3D坐标

        Args:
            angles: {thumb: 45.0, index: 30.0, middle: 60.0, ring: 20.0, pinky: 10.0}
                    角度值单位为度, 范围0~180

        Returns:
            {
                'joints': {finger_name: [np.array, ...]},   # 各关节坐标列表
                'bones':  {finger_name: [(start, end), ...]} # 骨骼线段端点对
            }
        """
        joints = {}
        bones = {}

        for finger in FINGER_KEYS:
            bend_angle = max(0.0, min(180.0, angles.get(finger, 0.0)))
            ratios = BEND_RATIOS[finger]
            max_angles = JOINT_MAX_ANGLE[finger]
            lengths = BONE_LENGTHS[finger]
            base = FINGER_BASES[finger]

            # 计算各关节实际弯曲角度
            joint_angles = []
            for i, (ratio, max_ang) in enumerate(zip(ratios, max_angles)):
                joint_angle = min(bend_angle * ratio, max_ang)
                joint_angles.append(joint_angle)

            # 计算关节坐标
            finger_joints = self._compute_finger_joints(
                finger, base, lengths, joint_angles
            )
            joints[finger] = finger_joints

            # 计算骨骼线段
            finger_bones = []
            for i in range(len(finger_joints) - 1):
                finger_bones.append((finger_joints[i].copy(), finger_joints[i + 1].copy()))
            bones[finger] = finger_bones

        return {'joints': joints, 'bones': bones}

    def _compute_finger_joints(self, finger, base, lengths, joint_angles):
        """
        计算单根手指的所有关节坐标

        使用累积旋转方式: 每个关节在前一关节方向基础上旋转
        弯曲方向为绕局部X轴旋转(手指向掌心弯曲，即Z负方向)

        关键逻辑:
          - 第0段(掌骨): 从根部出发，方向为初始方向，无弯曲
          - 第1段(近节): 在掌骨末端施加第0个关节弯曲角
          - 第2段(中节): 在近节末端施加第1个关节弯曲角
          - 第3段(远节): 在中节末端施加第2个关节弯曲角
        """
        # 起始位置
        x0, y0, z0 = base
        current_pos = np.array([x0, y0, z0], dtype=float)
        joint_positions = [current_pos.copy()]

        # 当前方向向量（初始指向Y正方向，即手指伸展方向）
        direction = np.array([0.0, 1.0, 0.0], dtype=float)

        # 拇指特殊处理: 初始方向有X轴偏转（外展）
        if finger == 'thumb':
            rx = radians(THUMB_BASE_ANGLE_X)
            rot_x = np.array([
                [1, 0,      0],
                [0, cos(rx), -sin(rx)],
                [0, sin(rx),  cos(rx)]
            ])
            direction = rot_x @ direction

        # 逐段计算
        for i, (length, angle) in enumerate(zip(lengths, joint_angles)):
            # 先沿当前方向延伸当前骨骼段
            next_pos = current_pos + direction * length
            joint_positions.append(next_pos.copy())
            current_pos = next_pos

            # 在当前骨骼末端施加弯曲（为下一段准备方向）
            if i < len(joint_angles):
                # 绕局部X轴旋转（手指向掌心弯曲 = Z负方向）
                rx = radians(angle)
                rot_x = np.array([
                    [1, 0,      0],
                    [0, cos(rx), -sin(rx)],
                    [0, sin(rx),  cos(rx)]
                ])
                direction = rot_x @ direction
                # 归一化方向向量
                norm = np.linalg.norm(direction)
                if norm > 1e-6:
                    direction = direction / norm

        return joint_positions

    def get_palm_outline(self):
        """
        生成手掌轮廓线段用于3D渲染

        Returns:
            list of (start_pos, end_pos) 线段对
        """
        # 手掌简化为5个手指根部连接的梯形
        bases = [np.array(FINGER_BASES[f]) for f in FINGER_KEYS]
        palm_lines = []
        for i in range(len(bases) - 1):
            # 跳过拇指到食指的连接（拇指位置特殊）
            if i == 0:
                continue
            palm_lines.append((bases[i], bases[i + 1]))

        # 拇指到食指的弧形连接（简化为直线）
        thumb_base = np.array(FINGER_BASES['thumb'])
        index_base = np.array(FINGER_BASES['index'])
        palm_lines.append((thumb_base, index_base))

        # 手掌底部
        palm_bottom_left = np.array([-1.5, -1.0, 0.0])
        palm_bottom_right = np.array([1.5, -1.0, 0.0])
        palm_lines.append((bases[-1], palm_bottom_left))   # 小指到底部
        palm_lines.append((bases[1], palm_bottom_right))    # 食指到底部
        palm_lines.append((palm_bottom_left, palm_bottom_right))  # 底部横线

        return palm_lines
