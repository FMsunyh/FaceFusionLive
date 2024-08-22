
import threading
from modules.logger import logger
import time
import cv2

class FrameVisThread(threading.Thread):
    def __init__(self, queue, stop_event):
        super().__init__()
        self.queue = queue
        self._stop_event = stop_event
        self.name = self.__class__.__name__
                
        # Log the properties when initializing the thread
        logger.info(
            f"Initialized {self.name},"
        )

    def run(self):
        while not self._stop_event.is_set():
            if self.queue.empty() !=True:
                frame=self.queue.get()
                cv2.imshow("frame1", frame)
            else:
                 logger.info(f"Queue is empty")
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    def stop(self):
        logger.info(
            f"Stop FrameVisThread: "
            f"Thread Name: {self.name}, "
        )
        self._stop_event.set()
