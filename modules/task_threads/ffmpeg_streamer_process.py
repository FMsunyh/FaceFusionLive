import subprocess
from modules.logger import logger
import time

class FFmpegStreamerProcess:
    def __init__(self, width, height, fps, input_rtmp_url, output_rtmp_url):
        self.width = width
        self.height = height
        self.fps = fps
        self.input_rtmp_url = input_rtmp_url
        self.output_rtmp_url = output_rtmp_url
        self.process = None

    def start(self):
        """Start the FFmpeg process for streaming."""
        ffmpeg_command = [
            'ffmpeg',
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{self.width}x{self.height}',
            '-r', str(self.fps),
            '-i', '-',
            '-itsoffset', '10',  # 延迟音频
            '-i', self.input_rtmp_url,
            '-c:v', 'h264_nvenc',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-pix_fmt', 'yuv420p',
            '-preset', 'fast',
            '-f', 'flv',
            '-flvflags', 'no_duration_filesize',
            '-fps_mode', 'vfr',  # Replace -vsync with -fps_mode
            '-af', 'aresample=async=1',  # Resample audio
            '-shortest',
            '-max_interleave_delta', '100M',
            '-probesize', '100M',
            '-analyzeduration', '100M',
            self.output_rtmp_url
        ]
        self.process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)
        logger.info(f"Started FFmpeg streaming to: {self.output_rtmp_url}")

    def stop(self):
        """Stop the FFmpeg process."""
        try:
            if self.process.stdin:
                self.process.stdin.close()
                logger.info("FFmpeg stdin closed")
        except Exception as e:
            logger.warning(f"Exception while closing FFmpeg stdin: {e}")

        try:
            self.process.wait(timeout=3)
            logger.info("FFmpeg process ended normally")
        except subprocess.TimeoutExpired:
            logger.warning("Timeout waiting for FFmpeg process to end, trying to terminate")
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
                logger.info("FFmpeg process terminated")
            except Exception as e:
                logger.error(f"Exception while terminating FFmpeg process: {e}")

    def is_running(self):
        """Check if the FFmpeg process is still running."""
        # exit_code = self.process.poll()
        # if exit_code != 0:
        #     logger.error(f"FFmpeg process exited abnormally, exit code: {exit_code}")
        # else:
        #     logger.info("FFmpeg process exited normally")

        return self.process is not None and self.process.poll() is None

    def send_frame(self, frame):
        """Send a video frame to the FFmpeg process."""
        if self.process and self.is_running():
            self.process.stdin.write(frame)
            return True

        else:
            logger.error("FFmpeg process is not running or not ready to receive frames.")
            return False

    def send_frame_with_retry(self, frame, retry_count=3):
        """Push the frame to FFmpeg with retry mechanism."""
        if frame is None:
            logger.info(f"Push Streaming failed, frame is none")
            return False
        
        for attempt in range(retry_count):
            try:
                return self.send_frame(frame)
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
