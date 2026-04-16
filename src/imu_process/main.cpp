/**
 * @file main.cpp
 * @brief IMU data process. Reads IMU data from CSV and sends it via Message Queue.
 */

#include <chrono>
#include <iostream>
#include <mqueue.h>
#include <string>
#include <thread>
#include <vector>

#include "../EuRoCDataLoader.h"
#include "../common/DataTypes.h"
#include "../common/IpcManager.h"

using namespace std;
using namespace ov_core;

int main(int argc, char **argv) {
  if (argc < 2) {
    cerr << "Usage: " << argv[0] << " <path_to_dataset>" << endl;
    return EXIT_FAILURE;
  }
  string dataset_path = argv[1];

  IpcManager ipc;
  sem_t *ready_sem = ipc.open_ready_sem(false);

  // Wait for VINS process to be ready
  cout << "[IMU Process] Waiting for VINS process readiness..." << endl;
  sem_wait(ready_sem);
  sem_post(ready_sem); // Relay the signal to next process
  mqd_t imu_mq = mq_open(IMU_MQ_NAME, O_WRONLY);
  if (imu_mq == (mqd_t)-1) {
    perror("mq_open imu_process");
    throw std::runtime_error("Failed to open IMU message queue");
  }

  EuRoCDataLoader loader(dataset_path);
  vector<ImuData> imu_data;
  if (!loader.load_imu_data(imu_data)) {
    cerr << "[IMU Process] Failed to load IMU data from " << dataset_path << endl;
    return EXIT_FAILURE;
  }
  cout << "[IMU Process] Loaded " << imu_data.size() << " IMU measurements." << endl;

  // Wait for a short duration to ensure main process is ready (as requested in prompt)
  this_thread::sleep_for(chrono::milliseconds(200));

  auto start_wall_time = chrono::steady_clock::now();
  double start_data_time = -1.0;

  // 模拟真实时间发送IMU数据
  for (const auto &data : imu_data) {
    if (start_data_time < 0) {
      start_data_time = data.timestamp;
      start_wall_time = chrono::steady_clock::now();
    }

    // Real-time wait
    double elapsed_data_time = data.timestamp - start_data_time;
    auto now = chrono::steady_clock::now();
    double elapsed_wall_time = chrono::duration<double>(now - start_wall_time).count();

    if (elapsed_data_time > elapsed_wall_time) {
      this_thread::sleep_for(chrono::duration<double>(elapsed_data_time - elapsed_wall_time));
    }

    ImuDataPacket packet;
    packet.timestamp = data.timestamp;
    packet.wm[0] = data.wm[0];
    packet.wm[1] = data.wm[1];
    packet.wm[2] = data.wm[2];
    packet.am[0] = data.am[0];
    packet.am[1] = data.am[1];
    packet.am[2] = data.am[2];

    if (mq_send(imu_mq, (const char *)&packet, sizeof(packet), 0) == -1) {
      perror("mq_send");
      break;
    }
  }

  cout << "[IMU Process] Finished sending all IMU data." << endl;
  mq_close(imu_mq);
  sem_close(ready_sem);

  return EXIT_SUCCESS;
}
