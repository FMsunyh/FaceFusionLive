import cv2
import numpy as np
import subprocess
import time
# RTMP server URL and stream key
input_rtmp_url = 'rtmp://120.241.153.43:1935/live_input'
output_rtmp_url = "rtmp://120.241.153.43:1935/live"

# Set the frame width, height, and frames per second (FPS)
cap = cv2.VideoCapture(input_rtmp_url)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS) or 25  # Default to 25 fps if unknown

# Define the FFmpeg command to send the video stream
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
    '-c:v', 'h264_nvenc',
    '-c:a', 'aac',
    '-b:a', '128k',
    '-pix_fmt', 'yuv420p',
    '-preset', 'fast',
    '-f', 'flv',
    '-flvflags', 'no_duration_filesize',
    # '-fps_mode', 'vfr',  # Replace -vsync with -fps_mod
    '-async', '1',        # Ensure audio sync
    '-shortest',          # Stop encoding when the shortest stream ends
    '-max_interleave_delta', '100M',
    '-probesize', '100M',
    '-analyzeduration', '100M',
    # '-loglevel', 'debug', # Debugging level
    output_rtmp_url
]

# Start the FFmpeg process
process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)



while(True):
    # Capture frame-by-frame
    ret, frame = cap.read()
    # frame = cv2.resize(frame, (frame_width, frame_height))
    time.sleep(0.01)
    process.stdin.write(frame.tobytes())

    # Our operations on the frame come here
    # gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Display the resulting frame
    # cv2.imshow('frame',frame)
    # if cv2.waitKey(1) & 0xFF == ord('q'):
    #     break
    
while True:
    # Loop to send frames to FFmpeg
    for i in range(300):  # Stream for 10 seconds if FPS is 30
        # Generate a dummy frame (replace with your actual image frames)
        frame = np.random.randint(0, 256, (frame_height, frame_width, 3), dtype=np.uint8)
        
        # Write the frame to FFmpeg's stdin
        process.stdin.write(frame.tobytes())

# Close the stdin to let FFmpeg know we are done
process.stdin.close()
process.wait()
