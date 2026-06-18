# -*- coding: utf-8 -*-
"""验证 GLB 模型骨骼结构与映射关系（修正后）"""
import sys
sys.path.insert(0, '.')
from core.glb_loader import (
    GLBLoader, JOINT_CN_LABELS, FINGER_GROUPS, FINGER_JOINTS,
    _LOGICAL_PARENT, CONTROLLABLE_JOINTS,
)

loader = GLBLoader()
ok = loader.load('model/bones_of_the_hand.glb')
print(f"加载结果: {ok}")

print("\n=== 骨骼层级树 ===")
if loader.root_bone:
    def print_tree(bone, indent=0):
        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        pos = bone.mesh_center
        print(f"{prefix}{bone.semantic_name}  [{pos[0]:+.4f}, {pos[1]:+.4f}, {pos[2]:+.4f}]")
        for child_idx in bone.children_indices:
            if 0 <= child_idx < len(loader.bones):
                print_tree(loader.bones[child_idx], indent + 1)
    print_tree(loader.root_bone)

print("\n=== 关键检查 ===")
print(f"  Thumb_Mid 存在: {'Thumb_Mid' in loader.bone_by_semantic}  (应为 False)")
print(f"  Pinky_Mid 存在: {'Pinky_Mid' in loader.bone_by_semantic}  (应为 True)")

# 检查各手指骨骼链完整性
print("\n=== 各手指骨骼链 (FINGER_GROUPS) ===")
for finger, names in FINGER_GROUPS.items():
    chain = []
    for n in names:
        b = loader.bone_by_semantic.get(n)
        if b:
            chain.append(f"{n}[{b.mesh_center[0]:+.3f},{b.mesh_center[1]:+.3f},{b.mesh_center[2]:+.3f}]")
        else:
            chain.append(f"{n}(缺失!)")
    print(f"  {finger:7s}: " + " -> ".join(chain))

print("\n=== 可控关节 (FINGER_JOINTS) ===")
for finger, joints in FINGER_JOINTS.items():
    status = []
    for j in joints:
        status.append(f"{j}({'OK' if j in loader.bone_by_semantic else '缺失!'})")
    print(f"  {finger:7s}: " + ", ".join(status))

print("\n=== 层级父子关系验证 (_LOGICAL_PARENT) ===")
for bone in loader.bones:
    expected_parent = _LOGICAL_PARENT.get(bone.semantic_name)
    actual_parent_idx = bone.parent_index
    actual_parent = loader.bones[actual_parent_idx].semantic_name if actual_parent_idx >= 0 else None
    match = "OK" if expected_parent == actual_parent else "MISMATCH"
    if match != "OK":
        print(f"  {bone.semantic_name:16s} 期望父={expected_parent}  实际父={actual_parent}  [{match}]")
print("  (仅显示不匹配项)")

print("\n=== CONTROLLABLE_JOINTS 完整性 ===")
missing = [j for j in CONTROLLABLE_JOINTS if j not in loader.bone_by_semantic]
if missing:
    print(f"  缺失关节: {missing}")
else:
    print("  全部存在 OK")

print("\n=== JOINT_CN_LABELS 覆盖检查 ===")
for bone in loader.bones:
    if bone.semantic_name not in JOINT_CN_LABELS:
        print(f"  缺少中文标签: {bone.semantic_name}")
print("  (仅显示缺失项)")
