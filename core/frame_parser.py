# -*- coding: utf-8 -*-
"""
数据帧解析器 — 处理BLE通知推送的原始字节流
帧格式 (14字节):
  [0x4E][0x4A][Thumb_L][Thumb_H][Index_L][Index_H]
  [Middle_L][Middle_H][Ring_L][Ring_H][Pinky_L][Pinky_H]
  [CRC_L][CRC_H]
角度值: uint16 LE, 单位0.1°, 范围0~1800 对应 0°~180°
"""
import struct


def crc16_ccitt(data: bytes, init: int = 0xFFFF) -> int:
    """CRC16-CCITT 校验算法"""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


FRAME_HEADER = bytes([0x4E, 0x4A])
FRAME_LEN = 14
FINGER_KEYS = ['thumb', 'index', 'middle', 'ring', 'pinky']


class FrameParser:
    """BLE数据帧解析器，处理粘包/半包"""

    def __init__(self):
        self.buffer = bytearray()
        self.packet_count = 0
        self.drop_count = 0

    def feed(self, raw_bytes: bytes) -> list:
        """
        输入原始字节流，输出解析后的数据包列表

        Returns:
            list[dict]: 每个元素为 {thumb: float, index: float, ...} 单位为度
        """
        self.buffer.extend(raw_bytes)
        results = []

        while len(self.buffer) >= FRAME_LEN:
            # 搜索帧头
            header_pos = self._find_header()
            if header_pos < 0:
                self.buffer.clear()
                break

            # 丢弃帧头之前的垃圾数据
            if header_pos > 0:
                del self.buffer[:header_pos]

            # 检查是否有完整帧
            if len(self.buffer) < FRAME_LEN:
                break

            frame = bytes(self.buffer[:FRAME_LEN])

            # CRC校验
            calc_crc = crc16_ccitt(frame[:12])
            pack_crc = struct.unpack('<H', frame[12:14])[0]

            if calc_crc == pack_crc:
                # 解包5个角度值
                raw_values = struct.unpack('<5H', frame[2:12])
                angles = {}
                for i, key in enumerate(FINGER_KEYS):
                    angles[key] = raw_values[i] / 10.0  # 0.1° -> 1°
                results.append(angles)
                self.packet_count += 1
                del self.buffer[:FRAME_LEN]
            else:
                # CRC校验失败，丢弃1字节重新同步
                self.drop_count += 1
                del self.buffer[0]

        return results

    def _find_header(self) -> int:
        """在缓冲区中搜索帧头位置"""
        for i in range(len(self.buffer) - 1):
            if self.buffer[i] == 0x4E and self.buffer[i + 1] == 0x4A:
                return i
        return -1

    def reset(self):
        """重置解析器状态"""
        self.buffer.clear()
        self.packet_count = 0
        self.drop_count = 0
