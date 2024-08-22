import threading
from modules.logger import logger
import time

class FrameCaptureThread(threading.Thread):
    def __init__(self, cap, queue, stop_event, buffer_size=10, max_retries=20):
        super().__init__()
        self.cap = cap
        self.queue = queue
        self._stop_event = stop_event
        self.buffer_size = buffer_size
        self.max_retries = max_retries

        self.name = self.__class__.__name__

        # Log the properties when initializing the thread
        logger.info(
            f"Initialized {self.name},"
            f"Queue Size: {self.queue.qsize()}, "
            f"Buffer Size: {self.buffer_size}, "
            f"Max Retries: {self.max_retries}"
        )

    def run(self):
        retry_count = 0
        while not self._stop_event.is_set() and retry_count < self.max_retries:
            try:
                if self.queue.qsize() < self.buffer_size:
                    ret, frame = self.cap.read()
                    if not ret:
                        retry_count += 1
                        logger.error(f"Failed to read frame, retrying... (attempt {retry_count})")
                        time.sleep(0.01)  # Wait before retrying
                    else:
                        retry_count = 0  # Reset retry count on successful read
                        # with self.resource_lock:
                        self.queue.put(frame)
                        # logger.info(f"Succeeded to read frame...{self.queue.qsize()}/{self.buffer_size}")
                else:
                    time.sleep(0.01)  # Avoid busy-waiting when the buffer is full

            except Exception as e:
                logger.error(f"Error in FrameCaptureThread: {e}")
                retry_count += 1
                time.sleep(1)  # Wait before retrying

        if retry_count >= self.max_retries:
            logger.error("Maximum retries reached for reading frames. Stopping thread.")

    def stop(self):
        logger.info(
            f"Stop FrameCaptureThread: "
            f"Thread Name: {self.name}, "
        )
        self._stop_event.set()
