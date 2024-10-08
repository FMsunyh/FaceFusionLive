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
import threading
import queue
import socket

from modules.task_threads.ffmpeg_streamer_process import FFmpegStreamerProcess
from modules.task_threads.ffmpeg_subprocess import start_ffmpeg_process
from modules.task_threads.frame_add_time_thread import FrameAddTimeThread
from modules.task_threads.frame_capture_thread import FrameCaptureThread
from modules.task_threads.frame_processor_thread import FrameProcessorThread
from modules.task_threads.frame_pull_thread import FramePullThread
from modules.task_threads.frame_vis_thread import FrameVisThread
from modules.task_threads.heart_beat_thread import HeartbeatThread
from modules.task_threads.rtmp_monitor_thread import RTMPMonitorThread
from modules.task_threads.runtime_monitor_thread import RuntimeMonitorThread
import signal

resource_lock = threading.Lock()


# def open_input_stream(input_rtmp_url):
#     """Open the input RTMP stream."""
#     cap = cv2.VideoCapture(input_rtmp_url)
#     if not cap.isOpened():
#         raise RuntimeError(f"Cannot open input stream: {input_rtmp_url}")
#     return cap

def open_input_stream(input_rtmp_url, delay=5):
    """Continuously attempt to open the input RTMP stream until successful."""
    while True:
        try:
            cap = cv2.VideoCapture(input_rtmp_url)
            if cap.isOpened():
                logger.info(f"Successfully opened input stream: {input_rtmp_url}")
                return cap
            else:
                logger.error(f"Failed to open input stream: {input_rtmp_url}. Retrying in {delay} seconds...")
                cap.release()  # Release the capture if opened
        except Exception as e:
            logger.error(f"An error occurred: {e}. Retrying in {delay} seconds...")

        time.sleep(delay)

def cleanup_resources(cap, process):
    """Release resources, close video stream and FFmpeg process."""
    try:
        if cap.isOpened():
            cap.release()
            logger.info("Video stream released")
    except Exception as e:
        logger.warning(f"Exception while releasing video stream: {e}")

    process.stop()

    logger.info("All resources released")


def handle_streaming(cap, ffmpeg_processor, face_source_path, frame_processors):
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
        buffer_size=100
        )
    frame_capture_thread.start()

   # Create and start processing thread
    frame_processor_thread = FrameProcessorThread(
        queue=frame_queue, 
        frame_processors=frame_processors, 
        source_image=source_image,
        ffmpeg_processor=ffmpeg_processor,
        stop_event=stop_event,
        max_workers=12
    )
    frame_processor_thread.start()
    
    frame_addtime_thread = FrameAddTimeThread(
        queue=frame_queue, 
        frame_processors=frame_processors, 
        source_image=source_image,
        ffmpeg_processor=ffmpeg_processor,
        stop_event=stop_event,
        max_workers=12
    )
    # frame_addtime_thread.start()

    frame_pull_thread = FramePullThread(queue=frame_queue, ffmpeg_processor=ffmpeg_processor, stop_event=stop_event)
    # frame_pull_thread.start()
    
    frame_vis_thread = FrameVisThread(queue=frame_queue,stop_event=stop_event)
    # frame_vis_thread.start()

    heartbeat_thread = HeartbeatThread(stop_event, interval=120)
    heartbeat_thread.start()

    runtime_monitor_thread = RuntimeMonitorThread(start_time=time.time(), stop_event=stop_event, interval=360)
    runtime_monitor_thread.start()

    # network_monitor_thread = NetworkMonitorThread(stop_event=stop_event, interval=5, check_host="rtmp://183.232.228.244")
    # network_monitor_thread.start()

    rtmp_monitor_thread = RTMPMonitorThread(rtmp_url='rtmp://183.232.228.244:1935', stop_event=stop_event, interval=720)
    rtmp_monitor_thread.start()

    try:
        while True:
            # time.sleep(120)
            
            if not ffmpeg_processor.is_running():
                logger.error("ffmpeg push processor have exited abnormally.")
                break
            
            if not frame_capture_thread.is_alive():
                logger.error("frame_capture_thread have exited abnormally.")
                break
            
            if not frame_processor_thread.is_alive():
                logger.error("frame_processor_thread have exited abnormally.")
                break
                        
            # if not frame_addtime_thread.is_alive():
            #     logger.error("frame_processor_thread have exited abnormally.")
            #     break
            
            
            if not heartbeat_thread.is_alive():
                logger.error("heartbeat_thread have exited abnormally.")
                break
            
            if not runtime_monitor_thread.is_alive():
                logger.error("runtime_monitor_thread have exited abnormally.")
                break
            
            # logger.info("handle streaming: Main program is running normally")
            
    except Exception as e:
        logger.error(f"Error in streaming: {e}")

    finally:
        logger.info("Handler streaming : Stop  thread.")
        frame_capture_thread.stop()
        frame_capture_thread.join(timeout=1)

        frame_processor_thread.stop()
        frame_processor_thread.join(timeout=1)

        # frame_addtime_thread.stop()
        # frame_addtime_thread.join(timeout=1)
        
        # frame_pull_thread.stop()
        # frame_pull_thread.join(timeout=1)

        # frame_vis_thread.stop()
        # frame_vis_thread.join(timeout=1)


        heartbeat_thread.stop()
        heartbeat_thread.join(timeout=1)

        rtmp_monitor_thread.stop()
        rtmp_monitor_thread.join(timeout=1)

        runtime_monitor_thread.stop()
        runtime_monitor_thread.join(timeout=1)
        
        logger.info("done thread.")

def test(cap, process):
    retries = 0
    max_retries = 10
    while retries < max_retries:
        # Capture frame-by-frame
        ret, frame = cap.read()
        
        # Check if the frame was read successfully
        if ret:
            # Display the resulting frame
            process.stdin.write(frame.tobytes())

            # If successful, reset retries
            retries = 0
        else:
            print(f"Failed to read frame. Retrying {retries}...")
            retries += 1
            time.sleep(0.1)

    # cleanup_resources(cap, process)

def signal_handler(sig, frame, ffmpeg_processor):
    """Handle termination signals to gracefully stop the FFmpeg process."""
    logger.info("Received termination signal, stopping FFmpeg process...")
    ffmpeg_processor.stop()
    logger.info("FFmpeg process stopped, exiting program.")
    exit(0)
    
def stream_worker(input_rtmp_url, output_rtmp_url, face_source_path, frame_processors, restart_interval=1, max_retries=100):
    """RTMP stream worker with retry mechanism."""
    retry_count = 0
    
    ffmpeg_processor = None  # Initialize the ffmpeg_processor variable

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, ffmpeg_processor))
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler(sig, frame, ffmpeg_processor))
    
    while retry_count < max_retries:
        try:
            logger.info(f"=================================================================================")
            logger.info(f"Stream Worker (retry_count/max_retries): {retry_count}/{max_retries}")
            logger.info(f"Starting stream: {input_rtmp_url}")
            cap = open_input_stream(input_rtmp_url)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25  # Default to 25 fps if unknown
            # process = start_ffmpeg_process(width, height, fps, input_rtmp_url, output_rtmp_url)
            ffmpeg_processor = FFmpegStreamerProcess(width, height, fps, input_rtmp_url, output_rtmp_url)
            ffmpeg_processor.start()

            handle_streaming(cap, ffmpeg_processor, face_source_path, frame_processors)

            cleanup_resources(cap, ffmpeg_processor)

        except cv2.error as cv_err:
            logger.exception(f"OpenCV error: {cv_err}")
        except IOError as io_err:
            logger.exception(f"IO error: {io_err}")
        except Exception as e:
            logger.exception(f"Unknown error during stream processing: {e}")
        finally:
            if 'cap' in locals():
                cleanup_resources(cap, ffmpeg_processor)
            logger.info(f"Waiting {restart_interval} seconds before retrying...")
            time.sleep(restart_interval)
            retry_count += 1

    if retry_count >= max_retries:
        logger.error(f"Reached maximum retries, stopping stream: {input_rtmp_url}")

def manage_streams(streams):
    """Manage multiple RTMP streams, each in a separate process."""
    processes = []

    def start_stream_process(stream_info):
        logger.info(f"=======================Start=======================")
        input_url, output_url, face_source_path, frame_processors = stream_info
        p = Process(target=stream_worker, args=(input_url, output_url, face_source_path, frame_processors))
        p.daemon = True
        p.start()
        logger.info(f"Started process {p.name} handling stream: {stream_info[0]} -> {stream_info[1]}")

        return p

    for stream_info in streams:
        p = start_stream_process(stream_info)
        processes.append(p)

    
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
    source_path =  modules.globals.source_path
    rtmp_input = modules.globals.rtmp_input # 'rtmp://183.232.228.244:1935/live_input'，'demo\\video\\m1.mp4'
    rtmp_output = modules.globals.rtmp_output # 'rtmp://183.232.228.244:1935/live'
    frame_processors = modules.globals.frame_processors
    
    streams = [
        (rtmp_input, rtmp_output,source_path, frame_processors),
    ]
    
    manage_streams(streams)

# if __name__ == "__main__":
#     webcam()
