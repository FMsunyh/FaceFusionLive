D:\code\FaceFusionLive\Dlab\python run.py --execution-provider cuda --execution-threads 60 --max-memory 60 --source "demo\images\masik.PNG"

python run.py --execution-provider cuda --execution-threads 60 --max-memory 60 --source "demo/images/masik.PNG" --rtmp_output "rtmp://120.241.153.43:1935/live"
--frame-processor face_swapper face_enhancer 

python run.py --execution-provider cuda --execution-threads 60 --max-memory 60 --source "demo/images/hgf.jpg" --rtmp_output "rtmp://120.241.153.43:1935/live"
python run.py --execution-provider cuda --execution-threads 60 --max-memory 60 --source "demo/images/hgf.jpg" --rtmp_input "rtmp://183.232.228.244:1935/live_input" --rtmp_output "rtmp://183.232.228.244:1935/live1"


--source "demo/images/masik.PNG"
--source "demo/images/hgf.jpg"