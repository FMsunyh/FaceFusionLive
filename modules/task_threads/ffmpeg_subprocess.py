
import subprocess
from modules.logger import logger


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
    # '-itsoffset', '2',   # 延迟音频
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
    
    # ffmpeg_command = [
    #     'ffmpeg',
    #     # '-hide_banner',  # 隐藏FFmpeg版本和版权信息
    #     '-y',  # Overwrite output files without asking
    #     '-f', 'rawvideo',  # Input format
    #     '-vcodec', 'rawvideo',
    #     '-pix_fmt', 'bgr24',  # Pixel format (OpenCV uses BGR by default)
    #     '-s', f'{width}x{height}',  # Frame size
    #     '-r', str(fps),  # Frame rate
    #     '-i', '-',  # Input from stdin
    #     '-i', input_rtmp_url,  # 来自RTMP流的音频输入
    #     # '-c:v', 'libx264',  # Video codec
    #     '-c:v', 'h264_nvenc',  # 使用 NVENC 进行视频编码
    #     '-c:a', 'copy', # 音频编码器（直接复制音频，不重新编码）
    #     '-pix_fmt', 'yuv420p',  # Pixel format for output
    #     # '-preset', 'ultrafast',  # Encoding speed
    #     '-preset', 'fast',  # NVENC 提供了一些预设选项，"fast" 比 "ultrafast" 更高效
    #     '-f', 'flv',  # Output format
    #     '-flvflags', 'no_duration_filesize',
    #     '-fps_mode', 'vfr',  # Replace -vsync with -fps_mod
    #     '-async', '1',        # Ensure audio sync
    #     '-shortest',          # Stop encoding when the shortest stream ends
    #     output_rtmp_url
    # ]

    ffmpeg_command = [
        'ffmpeg',
        '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f'{width}x{height}',
        '-r', str(fps),
        '-i', '-',
        '-itsoffset', '10',   # 延迟音频
        '-i', input_rtmp_url,
        '-c:v', 'h264_nvenc',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-pix_fmt', 'yuv420p',
        '-preset', 'fast',
        '-f', 'flv',
        '-flvflags', 'no_duration_filesize',
        # '-vsync', '1',              # Use vsync for synchronization
        '-fps_mode', 'vfr',  # Replace -vsync with -fps_mod
        # '-async', '10',
        '-af', 'aresample=async=1',  # Resample audio
        '-shortest',
        '-max_interleave_delta', '100M',
        '-probesize', '100M',
        '-analyzeduration', '100M',
        output_rtmp_url
    ]
    process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)
    logger.info(f"Started FFmpeg streaming to: {output_rtmp_url}")
    return process