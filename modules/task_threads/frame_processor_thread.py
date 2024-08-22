
import threading
from modules.logger import logger
import time
import concurrent.futures
import queue


class FrameProcessorThread(threading.Thread):
    def __init__(self, queue, frame_processors, source_image, ffmpeg_processor, stop_event, max_workers=12, resource_lock=None):
        super().__init__()
        self.queue = queue
        self.frame_processors = frame_processors
        self.source_image = source_image
        self.ffmpeg_processor = ffmpeg_processor
        self._stop_event = stop_event
        self.max_workers = max_workers
        self.resource_lock = resource_lock  # Store the lock
        
        self.name = self.__class__.__name__

        # Log the properties when initializing the thread
        logger.info(
            f"Initialized {self.name},"
            f"Queue Size: {self.queue.qsize()}, "
            f"Max Workers: {self.max_workers}"
        )

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            while not self._stop_event.is_set():
                if not self.queue.empty():
                    try:
                        # Fetch a frame from the queue
                        frame = self.queue.get(timeout=1)
                        
                        # Submit the frame processing task to the executor
                        future = executor.submit(self.process_single_frame, frame)
                        futures.append(future)
                        
                        # Ensure that futures are processed in the same order
                        if len(futures) >= self.max_workers:
                            for future in futures:
                                processed_frame = future.result()  # Blocking call to ensure order
                                if self.ffmpeg_processor and not self.ffmpeg_processor.send_frame_with_retry(processed_frame):
                                    logger.error(f" Push stream failed...")
                                    # self._stop_event.set()
                                    break
                            futures.clear()  # Clear the list of futures once processed

                    except Exception as e:
                        logger.error(f" An abnormal error occurred...")
                        continue
                else:
                    logger.info(f"Queue is empty")
                

    def process_single_frame(self, frame):
        # time.sleep(0.1)
        # start_time = time.time()

        for frame_processor in self.frame_processors:
            frame = frame_processor.process_frame(self.source_image, frame)

        # end_time = time.time()
        # elapsed_time = end_time - start_time
        # hours, remainder = divmod(elapsed_time, 3600)
        # minutes, seconds = divmod(remainder, 60)
        # logger.info(f"Program runtime: {int(hours)} hours {int(minutes)} minutes {seconds:.2f} seconds")
        return frame

    
    
    def stop(self):
        logger.info(
            f"Stop FrameProcessorThread: "
            f"Thread Name: {self.name}, "
        )

        self._stop_event.set()