# OpenVINS-Embedded

[![Build Status](https://github.com/your-username/openvins-embedded/actions/workflows/build.yml/badge.svg)](https://github.com/your-username/openvins-embedded/actions)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

**OpenVINS-Embedded** is a high-performance, ROS-free fork of the [OpenVINS](https://github.com/rpng/open_vins) project. It is specifically refactored to run on resource-constrained embedded platforms (such as the Rockchip RK3568) by removing heavy middleware dependencies while maintaining state-of-the-art visual-inertial estimation accuracy.

---

## Key Features

1.  **ROS-Free Architecture**: Stripped of all ROS/ROS2 dependencies. Built with pure C++17 and standard CMake.
2.  **Embedded Optimization**: Tailored for ARM-based SoC (e.g., RK3568). Supports manual CPU pinning and performance-mode optimizations.
3.  **Modular Process Design**: Separates data acquisition (Camera/IMU processes) from the core estimation engine using high-speed IPC (Shared Memory & Message Queues).
4.  **Standalone Simulation**: Includes a built-in simulation runner that pumps data from EuRoC datasets for rapid algorithm verification.
5.  **Low Latency**: Optimized data pipeline for real-time performance on low-power hardware.

---

## System Architecture

The project employs a multi-process architecture to ensure timing stability and modularity:

*   **Data Producers**: Independent processes for Camera (Shared Memory) and IMU (Message Queues).
*   **VINS Core**: The main estimator node that consumes IPC data and produces pose estimates.
*   **Evaluation**: Integrated Python scripts for ATE/RPE calculation and resource utilization plotting.

---

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
├── logs/               # Generated trajectories and performance reports
├── start_sim.sh        # One-key simulation & evaluation script
└── CMakeLists.txt      # Master build configuration
```

---

## Performance Benchmarks

Tested on the EuRoC MAV dataset (V1_01_easy).

| Platform | Processor | OS | Avg. Latency / Frame |
| :--- | :--- | :--- | :--- |
| **Desktop Host** | Intel i7-11700KF | Ubuntu 22.04 | **~9.4 ms** (>100 FPS) |
| **Embedded Board** | Rockchip RK3568 | Debian 12 | **~25-35 ms** (Real-time) |

---

## Prerequisites & Installation

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

---

## Quick Start

To run a simulation using the EuRoC dataset:

1.  Open `start_sim.sh` and set your `DATASET_PATH` and `GT_PATH`.
2.  Execute the one-key script:
    ```bash
    ./start_sim.sh
    ```
3.  The script will automatically compile the code, run the simulation, monitor system resources, and generate a PDF performance report in the `logs/` directory.

---

## Future Work

*   [ ] Integration of hardware-accelerated feature extraction (using RK3568 RGA/NPU).
*   [ ] Support for live camera/IMU streams via V4L2 and SPI/I2C.
*   [ ] Real-world flight testing on RK3568-based drones.

---

## Credits & License

This project is a derivative of [OpenVINS](https://github.com/rpng/open_vins) developed by the **RPNG Group** at the University of Delaware.

Licensed under **GPL-3.0**.