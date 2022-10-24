FROM nvidia/cuda:11.3.1-cudnn8-devel-ubuntu20.04

WORKDIR /app

RUN apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y --no-install-recommends python3 python3-pip wget pkg-config git llvm-12 llvm-12-dev python3-dev python3-pip python3-setuptools python3-wheel python3-opencv \
    gcc libtinfo-dev zlib1g-dev build-essential cmake libedit-dev libxml2-dev libomp-dev ffmpeg && \
    apt clean

COPY requirements.txt requirements.txt

RUN python3 -m pip install pip --upgrade
RUN python3 -m pip install -r requirements.txt

RUN wget "https://dl.k8s.io/release/v1.23.0/bin/linux/amd64/kubectl" -O /usr/bin/kubectl
RUN chmod +x /usr/bin/kubectl

#build tvm
RUN cd /root && \
    git clone --recursive https://github.com/apache/tvm tvm && \
    cd tvm && git checkout 4babd36481b7108bf50df5c3b256c95c0d9c3291 && \
    git submodule init && \
    git submodule update && \
    mkdir build && \
    cp cmake/config.cmake build && \
    cd build && \
    sed -i 's/set(USE_CUDA OFF)/set(USE_CUDA \/usr\/local\/cuda)/g' config.cmake && \
    sed -i 's/set(USE_CUDNN OFF)/set(USE_CUDNN ON)/g' config.cmake && \
    sed -i 's/set(USE_OPENMP OFF)/set(USE_OPENMP intel)/g' config.cmake && \
    sed -i 's/set(USE_LLVM OFF)/set(USE_LLVM \/usr\/bin\/llvm-config-12)/g' config.cmake && \
    cmake .. && \
    make -j `nproc` && \
    cd ../python && \
    python3 setup.py install && cd ../.. && rm -rf tvm

COPY main_processes ./main_processes
COPY nxs_libs ./nxs_libs
COPY nxs_types ./nxs_types
COPY nxs_utils ./nxs_utils
COPY configs.py .
COPY scripts ./scripts


