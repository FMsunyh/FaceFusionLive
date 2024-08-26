
import threading
from modules.logger import logger
import time
import concurrent.futures
import queue


import cv2
import time
import datetime


class FrameProcessorThread(threading.Thread):
    def __init__(self, queue, frame_processors, source_image, ffmpeg_processor, stop_event, max_workers=10):
        super().__init__()
        self.queue = queue
        self.frame_processors = frame_processors
        self.source_image = source_image
        self.ffmpeg_processor = ffmpeg_processor
        self._stop_event = stop_event
        self.max_workers = max_workers
        
        self.name = self.__class__.__name__

        # Log the properties when initializing the thread
        logger.info(
            f"Initialized {self.name},"
            f"Queue Size: {self.queue.qsize()}, "
            f"Max Workers: {self.max_workers}"
        )

    # def run(self):
    #     with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    #         futures = []
    #         while not self._stop_event.is_set():
    #             if not self.queue.empty():
    #                 try:
    #                     # Fetch a frame from the queue
    #                     frame = self.queue.get(timeout=1)
                        
    #                     # Submit the frame processing task to the executor
    #                     future = executor.submit(self.process_single_frame, frame)
    #                     futures.append(future)
                        
                        
    #                     # Ensure that futures are processed in the same order
    #                     if len(futures) >= self.max_workers:
    #                         for future in futures:
    #                             processed_frame = future.result()  # Blocking call to ensure order
    #                             if self.ffmpeg_processor and not self.ffmpeg_processor.send_frame_with_retry(processed_frame):
    #                                 logger.error(f" Push stream failed...")
    #                                 # self._stop_event.set()
    #                                 break
    #                         futures.clear()  # Clear the list of futures once processed

    #                 except Exception as e:
    #                     logger.error(f" An abnormal error occurred...")
    #                     continue
    #             else:
    #                 pass
    #                 # logger.info(f"Queue is empty")
                

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            frames = []
            while not self._stop_event.is_set():
                if not self.queue.empty():
                    try:
                        # Fetch a frame from the queue
                        frame = self.queue.get(timeout=1)
                        # Submit the frame processing task to the executor
                        frames.append(frame)
                        
                        # Ensure that futures are processed in the same order
                        if len(frames) >= self.max_workers:
                            # results = frames
                            results = list(executor.map(self.process_single_frame, frames))
                            # results = list(executor.map(self.add_timestamp_to_image, frames))

                            for future in results:
                                if self.ffmpeg_processor and not self.ffmpeg_processor.send_frame_with_retry(future):
                                    logger.error(f" Push stream failed...")
                                    # self._stop_event.set()
                                    break
                            frames.clear()  # Clear the list of futures once processed

                    except Exception as e:
                        logger.error(f" An abnormal error occurred...{e}")
                        continue
                else:
                    pass
                    # logger.info(f"Queue is empty")

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

    def add_timestamp_to_image(self, image):
        # 检查图像是否成功加载
        if image is None:
            raise ValueError("无法加载图像，请检查输入路径。")

        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 设置字体、大小、颜色和粗细
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.5
        font_color = (255, 0, 0)  # 蓝色
        thickness = 2

        # 获取文本的宽度和高度
        (text_width, text_height), baseline = cv2.getTextSize(current_time, font, font_scale, thickness)

        # 计算文本的起始位置 (在图像的中央)
        position = ((image.shape[1] - text_width) // 2, (image.shape[0] + text_height) // 2)

        # 在图像上写入当前时间
        cv2.putText(image, current_time, position, font, font_scale, font_color, thickness, cv2.LINE_AA)

        # # 显示图像
        # cv2.imshow('Image with Time', image)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()

        return image
    
    def stop(self):
        logger.info(
            f"Stop FrameProcessorThread: "
            f"Thread Name: {self.name}, "
        )

        self._stop_event.set()