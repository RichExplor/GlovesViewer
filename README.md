# GlovesViewer
**用于可视化和调试Gloves数据手套实时数据的上位机。**

## 1. 功能特性
* 通过BLE低功耗蓝牙连接数据手套(串口通讯)，实时接收5指弯曲度数据
* **GLB手部骨骼模型渲染** — 加载 `bones_of_the_hand.glb`，3D视窗显示手部骨骼网格+骨架
* **每个手指关节可单独调节旋转角度** — 3轴(弯曲/外展/扭转)滑块实时控制
* **T-Pose 重置功能** — 一键恢复到初始姿态
* **骨骼调试信息输出** — 控制台打印骨骼层级树和关节变换矩阵
* 5指弯曲度实时时序曲线显示
* 支持模拟数据模式（正弦波/手动控制），无需硬件即可调试
* 数据录制（CSV/JSON格式）

## 2. 运行环境
* Python=3.13
* numpy
* PyQt5
* pyqtgraph
* PyOpenGL
* pyserial
* trimesh (GLB模型加载)
* bleak (BLE支持)

### 2.1 创建conda虚拟环境
```bash
conda create -y -n gloves_env python=3.13
```

### 2.2 安装第三方库
```bash
conda activate gloves_env
pip install -r requirements.txt
```

> **注意**: `trimesh` 是GLB模型加载所必需的依赖，用于解析手部骨骼 `.glb` 文件。

## 3. 运行方式
- [**Ubuntu**] `python main.py`
- [**指定GLB文件**] `python main.py --glb /path/to/model.glb`
- [**Windows**] `点击exe可执行文件`

程序启动后会自动加载 `model/bones_of_the_hand.glb` 手部骨骼模型。  
右侧面板「🖐️ 关节控制」Tab 中，每个手指的各关节均可通过 3 轴滑块独立控制旋转角度。

### 3.1 关节控制说明
| 旋转轴 | 含义 | 默认范围 |
|--------|------|---------|
| X轴 (红色) | 弯曲/伸展 | -90° ~ +90° |
| Y轴 (绿色) | 外展/内收 | -45° ~ +45° |
| Z轴 (蓝色) | 扭转 | -45° ~ +45° |

- 🔄 **T-Pose 重置** — 将所有关节角度归零，恢复到模型初始姿态
- 🐛 **调试信息** — 在控制台输出完整的骨骼层级树和关节变换信息

## 4. 串口通信协议
8 bytes: fa081028000c00aa
| 字段 | 偏移 | 长度 | 说明 |
|------|------|------|------|
| 帧头 | 0 | 1B | 固定 0xfa |
| 拇指 | 1 | 1B | 0x, 单位° |
| 食指 | 2 | 1B | 0x, 单位° |
| 中指 | 3 | 1B | 0x, 单位° |
| 无名 | 4 | 1B | 0x, 单位° |
| 小指 | 5 | 1B | 0x, 单位° |
| 手背 | 6 | 1B | 0x, 单位° |
| 帧尾 | 7 | 1B | 固定 0xaa |

## 5. 骨骼命名映射
原始 GLB 骨骼名 → 简化语义名:
| 原始名 | 语义名 | 中文 |
|--------|--------|------|
| Retopo_Ulna | Wrist_Root | 腕根 |
| Retopo_Hamate | Carpal_Hamate | 钩骨 |
| Retopo_Lunate | Carpal_Lunate | 月骨 |
| Retopo_Pisiform | Carpal_Pisiform | 豌豆骨 |
| Retopo_Scaphoid | Carpal_Scaphoid | 舟骨 |
| Retopo_Trapezium | Carpal_Trapezium | 大多角骨 |
| Retopo_Trapezoid | Carpal_Trapezoid | 小多角骨 |
| Retopo_Triquetral | Carpal_Triquetral | 三角骨 |
| Retopo_1st Metacarpal | Thumb_Meta | 拇掌骨 |
| Retopo_2nd Metacarpal | Index_Meta | 食掌骨 |
| Retopo_3rd Metacarpal | Middle_Meta | 中掌骨 |
| Retopo_4th Metacarpal | Ring_Meta | 无名掌骨 |
| Retopo_5th Metacarpal | Pinky_Meta | 小掌骨 |
| Retopo_1st Proximal Phalanx | Thumb_Prox | 拇近节 |
| Retopo_2nd Proximal Phalanx | Index_Prox | 食近节 |
| Retopo_3rd Proximal Phalanx | Middle_Prox | 中近节 |
| Retopo_4th Proximal Phalanx | Ring_Prox | 无名近节 |
| Retopo_5th Proximal Phalanx | Pinky_Prox | 小近节 |
| Retopo_2nd Middle Phalanx | Index_Mid | 食中节 |
| Retopo_3rd Middle Phalanx | Middle_Mid | 中中节 |
| Retopo_4th Middle Phalanx | Ring_Mid | 无名中节 |
| Retopo_5th Middle Phalanx | Pinky_Mid | 小中节 |
| Retopo_1st Distal Phalanx | Thumb_Dist | 拇远节 |
| Retopo_2nd Distal Phalanx | Index_Dist | 食远节 |
| Retopo_3rd Distal Phalanx | Middle_Dist | 中远节 |
| Retopo_4th Distal Phalanx | Ring_Dist | 无名远节 |
| Retopo_5th Distal Phalanx | Pinky_Dist | 小远节 |

#     "Retopo_Radius":                  "Carpal_Radius",
#     "Retopo_Ulna":                    "Wrist_Root",
#     "Retopo_Hamate":                  "Carpal_Hamate",
#     "Retopo_Lunate":                  "Carpal_Lunate",
#     "Retopo_Pisiform":                "Carpal_Pisiform",
#     "Retopo_Scaphoid":                "Carpal_Scaphoid",
#     "Retopo_Trapezium":               "Carpal_Trapezium",
#     "Retopo_Trapezoid":               "Carpal_Trapezoid",
#     "Retopo_Triquetral":              "Carpal_Triquetral",
#     "Retopo_Capitate":                "Carpal_Capitate",
#     "Retopo_1st Metacarpal_5":          "Thumb_Meta",
#     "Retopo_2nd Metacarpal_9":          "Index_Meta",
#     "Retopo_3rd Metacarpal_13":          "Middle_Meta",
#     "Retopo_4th Metacarpal_17":          "Ring_Meta",
#     "Retopo_5th Metacarpal_21":          "Pinky_Meta",
#     "Retopo_1st Proximal Phalanx_7":    "Thumb_Prox",
#     "Retopo_2nd Proximal Phalanx_11":    "Index_Prox",
#     "Retopo_3rd Proximal Phalanx_15":    "Middle_Prox",
#     "Retopo_4th Proximal Phalanx_19":    "Ring_Prox",
#     "Retopo_5th Proximal Phalanx_22":    "Pinky_Prox",
#     # Middle Phalanx 编号偏移修正:
#     # GLB "1st Middle" 实际mesh位于食指, 非拇指(拇指无中节)
#     "Retopo_1st Middle Plalanx_6":      "Index_Mid",
#     "Retopo_2nd Middle Plalanx_10":      "Middle_Mid",
#     "Retopo_3rd Middle Plalanx_14":      "Ring_Mid",
#     "Retopo_4th Middle Plalanx_18":      "Pinky_Mid",
#     # 注意: 不存在 "Retopo_5th Middle Phalanx"
#     "Retopo_1st Distal Plalanx_4":      "Thumb_Dist",
#     "Retopo_2nd Distal Plalanx_8":      "Index_Dist",
#     "Retopo_3rd Distal Plalanx_12":      "Middle_Dist",
#     "Retopo_4th Distal Plalanx_16":      "Ring_Dist",
#     "Retopo_5th Distal Plalanx_20":      "Pinky_Dist",

=== 所有骨骼 (按加载顺序) ===
  Pinky_Prox           (小近节     )  raw=Retopo_5th Proximal Phalanx_22          pos=[-0.4591, +0.2624, -0.1014]
  Pinky_Meta           (小掌骨     )  raw=Retopo_5th Metacarpal_21                pos=[-0.3477, -0.0454, -0.0827]
  Pinky_Dist           (小远节     )  raw=Retopo_5th Distal Plalanx_20            pos=[-0.5654, +0.5885, -0.0079]
  Ring_Prox            (无名近节    )  raw=Retopo_4th Proximal Phalanx_19          pos=[-0.2780, +0.3592, -0.1209]
  Pinky_Mid            (小中节      )  raw=Retopo_4th Middle Plalanx_18            pos=[-0.5394, +0.4597, -0.0745]
  Ring_Meta            (无名掌骨    )  raw=Retopo_4th Metacarpal_17                pos=[-0.2297, -0.0292, -0.1157]
  Ring_Dist            (无名远节    )  raw=Retopo_4th Distal Plalanx_16            pos=[-0.3560, +0.8489, -0.0402]
  Middle_Prox          (中近节     )  raw=Retopo_3rd Proximal Phalanx_15          pos=[-0.1127, +0.4010, -0.1197]
  Ring_Mid             (无名中节    )  raw=Retopo_3rd Middle Plalanx_14            pos=[-0.3173, +0.6510, -0.0869]
  Middle_Meta          (中掌骨     )  raw=Retopo_3rd Metacarpal_13                pos=[-0.1083, -0.0341, -0.1167]
  Middle_Dist          (中远节     )  raw=Retopo_3rd Distal Plalanx_12            pos=[-0.1919, +0.9204, +0.0266]
  Index_Prox           (食近节     )  raw=Retopo_2nd Proximal Phalanx_11          pos=[+0.0665, +0.3848, -0.0808]
  Middle_Mid           (中中节     )  raw=Retopo_2nd Middle Plalanx_10            pos=[-0.1432, +0.7251, -0.0406]
  Index_Meta           (食掌骨     )  raw=Retopo_2nd Metacarpal_9                 pos=[+0.0248, -0.0433, -0.0786]
  Index_Dist           (食远节     )  raw=Retopo_2nd Distal Plalanx_8             pos=[+0.0137, +0.8116, +0.0499]
  Thumb_Prox           (拇近节     )  raw=Retopo_1st Proximal Phalanx_7           pos=[+0.2703, +0.0922, +0.1108]
  Index_Mid            (食中节     )  raw=Retopo_1st Middle Plalanx_6             pos=[+0.0445, +0.6504, -0.0126]
  Thumb_Meta           (拇掌骨     )  raw=Retopo_1st Metacarpal_5                 pos=[+0.1505, -0.1562, +0.0922]
  Thumb_Dist           (拇远节     )  raw=Retopo_1st Distal Plalanx_4             pos=[+0.3977, +0.2754, +0.1193]

=== 骨骼层级树 ===
Pinky_Meta  [-0.3477, -0.0454, -0.0827]
  └─ Pinky_Prox  [-0.4591, +0.2624, -0.1014]
    └─ Pinky_Dist  [-0.5654, +0.5885, -0.0079]

=== 关键检查 ===
  Thumb_Mid 存在: False
  Pinky_Mid 存在: True

=== 各手指骨骼链 ===
  thumb  : Thumb_Meta[+0.150,-0.156,+0.092] -> Thumb_Prox[+0.270,+0.092,+0.111] -> Thumb_Mid(缺失) -> Thumb_Dist[+0.398,+0.275,+0.119]
  index  : Index_Meta[+0.025,-0.043,-0.079] -> Index_Prox[+0.067,+0.385,-0.081] -> Index_Mid[+0.044,+0.650,-0.013] -> Index_Dist[+0.014,+0.812,+0.050]
  middle : Middle_Meta[-0.108,-0.034,-0.117] -> Middle_Prox[-0.113,+0.401,-0.120] -> Middle_Mid[-0.143,+0.725,-0.041] -> Middle_Dist[-0.192,+0.920,+0.027]
  ring   : Ring_Meta[-0.230,-0.029,-0.116] -> Ring_Prox[-0.278,+0.359,-0.121] -> Ring_Mid[-0.317,+0.651,-0.087] -> Ring_Dist[-0.356,+0.849,-0.040]
  pinky  : Pinky_Meta[-0.348,-0.045,-0.083] -> Pinky_Prox[-0.459,+0.262,-0.101] -> Pinky_Mid[-0.539,+0.460,-0.075] -> Pinky_Dist[-0.565,+0.589,-0.008]

## 6. 跨平台打包exe可执行文件
**基于Github Actions的CI/CD流水线自动打包生成Windows可执行文件。**

### 6.1 配置CI/CD yml文件
```bash
mkdir -p .github/workflows
cd .github/workflows
touch build.yml
```

### 6.2 推送远端
```bash
git add .
git commit -m "feat: gloves viewer v2.0 - GLB hand model"
git push origin main
git tag v2.0.0
git push origin v2.0.0
```
