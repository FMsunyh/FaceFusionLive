
import threading
import socket
from modules.logger import logger
import time

class RTMPMonitorThread(threading.Thread):
    def __init__(self, rtmp_url, stop_event, interval=5):
        super().__init__()
        self.rtmp_url = rtmp_url
        self.interval = interval
        self._stop_event = stop_event
        self.network_available = True

    def run(self):
        while not self._stop_event.is_set():
            self.network_available = self.is_rtmp_available(self.rtmp_url)
            if not self.network_available:
                logger.warning(f"RTMP server is unavailable: {self.rtmp_url}")
            else:
                logger.info(f"RTMP server is available: {self.rtmp_url}")

            time.sleep(self.interval)

    def is_rtmp_available(self, rtmp_url):
        """检查 RTMP 服务器是否可用"""
        try:
            # 从 RTMP URL 中提取主机和端口
            host, port = self.parse_rtmp_url(rtmp_url)
            socket.setdefaulttimeout(3)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            sock.close()
            return True
        except socket.error as e:
            logger.error(f"RTMP connection failed: {e}")
            return False

    def parse_rtmp_url(self, rtmp_url):
        """从 RTMP URL 中解析出主机和端口"""
        url_parts = rtmp_url.replace("rtmp://", "").split("/")
        host_port = url_parts[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 1935  # 默认端口为 1935
        return host, port

    def stop(self):
        logger.info(
            f"Stop RTMPMonitorThread: "
            f"Thread Name: {self.name}, "
        )
        self._stop_event.set()

