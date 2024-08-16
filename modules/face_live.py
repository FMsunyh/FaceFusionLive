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

# 配置日志记录
# logging.basicConfig(filename='live_streaming.log', level=logging.INFO,
#                     format='%(asctime)s - %(levelname)s - %(message)s')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(processName)s: %(message)s',
    handlers=[
        logging.FileHandler("face_live.log"),
        logging.StreamHandler()
    ]
)

# 定义RTMP服务器的输入输出URL
input_rtmp_url = 'rtmp://120.241.153.43:1935/live111'
output_rtmp_url = "rtmp://120.241.153.43:1935/live"
frame_width = 1280
frame_height = 720
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

def initialize_ffmpeg():
    return subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)

def process_single_frame(frame, frame_processors, source_image):
    for frame_processor in frame_processors:
        frame = frame_processor.process_frame(source_image, frame)
    return frame

def process_frames(frames, frame_processors, source_image):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        processed_frames = list(executor.map(
            process_single_frame, frames, 
            [frame_processors]*len(frames), 
            [source_image]*len(frames)
        ))
    return processed_frames

def push_stream_with_retry(frame, retry_count=3):
    """推流并在失败时重试"""
    for attempt in range(retry_count):
        try:
            push_process.stdin.write(frame.tobytes())
            return True
        except BrokenPipeError:
            logging.error(f"推流失败，正在重试...（第 {attempt+1} 次）")
            time.sleep(1)  # 等待一段时间后重试
            if attempt == retry_count - 1:
                return False
        except Exception as e:
            logging.error(f"未知错误: {e}")
            retry_count += 1
            logging.error(f"推流失败，正在重试...（第 {attempt+1} 次）")
            time.sleep(1)
            if attempt == retry_count - 1:
                return False
    return False

def manage_stream():
    global push_process
    push_process = initialize_ffmpeg()
    
    try:
        while True:
            cap = cv2.VideoCapture(input_rtmp_url)
            if cap.isOpened():
                logging.info("打开视频流，正常...")
            else:
                logging.error("无法打开视频流，尝试重新连接...")
                time.sleep(1)
                continue

            frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
            source_image = get_one_face(cv2.imread(modules.globals.source_path)) if modules.globals.source_path else None

            frame_buffer = []
            frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    logging.error("读取帧失败，尝试重新连接..., sleep 1, break")
                    cap.release()
                    time.sleep(1)
                    break

                frame_buffer.append(frame)
                frame_count += 1



                # 处理并推送帧
                if len(frame_buffer) >= 10:

                    processed_frames = process_frames(frame_buffer, frame_processors, source_image)
                    for processed_frame in processed_frames:
                        if not push_stream_with_retry(processed_frame):
                            logging.error("推流失败，无法恢复")
                            break
                    frame_buffer = []
                
                    # try:
                    #     processed_frames = process_frames(frame_buffer, frame_processors, source_image)
                    #     for processed_frame in processed_frames:
                    #         push_process.stdin.write(processed_frame.tobytes())
                    #     frame_buffer = []
                    # except BrokenPipeError:
                    #     logging.error("推流过程中出现错误，尝试重新连接...")
                    #     push_process.stdin.close()
                    #     push_process.wait()
                    #     push_process = initialize_ffmpeg()

                if frame_count % 3000 == 0:
                    frame_count = 0
                    logging.info("心跳")

            cap.release()
    except Exception as e:
        logging.error(f"进程 {current_process().name} 出现错误: {e}")
    finally:
        push_process.stdin.close()
        push_process.wait()

def start_process():
    p = Process(target=manage_stream)
    p.start()
    logging.info("子进程启动...")
    return p

def webcam():
    while True:
        manage_stream()
    # while True:
    #     process = start_process()
    #     process.join()
    #     logging.info("子进程已退出，准备重启...")
    #     time.sleep(2)  # 避免频繁重启