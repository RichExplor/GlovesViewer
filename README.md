# GlovesViewer
**用于可视化和调试Gloves数据手套实时数据的上位机。**

## 1. 功能特性
* 通过BLE低功耗蓝牙连接数据手套，实时接收5指弯曲度数据
* 3D手部骨骼模型实时渲染，直观反映真实手部动作
* 5指弯曲度实时时序曲线显示
* 支持模拟数据模式（正弦波/手动控制），无需硬件即可调试
* 数据录制（CSV/JSON格式）

## 2. 运行环境
* Python=3.13
* numpy
* PyQt5
* pyqtgraph
* PyOpenGL
* bleak

### 2.1 创建conda虚拟环境
```bash
conda create -y -n gloves_env python=3.13
```

### 2.2 安装第三方库
```bash
conda activate gloves_env
pip install -r requirements.txt
```

## 3. 运行方式
- [**Ubuntu**] `python main.py`
- [**Windows**] `点击exe可执行文件`

## 4. BLE通信协议
| 字段 | 偏移 | 长度 | 说明 |
|------|------|------|------|
| 帧头 | 0-1 | 2B | 固定 0x4E 0x4A |
| 拇指 | 2-3 | 2B | uint16 LE, 单位0.1° |
| 食指 | 4-5 | 2B | uint16 LE, 单位0.1° |
| 中指 | 6-7 | 2B | uint16 LE, 单位0.1° |
| 无名指 | 8-9 | 2B | uint16 LE, 单位0.1° |
| 小指 | 10-11 | 2B | uint16 LE, 单位0.1° |
| CRC16 | 12-13 | 2B | CRC16-CCITT |

GATT服务UUID: `00004e4a-0000-1000-8000-00805f9b34fb`
数据特征UUID: `00004e4a-0001-1000-8000-00805f9b34fb`

## 5. 跨平台打包exe可执行文件
**基于Github Actions的CI/CD流水线自动打包生成Windows可执行文件。**

### 5.1 配置CI/CD yml文件
```bash
mkdir -p .github/workflows
cd .github/workflows
touch build.yml
```

### 5.2 推送远端
```bash
git add .
git commit -m "feat: gloves viewer v1.0"
git push origin main
git tag v1.0.0
git push origin v1.0.0
```
