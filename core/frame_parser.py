# -*- coding: utf-8 -*-
"""
数据帧解析器 — 处理串口推送的原始字节流

帧格式 (8字节):
[0xFA][Thumb][Index][Middle][Ring][Pinky][Palm][0xAA]

帧头: 0xFA
帧尾: 0xAA
数据: 6字节，分别为拇指、食指、中指、无名指、小指、手背
角度值: 每字节1个原始角度值(0~180)，单位为度

示例: FA 08 10 28 00 0C 00 AA
  拇指=8°, 食指=16°, 中指=40°, 无名指=0°, 小指=12°, 手背=0°
"""

# 帧定义
FRAME_HEADER = 0xFA
FRAME_TAIL = 0xAA
FRAME_LEN = 8  # 帧头(1) + 数据(6) + 帧尾(1)

# 5指键名 — 用于3D手部模型渲染
FINGER_KEYS = ['thumb', 'index', 'middle', 'ring', 'pinky']

# 全部6通道键名 — 包含手背(palm)，用于数据解析和UI展示
ALL_KEYS = ['thumb', 'index', 'middle', 'ring', 'pinky', 'palm']


class FrameParser:
    """串口数据帧解析器，处理粘包/半包"""

    def __init__(self):
        self.buffer = bytearray()
        self.packet_count = 0
        self.drop_count = 0

    def feed(self, raw_bytes: bytes) -> list:
        """
        输入原始字节流，输出解析后的数据包列表

        Returns:
            list[dict]: 每个元素为 {thumb: float, index: float, ..., palm: float} 单位为度
        """
        self.buffer.extend(raw_bytes)
        results = []

        while len(self.buffer) >= FRAME_LEN:
            # 搜索帧头
            header_pos = self._find_header()
            if header_pos < 0:
                # 没有找到帧头，清空缓冲区
                self.buffer.clear()
                break

            # 丢弃帧头之前的垃圾数据
            if header_pos > 0:
                del self.buffer[:header_pos]

            # 检查是否有完整帧
            if len(self.buffer) < FRAME_LEN:
                break

            frame = bytes(self.buffer[:FRAME_LEN])

            # 验证帧尾
            if frame[7] != FRAME_TAIL:
                # 帧尾不匹配，丢弃1字节重新同步
                self.drop_count += 1
                del self.buffer[0]
                continue

            # 解析6个角度值
            angles = {}
            for i, key in enumerate(ALL_KEYS):
                angles[key] = float(frame[i + 1])  # 帧头后第1~6字节

            results.append(angles)
            self.packet_count += 1
            del self.buffer[:FRAME_LEN]

        return results

    def _find_header(self) -> int:
        """在缓冲区中搜索帧头位置"""
        for i in range(len(self.buffer)):
            if self.buffer[i] == FRAME_HEADER:
                return i
        return -1

    def reset(self):
        """重置解析器状态"""
        self.buffer.clear()
        self.packet_count = 0
        self.drop_count = 0
