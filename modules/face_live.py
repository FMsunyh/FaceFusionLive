from modules.logger import logger
from multiprocessing import Process, current_process
import cv2
import subprocess
import time
import concurrent.futures
import modules.globals
import modules.metadata
from modules.face_analyser import get_one_face
from modules.processors.frame.core import get_frame_processors_modules
import multiprocessing
import threading
import queue
import socket

resource_lock = threading.Lock()

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
                logger.warning(f"RTMP 服务器不可用: {self.rtmp_url}")
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
            logger.error(f"RTMP 连接失败: {e}")
            return False

    def parse_rtmp_url(self, rtmp_url):
        """从 RTMP URL 中解析出主机和端口"""
        url_parts = rtmp_url.replace("rtmp://", "").split("/")
        host_port = url_parts[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 1935  # 默认端口为 1935
        return host, port

    def stop(self):
        self._stop_event.set()


class NetworkMonitorThread(threading.Thread):
    def __init__(self, stop_event, interval=5, check_host="8.8.8.8"):
        super().__init__()
        self.interval = interval
        self.check_host = check_host
        self._stop_event = stop_event
        self.network_available = True

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
        self._stop_event.set()


class RuntimeMonitorThread(threading.Thread):
    def __init__(self, start_time, stop_event, interval=60):
        super().__init__()
        self.start_time = start_time
        self.interval = interval
        self._stop_event = stop_event
        
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
        self._stop_event.set()


class FrameCaptureThread(threading.Thread):
    def __init__(self, cap, queue, stop_event, buffer_size=10, max_retries=3, resource_lock=None):
        super().__init__()
        self.cap = cap
        self.queue = queue
        self._stop_event = stop_event
        self.buffer_size = buffer_size
        self.max_retries = max_retries
        self.resource_lock = resource_lock  # Store the lock

        # Log the properties when initializing the thread
        logger.info(
            f"Initialized FrameCaptureThread: "
            f"Thread Name: {self.name}, "
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
                        time.sleep(1)  # Wait before retrying
                    else:
                        retry_count = 0  # Reset retry count on successful read
                        # with self.resource_lock:
                        self.queue.put(frame)
                else:
                    time.sleep(0.01)  # Avoid busy-waiting when the buffer is full

            except Exception as e:
                logger.error(f"Error in FrameCaptureThread: {e}")
                retry_count += 1
                time.sleep(1)  # Wait before retrying

        if retry_count >= self.max_retries:
            logger.error("Maximum retries reached for reading frames. Stopping thread.")

    def stop(self):
        self._stop_event.set()


class HeartbeatThread(threading.Thread):
    def __init__(self, stop_event, interval=60):
        super().__init__()
        self.interval = interval
        self._stop_event = stop_event
                
        # Log the properties when initializing the thread
        logger.info(
            f"Initialized FrameProcessorThread: "
            f"Thread Name: {self.name}, "
            f"Interval: {self.interval} "
        )

    def run(self):
        while not self._stop_event.is_set():
            logger.info("Heartbeat: Program is running normally")
            time.sleep(self.interval)

    def stop(self):
        self._stop_event.set()


# class FrameProcessorThread(threading.Thread):
#     def __init__(self, queue, frame_processors, source_image, process, stop_event, max_workers=12, resource_lock=None):
#         super().__init__()
#         self.queue = queue
#         self.frame_processors = frame_processors
#         self.source_image = source_image
#         self.process = process
#         self._stop_event = stop_event
#         self.max_workers = max_workers
#         self.resource_lock = resource_lock  # Store the lock
        
#         # Log the properties when initializing the thread
#         logger.info(
#             f"Initialized FrameProcessorThread: "
#             f"Thread Name: {self.name}, "
#             f"Queue Size: {self.queue.qsize()}, "
#             f"Max Workers: {self.max_workers}"
#         )

#     def run(self):
#         with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
#             futures = []
#             while not self._stop_event.is_set() or not self.queue.empty():
#                 try:
#                     # with self.resource_lock:
#                     frame = self.queue.get(timeout=1)
#                     future = executor.submit(self.process_single_frame, frame)
#                     futures.append(future)

#                     if len(futures) > self.max_workers:
#                         for future in futures:
#                             processed_frame = future.result()
#                             if not self.push_stream_with_retry(processed_frame):
#                                 logger.error("Streaming failed, unable to recover, stop frame-processor-thread")
#                                 self._stop_event.set()
#                                 break
#                         futures.clear()

#                 except queue.Empty:
#                     continue

#     def process_single_frame(self, frame):
#         for frame_processor in self.frame_processors:
#             frame = frame_processor.process_frame(self.source_image, frame)
#         return frame

#     def push_stream_with_retry(self, frame, retry_count=3):
#         """Push the frame to FFmpeg with retry mechanism."""
#         for attempt in range(retry_count):
#             try:
#                 # with self.resource_lock:
#                 self.process.stdin.write(frame.tobytes())
#                 return True
#             except BrokenPipeError:
#                 logger.error(f"Push Streaming failed, retrying... (attempt {attempt + 1})")
#                 time.sleep(1)
#                 if attempt == retry_count - 1:
#                     return False
#             except Exception as e:
#                 logger.error(f"Error writing to FFmpeg: {e}")
#                 time.sleep(1)
#                 if attempt == retry_count - 1:
#                     return False
#         return False
    
#     def stop(self):
#         self._stop_event.set()

class FrameProcessorThread(threading.Thread):
    def __init__(self, queue, frame_processors, source_image, process, stop_event, max_workers=12, resource_lock=None):
        super().__init__()
        self.queue = queue
        self.frame_processors = frame_processors
        self.source_image = source_image
        self.process = process
        self._stop_event = stop_event
        self.max_workers = max_workers
        self.resource_lock = resource_lock  # Store the lock

        # Log the properties when initializing the thread
        logger.info(
            f"Initialized FrameProcessorThread: "
            f"Thread Name: {self.name}, "
            f"Queue Size: {self.queue.qsize()}, "
            f"Max Workers: {self.max_workers}"
        )

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            while not self._stop_event.is_set() or not self.queue.empty():
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
                            if not self.push_stream_with_retry(processed_frame):
                                logger.error("Streaming failed, unable to recover, stopping frame-processor-thread")
                                self._stop_event.set()
                                break
                        futures.clear()  # Clear the list of futures once processed

                except queue.Empty:
                    continue

    def process_single_frame(self, frame):
        for frame_processor in self.frame_processors:
            frame = frame_processor.process_frame(self.source_image, frame)
        return frame

    def push_stream_with_retry(self, frame, retry_count=3):
        """Push the frame to FFmpeg with retry mechanism."""
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
    
    def stop(self):
        self._stop_event.set()


def start_ffmpeg_process(width, height, fps, input_rtmp_url, output_rtmp_url):
    """Start the FFmpeg process for streaming."""
    # ffmpeg_command = [
    # 'ffmpeg',
    # '-y',
    # '-f', 'rawvideo',
    # '-vcodec', 'rawvideo',
    # '-pix_fmt', 'bgr24',
    # '-s', f'{width}x{height}',
    # '-r', str(fps),
    # '-i', '-',
    # '-i', input_rtmp_url,
    # '-c:v', 'h264_nvenc',
    # '-c:a', 'aac',
    # '-b:a', '128k',
    # '-pix_fmt', 'yuv420p',
    # '-preset', 'fast',
    # '-f', 'flv',
    # '-flvflags', 'no_duration_filesize',
    # # '-fps_mode', 'vfr',  # Replace -vsync with -fps_mod
    # '-async', '1',        # Ensure audio sync
    # '-shortest',          # Stop encoding when the shortest stream ends
    # '-max_interleave_delta', '100M',
    # '-probesize', '100M',
    # '-analyzeduration', '100M',
    # # '-loglevel', 'debug', # Debugging level
    # output_rtmp_url
    # ]
    
    ffmpeg_command = [
        'ffmpeg',
        # '-hide_banner',  # 隐藏FFmpeg版本和版权信息
        '-y',  # Overwrite output files without asking
        '-f', 'rawvideo',  # Input format
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24',  # Pixel format (OpenCV uses BGR by default)
        '-s', f'{width}x{height}',  # Frame size
        '-r', str(fps),  # Frame rate
        '-i', '-',  # Input from stdin
        '-i', input_rtmp_url,  # 来自RTMP流的音频输入
        # '-c:v', 'libx264',  # Video codec
        '-c:v', 'h264_nvenc',  # 使用 NVENC 进行视频编码
        '-c:a', 'copy', # 音频编码器（直接复制音频，不重新编码）
        '-pix_fmt', 'yuv420p',  # Pixel format for output
        # '-preset', 'ultrafast',  # Encoding speed
        '-preset', 'fast',  # NVENC 提供了一些预设选项，"fast" 比 "ultrafast" 更高效
        '-f', 'flv',  # Output format
        '-flvflags', 'no_duration_filesize',
        '-fps_mode', 'vfr',  # Replace -vsync with -fps_mod
        '-async', '1',        # Ensure audio sync
        '-shortest',          # Stop encoding when the shortest stream ends
        output_rtmp_url
    ]

    process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)
    logger.info(f"Started FFmpeg streaming to: {output_rtmp_url}")
    return process

def open_input_stream(input_rtmp_url):
    """Open the input RTMP stream."""
    cap = cv2.VideoCapture(input_rtmp_url)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input stream: {input_rtmp_url}")
    return cap

def cleanup_resources(cap, process):
    """Release resources, close video stream and FFmpeg process."""
    try:
        if cap.isOpened():
            cap.release()
            logger.info("Video stream released")
    except Exception as e:
        logger.warning(f"Exception while releasing video stream: {e}")

    try:
        if process.stdin:
            process.stdin.close()
            logger.info("FFmpeg stdin closed")
    except Exception as e:
        logger.warning(f"Exception while closing FFmpeg stdin: {e}")

    try:
        process.wait(timeout=3)
        logger.info("FFmpeg process ended normally")
    except subprocess.TimeoutExpired:
        logger.warning("Timeout waiting for FFmpeg process to end, trying to terminate")
        try:
            process.terminate()
            process.wait(timeout=3)
            logger.info("FFmpeg process terminated")
        except Exception as e:
            logger.error(f"Exception while terminating FFmpeg process: {e}")

    logger.info("All resources released")


def handle_streaming(cap, process, face_source_path, frame_processors):
    """Handle video streaming, capture, process frames, and push through FFmpeg."""
    logger.info(f"Face source: {face_source_path}")
    frame_processors = get_frame_processors_modules(frame_processors)
    source_image = get_one_face(cv2.imread(face_source_path))

    frame_queue = queue.Queue(maxsize=100)
    stop_event = threading.Event()

    # Start the frame capture thread
    frame_capture_thread = FrameCaptureThread(
        cap, 
        frame_queue, 
        stop_event, 
        buffer_size=1,
        resource_lock=resource_lock
        )
    frame_capture_thread.start()

   # Create and start processing thread
    frame_processor_thread = FrameProcessorThread(
        queue=frame_queue, 
        frame_processors=frame_processors, 
        source_image=source_image,
        process=process,
        stop_event=stop_event,
        resource_lock=resource_lock
    )
    frame_processor_thread.start()

    heartbeat_thread = HeartbeatThread(stop_event, interval=60)
    heartbeat_thread.start()

    runtime_monitor_thread = RuntimeMonitorThread(start_time=time.time(), stop_event=stop_event, interval=360)
    runtime_monitor_thread.start()

    # network_monitor_thread = NetworkMonitorThread(stop_event=stop_event, interval=5, check_host="rtmp://120.241.153.43")
    # network_monitor_thread.start()

    rtmp_monitor_thread = RTMPMonitorThread(rtmp_url='rtmp://120.241.153.43:1935', stop_event=stop_event, interval=5)
    rtmp_monitor_thread.start()

    try:
        while True:
            if process.poll() is not None:
                exit_code = process.poll()
                if exit_code != 0:
                    logger.error(f"FFmpeg process exited abnormally, exit code: {exit_code}")
                else:
                    logger.info("FFmpeg process exited normally")
                break
            
            if not frame_capture_thread.is_alive() or not frame_processor_thread.is_alive() or not heartbeat_thread.is_alive() or not runtime_monitor_thread.is_alive():
                logger.error("One or more threads have exited abnormally.")
                stop_event.set()
                break

    except Exception as e:
        logger.error(f"Error in streaming: {e}")

    finally:
        stop_event.set()
        frame_processor_thread.join()
        frame_capture_thread.join()
        heartbeat_thread.join()
        runtime_monitor_thread.join()
        rtmp_monitor_thread.join()
        cleanup_resources(cap, process)

def stream_worker(input_rtmp_url, output_rtmp_url, face_source_path, frame_processors, restart_interval=3, max_retries=3):
    """RTMP stream worker with retry mechanism."""
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.info(f"Starting stream: {input_rtmp_url}")
            cap = open_input_stream(input_rtmp_url)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25  # Default to 25 fps if unknown
            
            process = start_ffmpeg_process(width, height, fps, input_rtmp_url, output_rtmp_url)
            handle_streaming(cap, process, face_source_path, frame_processors)

        except cv2.error as cv_err:
            logger.exception(f"OpenCV error: {cv_err}")
        except IOError as io_err:
            logger.exception(f"IO error: {io_err}")
        except Exception as e:
            logger.exception(f"Unknown error during stream processing: {e}")
        finally:
            if 'cap' in locals():
                cleanup_resources(cap, process)
            logger.info(f"Waiting {restart_interval} seconds before retrying...")
            time.sleep(restart_interval)
            retry_count += 1

    if retry_count >= max_retries:
        logger.error(f"Reached maximum retries, stopping stream: {input_rtmp_url}")

def manage_streams(streams):
    """Manage multiple RTMP streams, each in a separate process."""
    processes = []

    def start_stream_process(stream_info):
        input_url, output_url, face_source_path, frame_processors = stream_info
        p = Process(target=stream_worker, args=(input_url, output_url, face_source_path, frame_processors))
        p.daemon = True
        p.start()
        return p

    for stream_info in streams:
        p = start_stream_process(stream_info)
        processes.append(p)
        logger.info(f"=======================Start=======================")
        logger.info(f"Started process {p.name} handling stream: {stream_info[0]} -> {stream_info[1]}")
    
    try:
        while True:
            for i, p in enumerate(processes):
                if not p.is_alive():
                    logger.error(f"Process {p.name} has stopped, restarting...")
                    processes[i] = start_stream_process(streams[i])
            time.sleep(3)
    except KeyboardInterrupt:
        logger.info("Termination signal received, shutting down...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join()
        logger.info("All processes closed. Program exiting.")

def webcam():
    frame_processors = modules.globals.frame_processors
    streams = [
        ('rtmp://120.241.153.43:1935/live_input', 'rtmp://120.241.153.43:1935/live', modules.globals.source_path, frame_processors),
    ]
    manage_streams(streams)

# if __name__ == "__main__":
#     webcam()
