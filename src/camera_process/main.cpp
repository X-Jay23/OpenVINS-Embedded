/**
 * @file main.cpp
 * @brief Camera data process. Reads camera images and sends them via Shared Memory.
 */

#include <chrono>
#include <iostream>
#include <map>
#include <semaphore.h>
#include <string>
#include <thread>

#include "../EuRoCDataLoader.h"
#include "../common/DataTypes.h"
#include "../common/IpcManager.h"

using namespace std;
using namespace ov_core;

/**
 * @brief Entry point for the camera data process.
 * @param argc Number of arguments.
 * @param argv Argument vector: <path_to_dataset>
 */
int main(int argc, char **argv) {
  if (argc < 2) {
    cerr << "Usage: " << argv[0] << " <path_to_dataset>" << endl;
    return EXIT_FAILURE;
  }
  string dataset_path = argv[1];

  IpcManager ipc;
  sem_t *ready_sem = ipc.open_ready_sem(false);

  // Wait for VINS process to be ready
  cout << "[Camera Process] Waiting for VINS process readiness..." << endl;
  sem_wait(ready_sem);
  sem_post(ready_sem); // Relay the signal to next process

  ShmRingBuffer *ring_buffer = (ShmRingBuffer *)ipc.open_cam_shm(false, sizeof(ShmRingBuffer));
  sem_t *sem = ipc.open_cam_sem(false);

  EuRoCDataLoader loader(dataset_path);
  map<double, string> cam0_filenames, cam1_filenames;
  if (!loader.load_cam_filenames(0, cam0_filenames) || !loader.load_cam_filenames(1, cam1_filenames)) {
    cerr << "[Camera Process] Failed to load camera data from " << dataset_path << endl;
    return EXIT_FAILURE;
  }
  cout << "[Camera Process] Loaded " << cam0_filenames.size() << " stereo camera image pairs." << endl;

  // Ensure IMU process starts first
  this_thread::sleep_for(chrono::milliseconds(500));

  auto start_wall_time = chrono::steady_clock::now();
  double start_data_time = -1.0;

  for (const auto &entry : cam0_filenames) {
    double timestamp = entry.first;
    string filename0 = entry.second;

    if (cam1_filenames.find(timestamp) == cam1_filenames.end())
      continue;
    string filename1 = cam1_filenames[timestamp];

    if (start_data_time < 0) {
      start_data_time = timestamp;
      start_wall_time = chrono::steady_clock::now();
    }

    // Real-time wait
    double elapsed_data_time = timestamp - start_data_time;
    auto now = chrono::steady_clock::now();
    double elapsed_wall_time = chrono::duration<double>(now - start_wall_time).count();

    if (elapsed_data_time > elapsed_wall_time) {
      this_thread::sleep_for(chrono::duration<double>(elapsed_data_time - elapsed_wall_time));
    }

    cv::Mat image0 = loader.get_image(0, filename0);
    cv::Mat image1 = loader.get_image(1, filename1);
    if (image0.empty() || image1.empty())
      continue;

    // Force overwrite if full to ensure real-time performance
    if (((ring_buffer->write_idx + 1) % ShmRingBuffer::BUFFER_SIZE) == ring_buffer->read_idx) {
      ring_buffer->read_idx = (ring_buffer->read_idx + 1) % ShmRingBuffer::BUFFER_SIZE;
    }
    CameraDataPacket &packet0 = ring_buffer->packets[ring_buffer->write_idx];
    packet0.timestamp = timestamp;
    packet0.cam_id = 0;
    packet0.width = image0.cols;
    packet0.height = image0.rows;
    memcpy(packet0.data, image0.data, image0.cols * image0.rows);
    ring_buffer->write_idx = (ring_buffer->write_idx + 1) % ShmRingBuffer::BUFFER_SIZE;
    sem_post(sem);

    // Force overwrite if full to ensure real-time performance
    if (((ring_buffer->write_idx + 1) % ShmRingBuffer::BUFFER_SIZE) == ring_buffer->read_idx) {
      ring_buffer->read_idx = (ring_buffer->read_idx + 1) % ShmRingBuffer::BUFFER_SIZE;
    }
    CameraDataPacket &packet1 = ring_buffer->packets[ring_buffer->write_idx];
    packet1.timestamp = timestamp;
    packet1.cam_id = 1;
    packet1.width = image1.cols;
    packet1.height = image1.rows;
    memcpy(packet1.data, image1.data, image1.cols * image1.rows);
    ring_buffer->write_idx = (ring_buffer->write_idx + 1) % ShmRingBuffer::BUFFER_SIZE;
    sem_post(sem);
  }

  cout << "[Camera Process] Finished sending all camera data." << endl;
  sem_close(sem);
  sem_close(ready_sem);

  return EXIT_SUCCESS;
}
