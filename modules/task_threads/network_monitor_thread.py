

import threading
import socket
from modules.logger import logger
import time

class NetworkMonitorThread(threading.Thread):
    def __init__(self, stop_event, interval=5, check_host="8.8.8.8"):
        super().__init__()
        self.interval = interval
        self.check_host = check_host
        self._stop_event = stop_event
        self.network_available = True

        self.name = self.__class__.__name__
        
    def run(self):
        while not self._stop_event.is_set():
            self.network_available = self.is_network_available()
            if not self.network_available:
                logger.warning("网络不可用，等待恢复...")
            time.sleep(self.interval)

    def is_network_available(self):
        """检查网络是否可用"""
        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((self.check_host, 53))
            return True
        except socket.error:
            return False

    def stop(self):
        logger.info(
            f"Stop NetworkMonitorThread: "
            f"Thread Name: {self.name}, "
        )
        self._stop_event.set()
