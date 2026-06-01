# -*- coding: utf-8 -*-
"""
串口通信线程 — 基于pyserial的串口数据接收与帧解析

架构要点:
- 使用QThread承载串口读取循环
- 通过FrameParser处理粘包/半包，解析手套数据帧
- 帧格式: [0xFA][Thumb][Index][Middle][Ring][Pinky][Palm][0xAA]
- 通过pyqtSignal将解析后的角度数据安全传递到主线程
"""
import time
import serial
import serial.tools.list_ports
from PyQt5 import QtCore

from core.frame_parser import FrameParser, ALL_KEYS


class GloveSerialThread(QtCore.QThread):
    """数据手套串口通信线程"""
    data_received = QtCore.pyqtSignal(dict)   # {thumb, index, middle, ring, pinky, palm}
    log_received = QtCore.pyqtSignal(str)     # 日志消息
    connection_changed = QtCore.pyqtSignal(bool)  # 连接状态

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_port = None
        self._running = False
        self._connected = False
        self.parser = FrameParser()

    @property
    def is_connected(self):
        return self._connected

    @property
    def packet_count(self):
        return self.parser.packet_count

    @property
    def drop_count(self):
        return self.parser.drop_count

    @staticmethod
    def list_available_ports():
        """列出所有可用串口"""
        ports = []
        for p in serial.tools.list_ports.comports():
            ports.append((p.device, p.description))
        return ports

    def connect_serial(self, port: str, baudrate: int = 115200) -> bool:
        """
        连接串口并启动数据接收线程

        Args:
            port: 串口设备路径，如 '/dev/ttyUSB0' 或 'COM3'
            baudrate: 波特率，默认115200

        Returns:
            bool: 连接是否成功
        """
        if self._connected:
            self.log_received.emit("已有活跃连接，请先断开")
            return False

        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.01,  # 短超时，保证线程响应性
            )
            self._running = True
            self._connected = True
            self.parser.reset()
            self.start()
            self.connection_changed.emit(True)
            self.log_received.emit(f"串口已连接: {port} @ {baudrate}")
            return True
        except Exception as e:
            self.log_received.emit(f"串口连接失败: {str(e)}")
            self._connected = False
            self.connection_changed.emit(False)
            return False

    def disconnect_serial(self):
        """断开串口连接"""
        self._running = False
        if self.isRunning():
            self.wait(3000)
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self._connected = False
        self.connection_changed.emit(False)
        self.log_received.emit("串口已断开连接")

    def run(self):
        """线程主循环 — 持续读取串口数据并解析"""
        rx_buffer = bytearray()

        while self._running:
            try:
                if self.serial_port and self.serial_port.is_open:
                    if self.serial_port.in_waiting > 0:
                        new_data = self.serial_port.read(self.serial_port.in_waiting)
                        rx_buffer.extend(new_data)
                        # print(f"Received {len(new_data)} bytes: {new_data.hex()}")  # 调试输出

                        # 使用FrameParser解析数据帧
                        packets = self.parser.feed(bytes(rx_buffer))
                        rx_buffer.clear()

                        for angles in packets:
                            self.data_received.emit(angles)
                    else:
                        # 无数据时短暂休眠，避免CPU空转
                        time.sleep(0.001)
                else:
                    # 串口未打开，退出循环
                    break
            except serial.SerialException as e:
                self.log_received.emit(f"串口读取异常: {str(e)}")
                break
            except Exception as e:
                self.log_received.emit(f"数据处理异常: {str(e)}")
                continue

        # 线程退出时清理
        self._connected = False
        self.connection_changed.emit(False)
