# GlovesViewer
**用于可视化和调试Gloves数据手套实时数据的上位机。**

## 1. 功能特性
* 通过BLE低功耗蓝牙连接数据手套(串口通讯)，实时接收5指弯曲度数据
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
