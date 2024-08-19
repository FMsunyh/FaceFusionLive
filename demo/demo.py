import os
import webbrowser
import customtkinter as ctk
from typing import Callable, Tuple
import cv2
from PIL import Image, ImageOps
import subprocess
import time

import modules.globals
import modules.metadata
from modules.face_analyser import get_one_face
from modules.capturer import get_video_frame, get_video_frame_total
from modules.processors.frame.core import get_frame_processors_modules
from modules.utilities import is_image, is_video, resolve_relative_path

ROOT = None
ROOT_HEIGHT = 700
ROOT_WIDTH = 600

PREVIEW = None
PREVIEW_MAX_HEIGHT = 700
PREVIEW_MAX_WIDTH = 1200

RECENT_DIRECTORY_SOURCE = None
RECENT_DIRECTORY_TARGET = None
RECENT_DIRECTORY_OUTPUT = None

preview_label = None
preview_slider = None
source_label = None
target_label = None
status_label = None

img_ft, vid_ft = modules.globals.file_types


# RTMP server URL and stream key
input_rtmp_url = 'rtmp://120.241.153.43:1935/live111'
output_rtmp_url = "rtmp://120.241.153.43:1935/live"
# Set the frame width, height, and frames per second (FPS)
frame_width = 640
frame_height = 360
fps = 30

# Define the FFmpeg command to send the video stream
ffmpeg_command = [
    'ffmpeg',
    '-y',  # Overwrite output files without asking
    '-f', 'rawvideo',  # Input format
    '-vcodec', 'rawvideo',
    '-pix_fmt', 'bgr24',  # Pixel format (OpenCV uses BGR by default)
    '-s', f'{frame_width}x{frame_height}',  # Frame size
    '-r', str(fps),  # Frame rate
    '-i', '-',  # Input from stdin
    '-i', input_rtmp_url,  # 来自RTMP流的音频输入
    '-c:v', 'libx264',  # Video codec
    '-c:a', 'copy', # 音频编码器（直接复制音频，不重新编码）
    '-pix_fmt', 'yuv420p',  # Pixel format for output
    '-preset', 'ultrafast',  # Encoding speed
    '-f', 'flv',  # Output format
    '-flvflags', 'no_duration_filesize',
    output_rtmp_url
]

# Start the FFmpeg process
process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)

def webcam_preview():
    if modules.globals.source_path is None:
        # No image selected
        return
    global preview_label, PREVIEW
    
    cap = cv2.VideoCapture(input_rtmp_url)  # Use index for the webcam (adjust the index accordingly if necessary)    
    if not cap.isOpened():
        print("无法打开摄像头")
    else:
        # 获取视频帧的宽度和高度
        frame_width = int(cap.get(3))
        frame_height = int(cap.get(4))
    
        print(f"视频帧大小: 宽度 = {frame_width}, 高度 = {frame_height}")

    # cap = cv2.VideoCapture(0)  # Use index for the webcam (adjust the index accordingly if necessary)    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)  # Set the width of the resolution
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)  # Set the height of the resolution
    cap.set(cv2.CAP_PROP_FPS, 60)  # Set the frame rate of the webcam
    PREVIEW_MAX_WIDTH = 960
    PREVIEW_MAX_HEIGHT = 540

    preview_label.configure(image=None)  # Reset the preview image before startup

    PREVIEW.deiconify()  # Open preview window

    frame_processors = get_frame_processors_modules(modules.globals.frame_processors)

    source_image = None  # Initialize variable for the selected face image

    while True:
        start_time = time.time()
        
        ret, temp_frame = cap.read()
        if not ret:
            break
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"cad read processor: {execution_time} s")
        
        
        # Select and save face image only once
        if source_image is None and modules.globals.source_path:
            source_image = get_one_face(cv2.imread(modules.globals.source_path))

        # temp_frame = frame.copy()  #Create a copy of the frame

        start_time = time.time()
        for frame_processor in frame_processors:
            temp_frame = frame_processor.process_frame(source_image, temp_frame)

        end_time = time.time()
        execution_time = end_time - start_time
        print(f"frame processor: {execution_time} s")

        try:
            start_time = time.time()

            if temp_frame is not None:
                process.stdin.write(temp_frame.tobytes())
            
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"pull rtmp server processor: {execution_time} s") 
        except BrokenPipeError as e:
            print(e)
            print("Broken pipe error occurred. Please check the RTMP server and connection.")
    
        # finally:
        #     # Close the stdin to let FFmpeg know we are done
        #     print("Close the stdin to let FFmpeg know we are done.")
            
        #     process.stdin.close()
        #     process.wait()
    
        image = cv2.cvtColor(temp_frame, cv2.COLOR_BGR2RGB)  # Convert the image to RGB format to display it with Tkinter
        image = Image.fromarray(image)
        image = ImageOps.contain(image, (PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT), Image.LANCZOS)
        image = ctk.CTkImage(image, size=image.size)
        preview_label.configure(image=image)
        ROOT.update()

    cap.release()
    PREVIEW.withdraw()  # Close preview window when loop is finished