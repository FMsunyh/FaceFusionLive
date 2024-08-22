import threading
from modules.logger import logger
import time

class RuntimeMonitorThread(threading.Thread):
    def __init__(self, start_time, stop_event, interval=60):
        super().__init__()
        self.start_time = start_time
        self.interval = interval
        self._stop_event = stop_event
        
        self.name = self.__class__.__name__
        # Log the properties when initializing the thread
        logger.info(
            f"Initialized FrameCaptureThread: "
            f"Thread Name: {self.name}, "
            f"Interval: {self.interval} "
        )

    def run(self):
        while not self._stop_event.is_set():
            self.measure_runtime(self.start_time)
            time.sleep(self.interval)

    def measure_runtime(self, start_time):
        """Record the program's runtime and output in hours, minutes, and seconds."""
        end_time = time.time()
        elapsed_time = end_time - start_time
        hours, remainder = divmod(elapsed_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        logger.info(f"Program runtime: {int(hours)} hours {int(minutes)} minutes {seconds:.2f} seconds")

    def stop(self):
        logger.info(
            f"Stop RuntimeMonitorThread: "
            f"Thread Name: {self.name}, "
        )
        self._stop_event.set()