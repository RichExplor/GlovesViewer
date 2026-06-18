# -*- coding: utf-8 -*-
"""检查 GLB 模型所有原始节点，确认腕骨是否存在"""
import sys
sys.path.insert(0, '.')
import trimesh
import numpy as np

scene = trimesh.load('model/bones_of_the_hand.glb', force='scene')
graph = scene.graph

print("=== 所有节点 ===")
for n in graph.nodes:
    print(f"  {n}")

print("\n=== 所有边 (parent -> child, geometry) ===")
for edge in graph.to_edgelist():
    parent, child = edge[0], edge[1]
    data = edge[2] if len(edge) > 2 else {}
    geom = data.get('geometry', None)
    print(f"  {parent} -> {child}  geom={geom}")

print("\n=== 所有几何体 ===")
for name in scene.geometry:
    g = scene.geometry[name]
    print(f"  {name}: {len(g.vertices)} verts, {len(g.faces)} faces")
