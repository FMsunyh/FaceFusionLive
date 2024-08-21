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
from multiprocessing import Process

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
input_rtmp_url = 'rtmp://120.241.153.43:1935/live_input'
output_rtmp_url = "rtmp://120.241.153.43:1935/live"
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
push_process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)

def init(start: Callable[[], None], destroy: Callable[[], None]) -> ctk.CTk:
    global ROOT, PREVIEW

    ROOT = create_root(start, destroy)
    PREVIEW = create_preview(ROOT)

    return ROOT


def create_root(start: Callable[[], None], destroy: Callable[[], None]) -> ctk.CTk:
    global source_label, target_label, status_label

    ctk.deactivate_automatic_dpi_awareness()
    ctk.set_appearance_mode('system')
    ctk.set_default_color_theme(resolve_relative_path('ui.json'))

    root = ctk.CTk()
    root.minsize(ROOT_WIDTH, ROOT_HEIGHT)
    root.title(f'{modules.metadata.name} {modules.metadata.version} {modules.metadata.edition}')
    root.configure()
    root.protocol('WM_DELETE_WINDOW', lambda: destroy())

    source_label = ctk.CTkLabel(root, text=None)
    source_label.place(relx=0.1, rely=0.1, relwidth=0.3, relheight=0.25)

    target_label = ctk.CTkLabel(root, text=None)
    target_label.place(relx=0.6, rely=0.1, relwidth=0.3, relheight=0.25)

    source_button = ctk.CTkButton(root, text='Select a face', cursor='hand2', command=lambda: select_source_path())
    source_button.place(relx=0.1, rely=0.4, relwidth=0.3, relheight=0.1)

    target_button = ctk.CTkButton(root, text='Select a target', cursor='hand2', command=lambda: select_target_path())
    target_button.place(relx=0.6, rely=0.4, relwidth=0.3, relheight=0.1)

    keep_fps_value = ctk.BooleanVar(value=modules.globals.keep_fps)
    keep_fps_checkbox = ctk.CTkSwitch(root, text='Keep fps', variable=keep_fps_value, cursor='hand2', command=lambda: setattr(modules.globals, 'keep_fps', not modules.globals.keep_fps))
    keep_fps_checkbox.place(relx=0.1, rely=0.6)

    keep_frames_value = ctk.BooleanVar(value=modules.globals.keep_frames)
    keep_frames_switch = ctk.CTkSwitch(root, text='Keep frames', variable=keep_frames_value, cursor='hand2', command=lambda: setattr(modules.globals, 'keep_frames', keep_frames_value.get()))
    keep_frames_switch.place(relx=0.1, rely=0.65)

    # for FRAME PROCESSOR ENHANCER tumbler:
    enhancer_value = ctk.BooleanVar(value=modules.globals.fp_ui['face_enhancer'])
    enhancer_switch = ctk.CTkSwitch(root, text='Face Enhancer', variable=enhancer_value, cursor='hand2', command=lambda: update_tumbler('face_enhancer',enhancer_value.get()))
    enhancer_switch.place(relx=0.1, rely=0.7)

    keep_audio_value = ctk.BooleanVar(value=modules.globals.keep_audio)
    keep_audio_switch = ctk.CTkSwitch(root, text='Keep audio', variable=keep_audio_value, cursor='hand2', command=lambda: setattr(modules.globals, 'keep_audio', keep_audio_value.get()))
    keep_audio_switch.place(relx=0.6, rely=0.6)

    many_faces_value = ctk.BooleanVar(value=modules.globals.many_faces)
    many_faces_switch = ctk.CTkSwitch(root, text='Many faces', variable=many_faces_value, cursor='hand2', command=lambda: setattr(modules.globals, 'many_faces', many_faces_value.get()))
    many_faces_switch.place(relx=0.6, rely=0.65)

    nsfw_value = ctk.BooleanVar(value=modules.globals.nsfw)
    nsfw_switch = ctk.CTkSwitch(root, text='NSFW', variable=nsfw_value, cursor='hand2', command=lambda: setattr(modules.globals, 'nsfw', nsfw_value.get()))
    nsfw_switch.place(relx=0.6, rely=0.7)

    start_button = ctk.CTkButton(root, text='Start', cursor='hand2', command=lambda: select_output_path(start))
    start_button.place(relx=0.15, rely=0.80, relwidth=0.2, relheight=0.05)

    stop_button = ctk.CTkButton(root, text='Destroy', cursor='hand2', command=lambda: destroy())
    stop_button.place(relx=0.4, rely=0.80, relwidth=0.2, relheight=0.05)

    preview_button = ctk.CTkButton(root, text='Preview', cursor='hand2', command=lambda: toggle_preview())
    preview_button.place(relx=0.65, rely=0.80, relwidth=0.2, relheight=0.05)

    live_button = ctk.CTkButton(root, text='Live', cursor='hand2', command=lambda: start_webcam_preview())
    live_button.place(relx=0.40, rely=0.86, relwidth=0.2, relheight=0.05)

    status_label = ctk.CTkLabel(root, text=None, justify='center')
    status_label.place(relx=0.1, rely=0.9, relwidth=0.8)

    donate_label = ctk.CTkLabel(root, text='Deep Live Cam', justify='center', cursor='hand2')
    donate_label.place(relx=0.1, rely=0.95, relwidth=0.8)
    donate_label.configure(text_color=ctk.ThemeManager.theme.get('URL').get('text_color'))
    donate_label.bind('<Button>', lambda event: webbrowser.open('https://paypal.me/hacksider'))

    return root


def create_preview(parent: ctk.CTkToplevel) -> ctk.CTkToplevel:
    global preview_label, preview_slider

    preview = ctk.CTkToplevel(parent)
    preview.withdraw()
    preview.title('Preview')
    preview.configure()
    preview.protocol('WM_DELETE_WINDOW', lambda: toggle_preview())
    preview.resizable(width=False, height=False)

    preview_label = ctk.CTkLabel(preview, text=None)
    preview_label.pack(fill='both', expand=True)

    preview_slider = ctk.CTkSlider(preview, from_=0, to=0, command=lambda frame_value: update_preview(frame_value))

    return preview


def update_status(text: str) -> None:
    status_label.configure(text=text)
    ROOT.update()


def update_tumbler(var: str, value: bool) -> None:
    modules.globals.fp_ui[var] = value


def select_source_path() -> None:
    global RECENT_DIRECTORY_SOURCE, img_ft, vid_ft

    PREVIEW.withdraw()
    source_path = ctk.filedialog.askopenfilename(title='select an source image', initialdir=RECENT_DIRECTORY_SOURCE, filetypes=[img_ft])
    if is_image(source_path):
        modules.globals.source_path = source_path
        RECENT_DIRECTORY_SOURCE = os.path.dirname(modules.globals.source_path)
        image = render_image_preview(modules.globals.source_path, (200, 200))
        source_label.configure(image=image)
    else:
        modules.globals.source_path = None
        source_label.configure(image=None)


def select_target_path() -> None:
    global RECENT_DIRECTORY_TARGET, img_ft, vid_ft

    PREVIEW.withdraw()
    target_path = ctk.filedialog.askopenfilename(title='select an target image or video', initialdir=RECENT_DIRECTORY_TARGET, filetypes=[img_ft, vid_ft])
    if is_image(target_path):
        modules.globals.target_path = target_path
        RECENT_DIRECTORY_TARGET = os.path.dirname(modules.globals.target_path)
        image = render_image_preview(modules.globals.target_path, (200, 200))
        target_label.configure(image=image)
    elif is_video(target_path):
        modules.globals.target_path = target_path
        RECENT_DIRECTORY_TARGET = os.path.dirname(modules.globals.target_path)
        video_frame = render_video_preview(target_path, (200, 200))
        target_label.configure(image=video_frame)
    else:
        modules.globals.target_path = None
        target_label.configure(image=None)


def select_output_path(start: Callable[[], None]) -> None:
    global RECENT_DIRECTORY_OUTPUT, img_ft, vid_ft

    if is_image(modules.globals.target_path):
        output_path = ctk.filedialog.asksaveasfilename(title='save image output file', filetypes=[img_ft], defaultextension='.png', initialfile='output.png', initialdir=RECENT_DIRECTORY_OUTPUT)
    elif is_video(modules.globals.target_path):
        output_path = ctk.filedialog.asksaveasfilename(title='save video output file', filetypes=[vid_ft], defaultextension='.mp4', initialfile='output.mp4', initialdir=RECENT_DIRECTORY_OUTPUT)
    else:
        output_path = None
    if output_path:
        modules.globals.output_path = output_path
        RECENT_DIRECTORY_OUTPUT = os.path.dirname(modules.globals.output_path)
        start()


def render_image_preview(image_path: str, size: Tuple[int, int]) -> ctk.CTkImage:
    image = Image.open(image_path)
    if size:
        image = ImageOps.fit(image, size, Image.LANCZOS)
    return ctk.CTkImage(image, size=image.size)


def render_video_preview(video_path: str, size: Tuple[int, int], frame_number: int = 0) -> ctk.CTkImage:
    capture = cv2.VideoCapture(video_path)
    if frame_number:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    has_frame, frame = capture.read()
    if has_frame:
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if size:
            image = ImageOps.fit(image, size, Image.LANCZOS)
        return ctk.CTkImage(image, size=image.size)
    capture.release()
    cv2.destroyAllWindows()


def toggle_preview() -> None:
    if PREVIEW.state() == 'normal':
        PREVIEW.withdraw()
    elif modules.globals.source_path and modules.globals.target_path:
        init_preview()
        update_preview()
        PREVIEW.deiconify()


def init_preview() -> None:
    if is_image(modules.globals.target_path):
        preview_slider.pack_forget()
    if is_video(modules.globals.target_path):
        video_frame_total = get_video_frame_total(modules.globals.target_path)
        preview_slider.configure(to=video_frame_total)
        preview_slider.pack(fill='x')
        preview_slider.set(0)


def update_preview(frame_number: int = 0) -> None:
    if modules.globals.source_path and modules.globals.target_path:
        temp_frame = get_video_frame(modules.globals.target_path, frame_number)
        if modules.globals.nsfw == False:
            from modules.predicter import predict_frame
            if predict_frame(temp_frame):
                quit()
        for frame_processor in get_frame_processors_modules(modules.globals.frame_processors):
            temp_frame = frame_processor.process_frame(
                get_one_face(cv2.imread(modules.globals.source_path)),
                temp_frame
            )
        image = Image.fromarray(cv2.cvtColor(temp_frame, cv2.COLOR_BGR2RGB))
        image = ImageOps.contain(image, (PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT), Image.LANCZOS)
        image = ctk.CTkImage(image, size=image.size)
        preview_label.configure(image=image)


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
    


def webcam_preview():
    global push_process
    
    if modules.globals.source_path is None:
        return
    
    cap = cv2.VideoCapture(input_rtmp_url)
    if not cap.isOpened():
        print("无法打开视频流")
        return
    
    # Initialize the frame processors and face image
    frame_processors = get_frame_processors_modules(modules.globals.frame_processors)
    source_image = get_one_face(cv2.imread(modules.globals.source_path)) if modules.globals.source_path else None

    # Frame buffer to store multiple frames
    frame_buffer = []
    frame_count = 0

    while True:
        # Capture frames and add them to the buffer
        ret, frame = cap.read()
        if not ret:
            break
        frame_buffer.append(frame)
        frame_count += 10
        if frame_count % 3000 == 0:  # 每处理 1000 帧，释放资源并重新初始化
            print("processing")
        
        # When buffer is full, process all frames in parallel
        if len(frame_buffer) >= 10:  # Adjust buffer size as needed
            processed_frames = process_frames(frame_buffer, frame_processors, source_image)
            
            for processed_frame in processed_frames:
                push_process.stdin.write(processed_frame.tobytes())

            frame_buffer = []  # Clear buffer after processing

            # frame_count += 10
            # if frame_count % 1000 == 0:  # 每处理 1000 帧，释放资源并重新初始化
            #     # cap.release()
            #     push_process.stdin.close()
            #     push_process.wait()

            #     # cap = cv2.VideoCapture(input_rtmp_url)
            #     push_process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)
            #     print("每处理 1000 帧，释放资源并重新初始化")

    # Process remaining frames in the buffer
    if frame_buffer:
        processed_frames = process_frames(frame_buffer, frame_processors, source_image)
        for processed_frame in processed_frames:
            push_process.stdin.write(processed_frame.tobytes())

    cap.release()
    push_process.stdin.close()
    push_process.wait()

def start_webcam_preview():
    # 创建一个新进程来运行 webcam_preview
    p = Process(target=webcam_preview)
    p.start()