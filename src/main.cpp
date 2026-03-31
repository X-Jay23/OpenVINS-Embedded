/**
 * @file main.cpp
 * @brief Standalone entry point for OpenVINS without ROS dependencies.
 * 
 * This file implements a manual data pump that reads data from the EuRoC MAV dataset,
 * synchronizes IMU and camera measurements, and feeds them into the VioManager.
 * It also handles trajectory logging to a file for evaluation.
 */

#include <iostream>
#include <memory>
#include <string>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <fstream>
#include <iomanip>

#include "core/VioManager.h"
#include "core/VioManagerOptions.h"
#include "utils/opencv_yaml_parse.h"
#include "utils/print.h"
#include "EuRoCDataLoader.h"
#include "state/State.h"

using namespace std;
using namespace ov_msckf;
using namespace ov_core;

int main(int argc, char **argv) {
    // 1. Check command line arguments
    if (argc < 3) {
        cerr << "[Error] Usage: ./vins_node <path_to_config.yaml> <path_to_dataset>" << endl;
        return EXIT_FAILURE;
    }
    string config_path = argv[1];
    string dataset_path = argv[2];

    cout << "========================================" << endl;
    cout << "  🚀 Starting Pure C++ VIO Firmware   " << endl;
    cout << "  Config : " << config_path << endl;
    cout << "  Dataset: " << dataset_path << endl;
    cout << "========================================" << endl;

    // 2. Initialize YAML Parser and Logger
    auto parser = std::make_shared<ov_core::YamlParser>(config_path);
    string verbosity = "INFO";
    parser->parse_config("verbosity", verbosity);
    ov_core::Printer::setPrintLevel(verbosity);

    // 3. Load VIO Parameters from YAML
    VioManagerOptions params;
    params.print_and_load(parser);
    if (!parser->successful()) {
        cerr << "[Error] Failed to parse all parameters in YAML!" << endl;
        return EXIT_FAILURE;
    }

    // 4. Create the core MSCKF Manager
    auto sys = std::make_shared<VioManager>(params);
    cout << "[System] VioManager initialized successfully." << endl;

    // 5. Load Dataset Metadata (IMU and Camera timestamps)
    EuRoCDataLoader loader(dataset_path);
    vector<ImuData> imu_data;
    if (!loader.load_imu_data(imu_data)) {
        cerr << "[Error] Failed to load IMU data!" << endl;
        return EXIT_FAILURE;
    }
    cout << "[System] Loaded " << imu_data.size() << " IMU measurements." << endl;

    map<double, string> cam0_filenames;
    if (!loader.load_cam_filenames(0, cam0_filenames)) {
        cerr << "[Error] Failed to load cam0 filenames!" << endl;
        return EXIT_FAILURE;
    }
    cout << "[System] Loaded " << cam0_filenames.size() << " cam0 images." << endl;

    map<double, string> cam1_filenames;
    bool has_cam1 = loader.load_cam_filenames(1, cam1_filenames);
    if (has_cam1) {
        cout << "[System] Loaded " << cam1_filenames.size() << " cam1 images." << endl;
    }

    // 6. Prepare Trajectory Logging (TUM format: timestamp p_x p_y p_z q_x q_y q_z q_w)
    ofstream traj_file("trajectory.txt");
    if (!traj_file.is_open()) {
        cerr << "[Error] Failed to open trajectory.txt for writing!" << endl;
        return EXIT_FAILURE;
    }

    // 7. Main Data Pump Loop
    // Synchronize IMU and Camera data: feed all IMU measurements up to the camera timestamp.
    size_t imu_idx = 0;
    for (auto const& cam_entry : cam0_filenames) {
        double cam_time = cam_entry.first;

        // Feed IMU data up to the current camera timestamp
        while (imu_idx < imu_data.size() && imu_data[imu_idx].timestamp <= cam_time) {
            sys->feed_measurement_imu(imu_data[imu_idx]);
            imu_idx++;
        }

        // Prepare Camera Data message (Mono or Stereo)
        CameraData message;
        message.timestamp = cam_time;
        
        // Add Cam0
        message.sensor_ids.push_back(0);
        message.images.push_back(loader.get_image(0, cam_entry.second));
        message.masks.push_back(cv::Mat::zeros(message.images[0].size(), CV_8UC1));

        // Add Cam1 if available and synchronized
        if (has_cam1 && cam1_filenames.count(cam_time)) {
            message.sensor_ids.push_back(1);
            message.images.push_back(loader.get_image(1, cam1_filenames[cam_time]));
            message.masks.push_back(cv::Mat::zeros(message.images[1].size(), CV_8UC1));
        }

        // Feed Camera measurement into the system
        sys->feed_measurement_camera(message);

        // 8. Log State if Initialized
        if (sys->initialized()) {
            auto state = sys->get_state();
            Eigen::Vector3d pos = state->_imu->pos();
            Eigen::Vector4d quat = state->_imu->quat();
            
            // Output trajectory to file
            traj_file << fixed << setprecision(15) << cam_time << " "
                      << pos.x() << " " << pos.y() << " " << pos.z() << " "
                      << quat.x() << " " << quat.y() << " " << quat.z() << " " << quat.w() << endl;
        }
    }

    // Cleanup
    traj_file.close();
    cout << "[System] VIO Firmware finished. Trajectory saved to trajectory.txt." << endl;
    return EXIT_SUCCESS;
}

