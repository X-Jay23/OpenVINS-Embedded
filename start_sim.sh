#!/bin/bash
# start_sim.sh: 一键启动脚本

# 1. 路径配置
PROJECT_ROOT=$(cd "$(dirname "$0")"; pwd)
CONFIG_PATH="$PROJECT_ROOT/config/euroc_mav/estimator_config.yaml"
DATASET_PATH="$PROJECT_ROOT/../mav0"
GT_PATH="$PROJECT_ROOT/groundtruth/V1_01_easy/data.csv"

# 2. 创建带时间戳的日志目录
LOG_DIR="$PROJECT_ROOT/logs/sim_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"
echo "[Sim] 日志目录: $LOG_DIR"

# # 3. 编译工程
# echo "[Sim] 正在编译工程..."
# mkdir -p "$PROJECT_ROOT/build"
cd "$PROJECT_ROOT/build"
# cmake -DCMAKE_TOOLCHAIN_FILE=../aarch64-toolchain.cmake ..
# make -j$(nproc)

# sudo mount -t nfs 192.168.137.1:/home/jay/nfs /mnt/nfs

# if [ $? -ne 0 ]; then
#     echo "[Error] 编译失败！"
#     exit 1
# fi

# 4. 清理旧的 IPC 资源 (以防万一)
echo "[Sim] 清理 IPC 资源..."
rm -f /dev/mqueue/vins_imu_mq
rm -f /dev/shm/vins_cam_shm
rm -f /dev/shm/sem.vins_cam_sem
rm -f /tmp/vins_ready

# 设置 CPU 为高性能模式
echo "[Sim] 设置 CPU 为高性能模式..."
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null

# 环境变量配置
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PROJECT_ROOT/build/src/ov_core:$PROJECT_ROOT/build/src/ov_init:$PROJECT_ROOT/build/src/ov_msckf

# 5. 启动主进程 (vins)
echo "[Sim] 启动 VINS 主进程 (绑定核心 0,1,2)..."
taskset -c 0,1,2 ./vins "$CONFIG_PATH" "$LOG_DIR" &
VINS_PID=$!

# 等待主进程就绪
sleep 5

# 6. 启动资源监测脚本
echo "[Sim] 启动资源监测 (绑定核心 3)..."
taskset -c 3 python3 "$PROJECT_ROOT/scripts/resource_monitor.py" $VINS_PID "$LOG_DIR/resource.csv" &
MONITOR_PID=$!

sleep 10

# 7. 启动 IMU 进程和相机进程
echo "[Sim] 启动 IMU 进程 (绑定核心 3)..."
# IMU 进程通常比相机进程早启动一点
taskset -c 3 ./imu_process "$DATASET_PATH" &
IMU_PID=$!

sleep 0.5 # 延迟 500ms 启动相机进程

taskset -c 3 ./camera_process "$DATASET_PATH" &
CAM_PID=$!

# 8. 等待数据进程结束
echo "[Sim] 模拟运行中... (按 Ctrl+C 停止)"
wait $IMU_PID
wait $CAM_PID

echo "[Sim] 数据读取完毕，正在关闭主进程..."
kill -SIGINT $VINS_PID

# 等待主进程退出
sleep 10

# 9. 停止资源监测
echo "[Sim] 停止资源监测..."
kill -SIGTERM $MONITOR_PID 2>/dev/null
wait $MONITOR_PID 2>/dev/null

# 10. 精度评估与绘图 
echo "[Sim] 计算轨迹精度并生成图表..."
python3 "$PROJECT_ROOT/scripts/evaluate_and_plot.py" "$LOG_DIR" "$GT_PATH"

echo ""
echo "[Sim] 仿真任务圆满结束。报告保存在: $LOG_DIR"