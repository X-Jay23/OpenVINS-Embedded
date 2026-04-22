#!/bin/bash
# start_sim.sh: One-key simulation script for OpenVINS (ROS-free version)

# =================================================================
# USER CONFIGURATION
# =================================================================

# Path to the project root (Auto-detected by default)
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Path to the estimator configuration YAML
CONFIG_PATH="$PROJECT_ROOT/config/euroc_mav/estimator_config.yaml"

# Path to the EuRoC MAV dataset (mav0 folder)
DATASET_PATH="$PROJECT_ROOT/dataset/euroc_mav/V1_01_easy/mav0"

# Path to the groundtruth CSV (Optional, set empty to skip evaluation)
GT_PATH="$PROJECT_ROOT/groundtruth/euroc_mav/V1_01_easy/data.csv"

# Whether to rebuild the project before running (true/false)
REBUILD=true

# =================================================================
# INTERNAL LOGIC (Do not modify unless needed)
# =================================================================

# ANSI Color codes for prettier output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    🚀 OpenVINS Simulation Automator       ${NC}"
echo -e "${GREEN}============================================${NC}"

# 1. Path Validation
if [ ! -d "$DATASET_PATH" ]; then
    echo -e "${RED}[Error] Dataset path not found: $DATASET_PATH${NC}"
    exit 1
fi

if [ ! -f "$CONFIG_PATH" ]; then
    echo -e "${RED}[Error] Config file not found: $CONFIG_PATH${NC}"
    exit 1
fi

# 2. Build Project
if [ "$REBUILD" = true ]; then
    echo -e "${YELLOW}[Sim] Compiling project...${NC}"
    mkdir -p "$PROJECT_ROOT/build"
    cd "$PROJECT_ROOT/build"
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)
    if [ $? -ne 0 ]; then
        echo -e "${RED}[Error] Compilation failed!${NC}"
        exit 1
    fi
    cd "$PROJECT_ROOT"
fi

# 3. Prepare Logs
LOG_DIR="$PROJECT_ROOT/logs/sim_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"
echo -e "${YELLOW}[Sim] Logs will be saved to: $LOG_DIR${NC}"

# 4. Cleanup IPC Resources (Shared Memory / Message Queues)
echo -e "${YELLOW}[Sim] Cleaning up IPC resources...${NC}"
rm -f /dev/mqueue/vins_imu_mq
rm -f /dev/shm/vins_cam_shm
rm -f /dev/shm/sem.vins_cam_sem
rm -f /tmp/vins_ready

# 5. Start VINS Core Process
echo -e "${GREEN}[Sim] Starting VINS process...${NC}"
cd "$PROJECT_ROOT/build"
./vins "$CONFIG_PATH" "$LOG_DIR" &
VINS_PID=$!

# Wait for system to initialize IPC
sleep 3

# 6. Start Resource Monitor
if [ -f "$PROJECT_ROOT/scripts/resource_monitor.py" ]; then
    echo -e "${YELLOW}[Sim] Starting resource monitor (PID=$VINS_PID)...${NC}"
    python3 "$PROJECT_ROOT/scripts/resource_monitor.py" $VINS_PID "$LOG_DIR/resource.csv" &
    MONITOR_PID=$!
fi

# 7. Start Data Producers (IMU & Camera)
echo -e "${GREEN}[Sim] Feeding dataset measurements...${NC}"
./imu_process "$DATASET_PATH" &
IMU_PID=$!

sleep 0.1 # Small delay for synchronization
./camera_process "$DATASET_PATH" &
CAM_PID=$!

# 8. Wait for completion
echo -e "${YELLOW}[Sim] Simulation running. Press Ctrl+C to stop manually.${NC}"
wait $IMU_PID
wait $CAM_PID

echo -e "${YELLOW}[Sim] Data stream finished. Shutting down VINS...${NC}"
kill -SIGINT $VINS_PID
wait $VINS_PID 2>/dev/null

# 9. Cleanup Monitor
if [ ! -z "$MONITOR_PID" ]; then
    kill -SIGTERM $MONITOR_PID 2>/dev/null
    wait $MONITOR_PID 2>/dev/null
fi

# 10. Trajectory Evaluation
if [ -n "$GT_PATH" ] && [ -f "$GT_PATH" ]; then
    echo -e "${GREEN}[Sim] Calculating accuracy metrics...${NC}"
    python3 "$PROJECT_ROOT/scripts/evaluate_and_plot.py" "$LOG_DIR" "$GT_PATH"
else
    echo -e "${YELLOW}[Sim] Ground truth not provided or not found, skipping evaluation.${NC}"
fi

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} ✅ Simulation Complete! ${NC}"
echo -e "${GREEN} Logs & Results: $LOG_DIR ${NC}"
echo -e "${GREEN}============================================${NC}"
