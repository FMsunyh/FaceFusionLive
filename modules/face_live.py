import logging
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s',
    handlers=[
        logging.FileHandler("face_live.log"),
        logging.StreamHandler()
    ]
)

class RuntimeMonitorThread(threading.Thread):
    def __init__(self, start_time, stop_event, interval=60):
        super().__init__()
        self.start_time = start_time
        self.interval = interval
        self._stop_event = stop_event

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
        logging.info(f"Program runtime: {int(hours)} hours {int(minutes)} minutes {seconds:.2f} seconds")

    def stop(self):
        self._stop_event.set()

class FrameCaptureThread(threading.Thread):
    def __init__(self, cap, frame_queue, stop_event, buffer_size=10, max_retries=5):
        super().__init__()
        self.cap = cap
        self.frame_queue = frame_queue
        self._stop_event = stop_event
        self.buffer_size = buffer_size
        self.max_retries = max_retries

    def run(self):
        retry_count = 0
        while not self._stop_event.is_set() and retry_count < self.max_retries:
            try:
                if self.frame_queue.qsize() < self.buffer_size:
                    ret, frame = self.cap.read()
                    if not ret:
                        retry_count += 1
                        logging.error(f"Failed to read frame, retrying... (attempt {retry_count})")
                        time.sleep(1)  # Wait before retrying
                    else:
                        retry_count = 0  # Reset retry count on successful read
                        self.frame_queue.put(frame)
                else:
                    time.sleep(0.01)  # Avoid busy-waiting when the buffer is full

            except Exception as e:
                logging.error(f"Error in FrameCaptureThread: {e}")
                retry_count += 1
                time.sleep(1)  # Wait before retrying

        if retry_count >= self.max_retries:
            logging.error("Maximum retries reached for reading frames. Stopping thread.")

    def stop(self):
        self._stop_event.set()



class HeartbeatThread(threading.Thread):
    def __init__(self, stop_event, interval=60):
        super().__init__()
        self.interval = interval
        self._stop_event = stop_event

    def run(self):
        while not self._stop_event.is_set():
            logging.info("Heartbeat: Program is running normally")
            time.sleep(self.interval)

    def stop(self):
        self._stop_event.set()


class FrameProcessorThread(threading.Thread):
    def __init__(self, queue, frame_processors, source_image, process, stop_event, max_workers=12):
        super().__init__()
        self.queue = queue
        self.frame_processors = frame_processors
        self.source_image = source_image
        self.process = process
        self._stop_event = stop_event
        self.max_workers = max_workers

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            while not self._stop_event.is_set() or not self.queue.empty():
                try:
                    frame = self.queue.get(timeout=1)
                    future = executor.submit(self.process_single_frame, frame)
                    futures.append(future)

                    if len(futures) > self.max_workers:
                        for future in futures:
                            processed_frame = future.result()
                            if not self.push_stream_with_retry(processed_frame):
                                logging.error("Streaming failed, unable to recover, stop frame-processor-thread")
                                self._stop_event.set()
                                break
                        futures.clear()

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
                logging.error(f"Streaming failed, retrying... (attempt {attempt + 1})")
                time.sleep(1)
                if attempt == retry_count - 1:
                    return False
            except Exception as e:
                logging.error(f"Error writing to FFmpeg: {e}")
                time.sleep(1)
                if attempt == retry_count - 1:
                    return False
        return False
    
    def stop(self):
        self._stop_event.set()

def start_ffmpeg_process(width, height, fps, input_rtmp_url, output_rtmp_url):
    """Start the FFmpeg process for streaming."""
    ffmpeg_command = [
        'ffmpeg',
        '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f'{width}x{height}',
        '-r', str(fps),
        '-i', '-',
        '-i', input_rtmp_url,
        '-c:v', 'h264_nvenc',  # Use Nvidia GPU for encoding
        '-c:a', 'copy',
        '-pix_fmt', 'yuv420p',
        '-preset', 'fast',
        '-f', 'flv',
        '-flvflags', 'no_duration_filesize',
        # '-loglevel', 'quiet',
        output_rtmp_url
    ]
    process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)
    logging.info(f"Started FFmpeg streaming to: {output_rtmp_url}")
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
            logging.info("Video stream released")
    except Exception as e:
        logging.warning(f"Exception while releasing video stream: {e}")

    try:
        if process.stdin:
            process.stdin.close()
            logging.info("FFmpeg stdin closed")
    except Exception as e:
        logging.warning(f"Exception while closing FFmpeg stdin: {e}")

    try:
        process.wait(timeout=5)
        logging.info("FFmpeg process ended normally")
    except subprocess.TimeoutExpired:
        logging.warning("Timeout waiting for FFmpeg process to end, trying to terminate")
        try:
            process.terminate()
            process.wait(timeout=5)
            logging.info("FFmpeg process terminated")
        except Exception as e:
            logging.error(f"Exception while terminating FFmpeg process: {e}")

    logging.info("All resources released")


def handle_streaming(cap, process, face_source_path, frame_processors):
    """Handle video streaming, capture, process frames, and push through FFmpeg."""
    logging.info(f"Face source: {face_source_path}")
    frame_processors = get_frame_processors_modules(frame_processors)
    source_image = get_one_face(cv2.imread(face_source_path))

    frame_queue = queue.Queue(maxsize=300)
    stop_event = threading.Event()

    # Start the frame capture thread
    frame_capture_thread = FrameCaptureThread(cap, frame_queue, stop_event)
    frame_capture_thread.start()

   # Create and start processing thread
    frame_processor_thread = FrameProcessorThread(
        queue=frame_queue, 
        frame_processors=frame_processors, 
        source_image=source_image,
        process=process,
        stop_event=stop_event
    )
    frame_processor_thread.start()

    heartbeat_thread = HeartbeatThread(stop_event, interval=60)
    heartbeat_thread.start()

    runtime_monitor_thread = RuntimeMonitorThread(start_time=time.time(), stop_event=stop_event, interval=360)
    runtime_monitor_thread.start()

    try:
        while True:
            if process.poll() is not None:
                exit_code = process.poll()
                if exit_code != 0:
                    logging.error(f"FFmpeg process exited abnormally, exit code: {exit_code}")
                else:
                    logging.info("FFmpeg process exited normally")
                break
            
            if not frame_capture_thread.is_alive() or not frame_processor_thread.is_alive() or not heartbeat_thread.is_alive() or not runtime_monitor_thread.is_alive():
                logging.error("One or more threads have exited abnormally.")
                stop_event.set()
                break

    except Exception as e:
        logging.error(f"Error in streaming: {e}")

    finally:
        stop_event.set()
        frame_processor_thread.join()
        frame_capture_thread.join()
        heartbeat_thread.join()
        runtime_monitor_thread.join()
        cleanup_resources(cap, process)

def stream_worker(input_rtmp_url, output_rtmp_url, face_source_path, frame_processors, restart_interval=5, max_retries=5):
    """RTMP stream worker with retry mechanism."""
    retry_count = 0
    while retry_count < max_retries:
        try:
            logging.info(f"Starting stream: {input_rtmp_url}")
            cap = open_input_stream(input_rtmp_url)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25  # Default to 25 fps if unknown
            
            process = start_ffmpeg_process(width, height, fps, input_rtmp_url, output_rtmp_url)
            handle_streaming(cap, process, face_source_path, frame_processors)

        except cv2.error as cv_err:
            logging.exception(f"OpenCV error: {cv_err}")
        except IOError as io_err:
            logging.exception(f"IO error: {io_err}")
        except Exception as e:
            logging.exception(f"Unknown error during stream processing: {e}")
        finally:
            if 'cap' in locals():
                cleanup_resources(cap, process)
            logging.info(f"Waiting {restart_interval} seconds before retrying...")
            time.sleep(restart_interval)
            retry_count += 1

    if retry_count >= max_retries:
        logging.error(f"Reached maximum retries, stopping stream: {input_rtmp_url}")

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
        logging.info(f"========================================Started========================================")
        logging.info(f"Started process {p.name} handling stream: {stream_info[0]} -> {stream_info[1]}")
    
    try:
        while True:
            for i, p in enumerate(processes):
                if not p.is_alive():
                    logging.error(f"Process {p.name} has stopped, restarting...")
                    processes[i] = start_stream_process(streams[i])
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Termination signal received, shutting down...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join()
        logging.info("All processes closed. Program exiting.")

def webcam():
    frame_processors = modules.globals.frame_processors
    streams = [
        ('rtmp://120.241.153.43:1935/live111', 'rtmp://120.241.153.43:1935/live', modules.globals.source_path, frame_processors),
    ]
    manage_streams(streams)

if __name__ == "__main__":
    webcam()
