
import threading
from modules.logger import logger
import time
import concurrent.futures

class FramePullThread(threading.Thread):
    def __init__(self,  queue, process, stop_event, max_workers=10):
        super().__init__()
        self.queue = queue
        self.process = process
        self._stop_event = stop_event
        self.name = self.__class__.__name__
        self.max_workers  = max_workers
        # Log the properties when initializing the thread
        logger.info(
            f"Initialized Thread Name: {self.name}"
        )

    def run(self):
            futures = []
            while not self._stop_event.is_set():
                if not self.queue.empty():
                    try:
                        # Fetch a frame from the queue
                        frame = self.queue.get(timeout=1)
                        # Submit the frame processing task to the executor
                        futures.append(frame)
                        
                        # Ensure that futures are processed in the same order
                        if len(futures) >= self.max_workers:
                            for future in futures:
                                if not self.push_stream_with_retry(future):
                                    logger.error(f" Push stream failed...")
                                    # self._stop_event.set()
                                    break
                            futures.clear()  # Clear the list of futures once processed

                    except Exception as e:
                        logger.error(f" An abnormal error occurred...{e}")
                        continue
                else:
                    pass
                    # logger.info(f"Queue is empty")

    def stop(self):
        logger.info(
            f"Stop thread Name: {self.name}"
        )
        self._stop_event.set()

    def push_stream_with_retry(self, frame, retry_count=3):
        """Push the frame to FFmpeg with retry mechanism."""
        if frame is None:
            logger.info(f"Push Streaming failed, frame is none")
            return False
        
        for attempt in range(retry_count):
            try:
                self.process.stdin.write(frame.tobytes())
                return True
            except BrokenPipeError:
                logger.error(f"Push Streaming failed, retrying... (attempt {attempt + 1})")
                time.sleep(1)
                if attempt == retry_count - 1:
                    return False
            except Exception as e:
                logger.error(f"Error writing to FFmpeg: {e}")
                time.sleep(1)
                if attempt == retry_count - 1:
                    return False
        return False
