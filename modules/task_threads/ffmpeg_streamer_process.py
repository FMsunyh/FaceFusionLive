import subprocess
from modules.logger import logger
import time
import threading
import io

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
            # '-fps_mode', 'vfr',  # Replace -vsync with -fps_mode
            '-af', 'aresample=async=1',  # Resample audio
            '-shortest',
            '-max_interleave_delta', '100M',
            '-probesize', '100M',
            '-analyzeduration', '100M',
            self.output_rtmp_url
        ]
        
        self.process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE, stderr=io.open('logs/ffmpeg.logs', 'w', buffering=1))
        
        # Start a thread to read stderr
        self.stderr_thread = threading.Thread(target=self._read_stderr)
        self.stderr_thread.start()
        
        logger.info(f"Started FFmpegStreamer Process: {self.output_rtmp_url}")

    def _read_stderr(self):
        """Continuously read from stderr."""
        while True:
            output = self.process.stderr.readline()
            if output == b'' and self.process.poll() is not None:
                break
            if output:
                logger.error(f"FFmpegStreamer stderr: {output.decode('utf-8')}")
                
    def stop(self):
        """Stop the FFmpeg process."""
        if self.process is None:
            logger.info("FFmpegStreamer Process is None")
            return
        
        try:
            if self.process.stdin:
                self.process.stdin.close()
                logger.info("FFmpegStreamer Process stdin closed")
        except Exception as e:
            logger.warning(f"Exception while closing FFmpeg stdin: {e}")

        try:
            self.process.wait(timeout=3)
            logger.info("FFmpegStreamer Process ended normally")
        except subprocess.TimeoutExpired:
            logger.warning("Timeout waiting for FFmpeg process to end, trying to terminate")
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
                logger.info("FFmpeg process terminated")
            except Exception as e:
                logger.error(f"Exception while terminating FFmpeg process: {e}")

    def is_running(self):
        """Check if the FFmpegStreamer process is still running."""
        
        # if not self.running:
        #     return False
        if self.process is None:
            return False
        # poll() returns None if the process is still running
        if self.process.poll() is None:
            return True
        else:
            # If poll() returns a value, the process has exited
            logger.info(f"FFmpegStreamer process exited with code: {self.process.poll()}")
            self.process = None  # Clear the process to reflect that it's no longer running
            return False

    def send_frame(self, frame):
        """Send a video frame to the FFmpeg process."""
        if self.process and self.is_running():
            self.process.stdin.write(frame)
            return True

        else:
            logger.error("FFmpegStreamer process is not running or not ready to receive frames.")
            return False

    def send_frame_with_retry(self, frame, retry_count=3):
        """Push the frame to FFmpeg with retry mechanism."""
        if frame is None:
            logger.info(f"FFmpegStreamer Push Streaming failed, frame is none")
            return False
        
        for attempt in range(retry_count):
            try:
                return self.send_frame(frame)
            except BrokenPipeError:
                logger.error(f"FFmpegStreamer Push Streaming failed, retrying... (attempt {attempt + 1})")
                time.sleep(1)
                if attempt == retry_count - 1:
                    return False
            except Exception as e:
                logger.error(f"FFmpegStreamer Error writing to FFmpeg: {e}")
                time.sleep(1)
                if attempt == retry_count - 1:
                    return False
        return False
