# OpenVINS-Embedded

**OpenVINS-Embedded** is a high-performance, ROS-free fork of the [OpenVINS](https://github.com/rpng/open_vins) project. It is specifically refactored to run on resource-constrained embedded platforms (such as the Rockchip RK3568) by removing heavy middleware dependencies while maintaining state-of-the-art visual-inertial estimation accuracy.

## Branch Overview

*   **master**: Main branch optimized for Linux x86 desktop simulation and general development.
*   **dev_rk3568**: Active development branch focusing on **Rockchip RK3568** hardware optimizations.



## Key Features

1.  **ROS-Free Architecture**: Completely stripped of all ROS/ROS2 dependencies. Built with pure C++17 and standard CMake.
2.  **IPC-Based Simulation**: Replaces the bulky `rosbag play` mechanism with a lightweight Inter-Process Communication (IPC) architecture. Producer processes simulate real-time sensor streams, delivering data directly to the estimator core.
3.  **High-Efficiency Camera Process**:
    *   **Shared Memory**: Implements a zero-copy circular buffer in Shared Memory, avoiding the heavy serialization and memory copies found in ROS.
    *   **Direct Decoding**: Images are decoded directly into IPC buffers, bypassing standard filesystem overhead during simulation.



## System Architecture

The project employs a multi-process architecture to ensure timing stability and modularity:

*   **Data Producers**: Independent processes for Camera (Shared Memory) and IMU (Message Queues).
*   **VINS Core**: The main estimator node that consumes IPC data and produces pose estimates.
*   **Evaluation**: Integrated Python scripts for ATE calculation and resource utilization plotting.



## Project Structure

```text
openvins-embedded/
├── apps/               # Executable applications
│   ├── vins/           # Main VINS node & standalone simulation entry
│   ├── camera/         # Camera driver process (Shm producer)
│   └── imu/            # IMU driver process (Mq producer)
├── core/               # Algorithmic Library Modules
│   ├── ov_core/        # Core utilities and feature tracking
│   ├── ov_init/        # VIO state initialization
│   └── ov_msckf/       # MSCKF filter implementation
├── include/            # Shared Infrastructure (Headers & IPC)
│   ├── DataTypes.h     # Common data packets
│   ├── IpcManager.h    # Shared Memory & Semaphore management
│   └── EuRoCDataLoader.h # Dataset parser
├── config/             # YAML sensor and estimator configurations
├── scripts/            # Python tools for evaluation & resource monitoring
├── start_sim.sh        # One-key simulation & evaluation script
└── CMakeLists.txt      # Master build configuration
```



## Performance Benchmarks

### Environment

*   **OS**: Debian 12 (No-GUI)
*   **CPU**: RK3568
*   **RAM**: 2GB
*   **Build Type**: Release (-O3 -mcpu=cortex-a55)
*   **Dataset**: EuRoC MAV dataset (V1_01_medium)

| Metric                 | Value    |
| :--------------------- | :------- |
| Avg Frame Time         | 62.13 ms |
| Avg CPU Usage          | 131.76 % |
| Avg RSS Memory         | 67.18 MB |
| Mean ATE (Translation) | 0.0724 m |




## Prerequisites & Installation

For cross-compilation, ensure RK3568_SYSROOT in aarch64-toolchain.cmake points to your target device's library directory.

### Dependencies
Ensure you have the following libraries installed:
```bash
sudo apt-get update
sudo apt-get install libeigen3-dev libboost-all-dev libceres-dev libopencv-dev
```

### Build
```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```



## Quick Start

To run a simulation using the EuRoC dataset:

1.  Open `start_sim.sh` and set your `DATASET_PATH` and `GT_PATH`.
2.  Execute the one-key script:
    ```bash
    ./start_sim.sh
    ```
3.  The script will automatically compile the code, run the simulation, monitor system resources, and generate a PDF performance report in the `logs/` directory.



## Future Work

*   [ ] Integration of hardware-accelerated feature extraction (using RK3568 RGA/NPU).
*   [ ] Support for live camera/IMU streams via V4L2 and IIC.
*   [ ] Real-world flight testing on RK3568-based drones.



## Credits & License

This project is a derivative of [OpenVINS](https://github.com/rpng/open_vins) developed by the **RPNG Group** at the University of Delaware.

Licensed under **GPL-3.0**.
