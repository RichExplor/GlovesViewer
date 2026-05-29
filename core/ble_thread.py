# -*- coding: utf-8 -*-
"""
BLE通信线程 — 基于bleak的异步BLE设备扫描/连接/通知管理

架构要点:
  - 使用QThread承载asyncio事件循环
  - bleak所有异步操作在独立事件循环中执行
  - 通过pyqtSignal将数据安全传递到主线程
"""
import asyncio
import struct
from PyQt5 import QtCore

from core.frame_parser import FrameParser, FINGER_KEYS

# BLE GATT 服务和特征UUID
GLOVE_SERVICE_UUID = "00004e4a-0000-1000-8000-00805f9b34fb"
GLOVE_CHAR_UUID    = "00004e4a-0001-1000-8000-00805f9b34fb"


class BLEWorker(QtCore.QObject):
    """在QThread中运行的BLE异步工作对象"""
    device_found = QtCore.pyqtSignal(str, str)       # name, address
    data_received = QtCore.pyqtSignal(dict)           # {thumb, index, middle, ring, pinky}
    log_received = QtCore.pyqtSignal(str)             # 日志消息
    connection_changed = QtCore.pyqtSignal(bool)      # 连接状态
    scan_finished = QtCore.pyqtSignal()               # 扫描结束

    def __init__(self):
        super().__init__()
        self._running = True
        self._loop = None
        self._client = None
        self._connected = False
        self.parser = FrameParser()
        self._scan_event = None
        self._connect_address = None
        self._command = None  # 'scan', 'connect', 'disconnect'

    def run(self):
        """在QThread中启动asyncio事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_loop())
        except Exception as e:
            self.log_received.emit(f"BLE事件循环异常: {str(e)}")
        finally:
            self._loop.close()

    async def _main_loop(self):
        """主事件循环，等待并执行命令"""
        while self._running:
            if self._command == 'scan':
                self._command = None
                await self._do_scan()
            elif self._command == 'connect':
                self._command = None
                await self._do_connect()
            elif self._command == 'disconnect':
                self._command = None
                await self._do_disconnect()
            else:
                await asyncio.sleep(0.05)

    # ==================== 扫描 ====================
    async def _do_scan(self):
        """扫描BLE设备"""
        try:
            from bleak import BleakScanner
            self.log_received.emit("正在扫描BLE设备...")
            devices = await BleakScanner.discover(timeout=5.0)
            for d in devices:
                name = d.name or "Unknown"
                self.device_found.emit(name, d.address)
            self.log_received.emit(f"扫描完成，发现 {len(devices)} 个设备")
        except Exception as e:
            self.log_received.emit(f"扫描失败: {str(e)}")
        finally:
            self.scan_finished.emit()

    # ==================== 连接 ====================
    async def _do_connect(self):
        """连接到指定BLE设备并订阅通知"""
        if not self._connect_address:
            self.log_received.emit("未指定设备地址")
            return

        try:
            from bleak import BleakClient
            self.log_received.emit(f"正在连接 {self._connect_address}...")
            self._client = BleakClient(self._connect_address)
            await self._client.connect()
            self._connected = True
            self.connection_changed.emit(True)
            self.log_received.emit("BLE连接成功")

            # 订阅特征通知
            await self._client.start_notify(GLOVE_CHAR_UUID, self._on_notification)
            self.log_received.emit("已订阅数据通知")

            # 保持连接，处理数据
            while self._connected and self._running:
                await asyncio.sleep(0.01)

        except Exception as e:
            self.log_received.emit(f"连接失败: {str(e)}")
            self._connected = False
            self.connection_changed.emit(False)

    # ==================== 断开 ====================
    async def _do_disconnect(self):
        """断开BLE连接"""
        try:
            if self._client and self._connected:
                await self._client.stop_notify(GLOVE_CHAR_UUID)
                await self._client.disconnect()
            self._connected = False
            self.connection_changed.emit(False)
            self.log_received.emit("BLE已断开连接")
        except Exception as e:
            self.log_received.emit(f"断开连接异常: {str(e)}")
            self._connected = False
            self.connection_changed.emit(False)

    # ==================== 通知回调 ====================
    def _on_notification(self, sender, data: bytearray):
        """BLE特征通知回调，在asyncio线程中执行"""
        packets = self.parser.feed(bytes(data))
        for angles in packets:
            self.data_received.emit(angles)

    # ==================== 外部命令接口 ====================
    def request_scan(self):
        self._command = 'scan'

    def request_connect(self, address: str):
        self._connect_address = address
        self._command = 'connect'

    def request_disconnect(self):
        self._command = 'disconnect'

    def stop(self):
        self._running = False
        self._connected = False
        self._command = 'disconnect'


class BLEThread(QtCore.QThread):
    """BLE通信管理线程"""
    device_found = QtCore.pyqtSignal(str, str)
    data_received = QtCore.pyqtSignal(dict)
    log_received = QtCore.pyqtSignal(str)
    connection_changed = QtCore.pyqtSignal(bool)
    scan_finished = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = BLEWorker()
        self.worker.moveToThread(self)
        self.started.connect(self.worker.run)

        # 转发worker信号
        self.worker.device_found.connect(self.device_found)
        self.worker.data_received.connect(self.data_received)
        self.worker.log_received.connect(self.log_received)
        self.worker.connection_changed.connect(self.connection_changed)
        self.worker.scan_finished.connect(self.scan_finished)

    def scan_devices(self):
        """请求扫描BLE设备"""
        self.worker.request_scan()

    def connect_device(self, address: str):
        """请求连接指定设备"""
        self.worker.request_connect(address)

    def disconnect_device(self):
        """请求断开连接"""
        self.worker.request_disconnect()

    @property
    def packet_count(self):
        return self.worker.parser.packet_count

    @property
    def drop_count(self):
        return self.worker.parser.drop_count

    def stop(self):
        """停止线程"""
        self.worker.stop()
        self.wait(3000)
