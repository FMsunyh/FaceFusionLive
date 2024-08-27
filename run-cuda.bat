D:\code\FaceFusionLive\Dlab\python run.py --execution-provider cuda --execution-threads 60 --max-memory 60 --source "demo\images\masik.PNG"

python run.py --execution-provider cuda --execution-threads 60 --max-memory 60 --source "demo/images/masik.PNG" --rtmp_output "rtmp://120.241.153.43:1935/live"
--frame-processor face_swapper face_enhancer 