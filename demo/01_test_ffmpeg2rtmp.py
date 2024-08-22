import os
import sys
parent_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_directory)
import cv2
import subprocess
import time
import datetime

# RTMP server URL and stream key
input_rtmp_url = 'rtmp://120.241.153.43:1935/live_input'
output_rtmp_url = "rtmp://120.241.153.43:1935/demo"

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
        # '-fps_mode', 'vfr',  # Replace -vsync with -fps_mod
        '-async', '1',        # Ensure audio sync
        '-shortest',          # Stop encoding when the shortest stream ends
        '-max_interleave_delta', '100M',
        '-probesize', '100M',
        '-analyzeduration', '100M',
        output_rtmp_url
    ]
    
    process = subprocess.Popen(ffmpeg_command, 
                               stdin=subprocess.PIPE)
    print(f"启动FFmpeg推流至：{output_rtmp_url}")
    return process

def add_timestamp_to_image(image):
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

def webcam():
    cap = cv2.VideoCapture(input_rtmp_url)  # Use index for the webcam (adjust the index accordingly if necessary)    
    if not cap.isOpened():
        print("无法打开摄像头")
    else:
        # 获取视频帧的宽度和高度
        frame_width = int(cap.get(3))
        frame_height = int(cap.get(4))
    
        print(f"视频帧大小: 宽度 = {frame_width}, 高度 = {frame_height}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25  # 默认帧率为25

    process = start_ffmpeg_process(width, height, fps, input_rtmp_url, output_rtmp_url)
    while True:
        start_time = time.time()
        
        ret, temp_frame = cap.read()
        if not ret:
            break
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"cad read processor: {execution_time} s")

        start_time = time.time()

        temp_frame = add_timestamp_to_image(temp_frame)

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
    
        # image = cv2.cvtColor(temp_frame, cv2.COLOR_BGR2RGB)  # Convert the image to RGB format to display it with Tkinter
        # cv2.imshow('frame',temp_frame)
        # if cv2.waitKey(1) & 0xFF == ord('q'):
        #     break

    cap.release()

if __name__ == "__main__":

    webcam()