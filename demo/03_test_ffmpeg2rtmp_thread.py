import cv2
import queue
import time
import threading
q=queue.Queue()
 
def Receive():
    print("start Reveive")
    # cap = cv2.VideoCapture("rtmp://183.232.228.244/live/videos/test2")
    cap = cv2.VideoCapture("rtsp://183.232.228.244:1935/live_input")
    ret, frame = cap.read()
    q.put(frame)
    frame_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    frame_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    print(frame_height, frame_width)
    retry_count=0
    while ret:
        ret, frame = cap.read()
        if not ret:
            retry_count += 1
            print(f"Failed to read frame, retrying... (attempt {retry_count})")
        else:
            print(f"Successful to read frame")
            retry_count = 0  # Reset retry count on successful read
            q.put(frame)
            
 
 
def Display():
     print("Start Displaying")
     while True:
        if q.empty() !=True:
            frame=q.get()
            cv2.imshow("frame1", frame)
        else:
            print("q is empty")
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
 
if __name__=='__main__':
    p1=threading.Thread(target=Receive)
    p2 = threading.Thread(target=Display)
    p1.start()
    p2.start()