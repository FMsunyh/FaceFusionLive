# 配置FaceLive环境在Ubuntu22.04

## 下载代码
```vim 
git clone https://github.com/FMsunyh/FaceFusionLive.git
```

## 安装miniconda
下载
```sh
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
```
安装
```sh
bash Miniconda3-latest-Linux-x86_64.sh
```

Conda设置清华源
```bash
conda config --show channels

conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --set show_channel_urls yes
```
pip设置清华源
```
pip config list
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

## Python环境
```sh
conda create -n facelive python==3.10.14 -y
```

```sh
conda activate facelive
```

```sh
pip install -r requirements.txt
```

```sh
pip uninstall onnxruntime onnxruntime-gpu
pip install onnxruntime-gpu==1.16.3
```