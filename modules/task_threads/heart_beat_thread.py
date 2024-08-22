
import threading
from modules.logger import logger
import time

class HeartbeatThread(threading.Thread):
    def __init__(self, stop_event, interval=60):
        super().__init__()
        self.interval = interval
        self._stop_event = stop_event

        self.name = self.__class__.__name__      
        # Log the properties when initializing the thread
        logger.info(
            f"Initialized {self.name},"
            f"Interval: {self.interval} "
        )

    def run(self):
        while not self._stop_event.is_set():
            logger.info("Heartbeat: Program is running normally")
            time.sleep(self.interval)

    def stop(self):
        logger.info(
            f"Stop HeartbeatThread: "
            f"Thread Name: {self.name}, "
        )
        self._stop_event.set()
