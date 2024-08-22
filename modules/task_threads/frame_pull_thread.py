
import threading
from modules.logger import logger
import time
import concurrent.futures

class FramePullThread(threading.Thread):
    def __init__(self,  queue, ffmpeg_processor, stop_event, max_workers=10):
        super().__init__()
        self.queue = queue
        self.ffmpeg_processor = ffmpeg_processor
        self._stop_event = stop_event
        self.name = self.__class__.__name__
        self.max_workers  = max_workers
        # Log the properties when initializing the thread
        logger.info(
            f"Initialized {self.name},"
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
                                if not self.ffmpeg_processor and not self.ffmpeg_processor.send_frame_with_retry(future):
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