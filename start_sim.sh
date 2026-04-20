#!/bin/bash
# start_sim.sh: 一键启动脚本

# 1. 路径配置
# 动态获取脚本所在目录作为项目根目录
PROJECT_ROOT=$(cd "$(dirname "$0")"; pwd)
CONFIG_PATH="$PROJECT_ROOT/config/euroc_mav/estimator_config.yaml"
# 假设 mav0 在 openvins 目录的同级目录下
DATASET_PATH="$PROJECT_ROOT/../mav0"

# 2. 环境清理
echo "[Sim] 清理历史运行环境..."
pkill -9 vins 2>/dev/null
pkill -9 imu_process 2>/dev/null
pkill -9 camera_process 2>/dev/null
# 强制清理残留的共享内存文件，防止 Bus Error
rm -f /dev/shm/vins_* 2>/dev/null


# 4. 环境变量配置
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PROJECT_ROOT/build/src/ov_core:$PROJECT_ROOT/build/src/ov_init:$PROJECT_ROOT/build/src/ov_msckf

# 7. 启动主进程 (vins)
DATASET_PATH="/home/jay/Project/dataset/vicon_room1/V1_01_easy/V1_01_easy/mav0"
GT_PATH="$PROJECT_ROOT/groundtruth/V1_01_easy/data.csv"

# 2. 创建带时间戳的日志目录
LOG_DIR="$PROJECT_ROOT/logs/sim_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"
echo "[Sim] 日志目录: $LOG_DIR"

# 3. 编译工程
echo "[Sim] 正在编译工程..."
mkdir -p "$PROJECT_ROOT/build"
cd "$PROJECT_ROOT/build"
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

if [ $? -ne 0 ]; then
    echo "[Error] 编译失败！"
    exit 1
fi

# 4. 清理旧的 IPC 资源 (以防万一)
echo "[Sim] 清理 IPC 资源..."
rm -f /dev/mqueue/vins_imu_mq
rm -f /dev/shm/vins_cam_shm
rm -f /dev/shm/sem.vins_cam_sem
rm -f /tmp/vins_ready

# 5. 启动主进程 (vins)
echo "[Sim] 启动 VINS 主进程..."
$PROJECT_ROOT/build/vins "$CONFIG_PATH" &
./vins "$CONFIG_PATH" "$LOG_DIR" &
VINS_PID=$!

# 等待主进程就绪
sleep 5

# 8. 启动 IMU 进程和相机进程
if ! kill -0 $VINS_PID 2>/dev/null; then
    echo "[Error] VINS 主进程启动失败，请检查上方的错误信息。"
    exit 1
fi

# 6. 启动资源监测脚本
echo "[Sim] 启动资源监测 (PID=$VINS_PID)..."
python3 "$PROJECT_ROOT/scripts/resource_monitor.py" $VINS_PID "$LOG_DIR/resource.csv" &
MONITOR_PID=$!

sleep 10

# 7. 启动 IMU 进程和相机进程
echo "[Sim] 启动 IMU 进程和相机进程..."
$PROJECT_ROOT/build/imu_process "$DATASET_PATH" &
IMU_PID=$!

sleep 0.5
$PROJECT_ROOT/build/camera_process "$DATASET_PATH" &
CAM_PID=$!

# 9. 等待数据进程结束
# 8. 等待数据进程结束
echo "[Sim] 模拟运行中... (按 Ctrl+C 停止)"
wait $IMU_PID
wait $CAM_PID

echo "[Sim] 数据量读取完毕，等待 VINS 主进程处理积压数据..."
wait $VINS_PID

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
