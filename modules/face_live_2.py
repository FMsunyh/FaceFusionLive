import os
import webbrowser
import customtkinter as ctk
from typing import Callable, Tuple
import cv2
from PIL import Image, ImageOps
import subprocess
import time
import concurrent.futures
import modules.globals
import modules.metadata
from modules.face_analyser import get_one_face
from modules.capturer import get_video_frame, get_video_frame_total
from modules.processors.frame.core import get_frame_processors_modules
from modules.utilities import is_image, is_video, resolve_relative_path
from queue import Queue
from threading import Thread

# RTMP server URL and stream key
input_rtmp_url = 'rtmp://183.232.228.244:1935/live_input'
output_rtmp_url = "rtmp://183.232.228.244:1935/live"
# Set the frame width, height, and frames per second (FPS)
frame_width = 1280
frame_height = 720

# frame_width = 1920
# frame_height = 1080
fps = 30

# Define the FFmpeg command to send the video stream
ffmpeg_command = [
    'ffmpeg',
    '-y',  # Overwrite output files without asking
    '-f', 'rawvideo',  # Input format
    '-reconnect', '1',
    '-reconnect_streamed', '1',
    '-reconnect_delay_max', '2',
    '-vcodec', 'rawvideo',
    '-pix_fmt', 'bgr24',  # Pixel format (OpenCV uses BGR by default)
    '-s', f'{frame_width}x{frame_height}',  # Frame size
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
    output_rtmp_url
]

# Start the FFmpeg process
# push_process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)

def initialize_ffmpeg():
    return subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)

# Process a single frame (this is the function you already have)
def process_single_frame(frame, frame_processors, source_image):
    for frame_processor in frame_processors:
        frame = frame_processor.process_frame(source_image, frame)
    return frame

# # Process multiple frames in parallel
# def process_frames(frames, frame_processors, source_image):
#     # Create a thread pool executor for parallel processing
#     with concurrent.futures.ThreadPoolExecutor() as executor:
#         # Submit each frame to be processed
#         futures = [executor.submit(process_single_frame, frame, frame_processors, source_image) for frame in frames]
        
#         # Collect the processed frames as they complete
#         processed_frames = [future.result() for future in concurrent.futures.as_completed(futures)]
        
#     return processed_frames

# Process multiple frames in parallel while maintaining order
def process_frames(frames, frame_processors, source_image):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Use map to process frames in order
        processed_frames = list(executor.map(process_single_frame, frames, [frame_processors]*len(frames), [source_image]*len(frames)))
    return processed_frames

# Thread function for capturing frames
def capture_frames(cap, frame_queue):
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_queue.put(frame)
    cap.release()

# Thread function for pushing frames to FFmpeg
def push_frames(frame_queue, processed_frame, frame_processors, source_image):
    while True:
        frame = frame_queue.get()
        if frame is None:
            break
        processed_frame = process_single_frame(frame, frame_processors, source_image)
        push_process.stdin.write(processed_frame.tobytes())
    push_process.stdin.close()
    push_process.wait()
    

def webcam():
    global push_process
    push_process = initialize_ffmpeg()

    if modules.globals.source_path is None:
        return
    
    while True:
        try:
            if modules.globals.source_path is None:
                return
            
            cap = cv2.VideoCapture(input_rtmp_url)
            if not cap.isOpened():
                print("无法打开视频流")
                return
            
            frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
            source_image = get_one_face(cv2.imread(modules.globals.source_path)) if modules.globals.source_path else None

            frame_buffer = []
            frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    print("读取帧失败，尝试重新连接")
                    cap.release()
                    time.sleep(1)
                    cap = cv2.VideoCapture(input_rtmp_url)
                    continue
                
                frame_buffer.append(frame)
                frame_count += 10
                if frame_count % 3000 == 0:  # 每处理 1000 帧，释放资源并重新初始化
                    print("\nprocessing")
                    
                # if frame_count % 3000 == 0:
                #     print("每处理3000帧，释放资源并重新初始化")
                #     push_process.stdin.close()
                #     push_process.wait()
                #     push_process = initialize_ffmpeg()

                if len(frame_buffer) >= 10:
                    processed_frames = process_frames(frame_buffer, frame_processors, source_image)
                    
                    for processed_frame in processed_frames:
                        push_process.stdin.write(processed_frame.tobytes())

                    frame_buffer = []

            if frame_buffer:
                processed_frames = process_frames(frame_buffer, frame_processors, source_image)
                for processed_frame in processed_frames:
                    push_process.stdin.write(processed_frame.tobytes())

            cap.release()
            push_process.stdin.close()
            push_process.wait()

        except Exception as e:
            print(f"出现错误: {e}")
            push_process.stdin.close()
            push_process.wait()
            push_process = initialize_ffmpeg()
            time.sleep(1)  # 等待2秒后重新尝试