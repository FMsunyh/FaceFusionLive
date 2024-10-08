import os
import sys
sys.path
parent_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_directory)

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

# 配置日志记录
# logging.basicConfig(filename='live_streaming.log', level=logging.INFO,
#                     format='%(asctime)s - %(levelname)s - %(message)s')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(processName)s: %(message)s',
    handlers=[
        logging.FileHandler(r"logs\\app.log"),
        logging.StreamHandler()
    ]
)

# # 定义RTMP服务器的输入输出URL
# input_rtmp_url = 'rtmp://183.232.228.244:1935/live_input'
# output_rtmp_url = "rtmp://183.232.228.244:1935/live"
# frame_width = 1280
# frame_height = 720
# fps = 30

def measure_runtime(start_time):
    """
    记录程序的运行时长，并以小时、分钟、秒的格式输出。
    """
    # 记录结束时间
    end_time = time.time()

    # 计算运行时长
    elapsed_time = end_time - start_time

    # 将秒数转换为时分秒
    hours, remainder = divmod(elapsed_time, 3600)
    minutes, seconds = divmod(remainder, 60)

    logging.info(f"程序运行时长: {int(hours)} 小时 {int(minutes)} 分钟 {seconds:.2f} 秒")

def process_single_frame(frame, frame_processors, source_image):
    for frame_processor in frame_processors:
        frame = frame_processor.process_frame(source_image, frame)
    return frame

def process_frames(frames, frame_processors, source_image):
    # with concurrent.futures.ThreadPoolExecutor() as executor:
    #     processed_frames = list(executor.map(
    #         process_single_frame, frames, 
    #         [frame_processors]*len(frames), 
    #         [source_image]*len(frames)
    #     ))
    # return processed_frames

    time.sleep(0.)
    return frames


def start_ffmpeg_process(width, height, fps,input_rtmp_url, output_rtmp_url):
    """启动FFmpeg进程，用于推送处理后的视频流"""
    # Define the FFmpeg command to send the video stream
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
        '-max_interleave_delta', '100M',
        '-probesize', '100M',
        '-analyzeduration', '100M',
        output_rtmp_url
    ]
    
    process = subprocess.Popen(ffmpeg_command, 
                               stdin=subprocess.PIPE)
    logging.info(f"启动FFmpeg推流至：{output_rtmp_url}")
    return process

def open_input_stream(input_rtmp_url):
    """打开输入RTMP流"""
    cap = cv2.VideoCapture(input_rtmp_url)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开输入流：{input_rtmp_url}")
    return cap


def push_stream_with_retry(process, frame, retry_count=3):
    """推流并在失败时重试"""
    for attempt in range(retry_count):
        try:
            process.stdin.write(frame.tobytes())
            return True
        except BrokenPipeError:
            logging.error(f"推流失败，正在重试...（第 {attempt+1} 次）")
            time.sleep(1)  # 等待一段时间后重试
            if attempt == retry_count - 1:
                return False
        except Exception as e:
            logging.error(f"写入FFmpeg时发生错误: {e}")
            retry_count += 1
            logging.error(f"推流失败，正在重试...（第 {attempt+1} 次）")
            time.sleep(1)
            if attempt == retry_count - 1:
                return False
    return False

def cleanup_resources(cap, process):
    """清理资源，关闭视频流和FFmpeg进程"""
    try:
        if cap.isOpened():
            cap.release()
            logging.info("视频流已释放")
    except Exception as e:
        logging.warning(f"释放视频流时发生异常：{e}")
    
    try:
        if process.stdin:
            process.stdin.close()
            logging.info("FFmpeg stdin 已关闭")
    except Exception as e:
        logging.warning(f"关闭FFmpeg stdin时发生异常：{e}")
    
    try:
        # 尝试正常等待进程结束
        process.wait(timeout=5)
        logging.info("FFmpeg进程已正常结束")
    except subprocess.TimeoutExpired:
        logging.warning("等待FFmpeg进程结束超时，尝试强制终止")
        try:
            process.terminate()
            process.wait(timeout=5)
            logging.info("FFmpeg进程已被强制终止")
        except Exception as e:
            logging.error(f"强制终止FFmpeg进程时发生异常：{e}")
    except Exception as e:
        logging.warning(f"等待FFmpeg进程结束时发生异常：{e}")

    logging.info("已释放全部资源")

def handle_streaming(cap, process, face_source_path, frame_processors):
    """处理视频流，从输入捕获帧，处理后通过FFmpeg推流"""

    logging.info(f"人脸: {face_source_path}")
    # frame_processors = get_frame_processors_modules(frame_processors)
    frame_processors = None
    source_image = cv2.imread(face_source_path)
    # source_image = get_one_face(cv2.imread(face_source_path))

    frame_buffer = []
    frame_count = 0
    exception_count = 0
    start_time = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            logging.error("读取帧失败，尝试重新连接..., sleep 1, break")
            time.sleep(1)
            break

        frame_buffer.append(frame)
        frame_count += 1
        exception_count += 1
        # 处理并推送帧
        if len(frame_buffer) >= 10:
            processed_frames = process_frames(frame_buffer, frame_processors, source_image)
            for processed_frame in processed_frames:
                if not push_stream_with_retry(process, processed_frame):
                    logging.error("推流失败，无法恢复")
                    break
            frame_buffer = []

        if frame_count % 3000 == 0:
            frame_count = 0
            measure_runtime(start_time)
            logging.info("心跳正常...")

        if process.poll() is not None:
            exit_code = process.poll()
            if exit_code != 0:
                # 捕获并记录FFmpeg的错误信息
                ffmpeg_error = process.stderr.read()
                logging.error(f"FFmpeg进程异常退出，退出码：{exit_code}")
                logging.error(f"FFmpeg错误信息：{ffmpeg_error}")
            else:
                logging.info("FFmpeg进程已正常退出")
            break

        # if time.time() - last_frame_time > 10:
        #     logging.warning("超过10秒未接收到新帧")
        #     break
        # if exception_count % 300000 == 0:
        #     exception_count = 0
        #     logging.warning("假设异常退出")
        #     break

def stream_worker(input_rtmp_url, output_rtmp_url, face_source_path, frame_processors, restart_interval=5):
    """RTMP流处理工作进程，包含重试机制"""
    while True:
        try:
            logging.info(f"开始处理流：{input_rtmp_url}")
            cap = open_input_stream(input_rtmp_url)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25  # 默认帧率为25
            
            process = start_ffmpeg_process(width, height, fps, input_rtmp_url, output_rtmp_url)
            handle_streaming(cap, process, face_source_path, frame_processors)
            logging.info(f"处理结束")

        except Exception as e:
            logging.exception(f"处理流时发生错误：{e}")
        finally:
            cleanup_resources(cap, process)
            logging.info(f"等待 {restart_interval} 秒后重试...")
            time.sleep(restart_interval)

def manage_streams(streams):
    """管理多个RTMP流，每个流使用一个独立的进程"""
    processes = []
    
    for input_url, output_url , face_source_path, frame_processors in streams:
        p = multiprocessing.Process(target=stream_worker, args=(input_url, output_url, face_source_path, frame_processors))
        p.daemon = True
        p.start()
        processes.append(p)
        logging.info(f"已启动进程 {p.name} 处理流：{input_url} -> {output_url}")
    
    try:
        while True:
            for i, p in enumerate(processes):
                if not p.is_alive():
                    logging.warning(f"检测到进程 {p.name} 已退出，正在重启...")
                    input_url, output_url, face_source_path, frame_processors = streams[i]
                    new_p = multiprocessing.Process(target=stream_worker, args=(input_url, output_url, face_source_path, frame_processors))
                    new_p.daemon = True
                    new_p.start()
                    processes[i] = new_p
                    logging.info(f"已重启进程 {new_p.name} 处理流：{input_url} -> {output_url}")
            time.sleep(5)
            
    except KeyboardInterrupt:
        logging.info("检测到中断信号，正在关闭所有进程...")
        for p in processes:
            p.terminate()
            p.join()
        logging.info("所有进程已关闭。程序退出。")


def webcam():
    frame_processors = modules.globals.frame_processors
    streams = [
        ('rtmp://183.232.228.244:1935/live_input', 'rtmp://183.232.228.244:1935/live', "demo/images/face.png", frame_processors),
    ]
    manage_streams(streams)


if __name__ == "__main__":
    webcam()