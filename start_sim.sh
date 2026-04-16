#!/bin/bash
# start_sim.sh: 一键启动脚本

# 1. 路径配置
PROJECT_ROOT="/home/jay/Project/openvins"
CONFIG_PATH="$PROJECT_ROOT/config/euroc_mav/estimator_config.yaml"
DATASET_PATH="/home/jay/Project/dataset/vicon_room1/V1_01_easy/V1_01_easy/mav0"

# 2. 编译工程
echo "[Sim] 正在编译工程..."
mkdir -p "$PROJECT_ROOT/build"
cd "$PROJECT_ROOT/build"
cmake ..
make -j$(nproc)

if [ $? -ne 0 ]; then
    echo "[Error] 编译失败！"
    exit 1
fi

# 3. 清理旧的 IPC 资源 (以防万一)
echo "[Sim] 清理 IPC 资源..."
rm -f /dev/mqueue/vins_imu_mq
rm -f /dev/shm/vins_cam_shm
rm -f /dev/shm/sem.vins_cam_sem
rm -f /tmp/vins_ready

# 4. 启动主进程 (vins)
echo "[Sim] 启动 VINS 主进程..."
./vins "$CONFIG_PATH" &
VINS_PID=$!

# 等待主进程就绪
sleep 5

# 5. 启动 IMU 进程和相机进程
echo "[Sim] 启动 IMU 进程和相机进程..."
# IMU 进程通常比相机进程早启动一点
./imu_process "$DATASET_PATH" &
IMU_PID=$!

sleep 0.5 # 延迟 500ms 启动相机进程

./camera_process "$DATASET_PATH" &
CAM_PID=$!

# 6. 等待数据进程结束
echo "[Sim] 模拟运行中... (按 Ctrl+C 停止)"
wait $IMU_PID
wait $CAM_PID

echo "[Sim] 数据读取完毕，正在关闭主进程..."
kill -SIGINT $VINS_PID

echo "[Sim] 仿真任务圆满结束。"
