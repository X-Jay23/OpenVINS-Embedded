#include <atomic>
#include <cerrno>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mqueue.h>
#include <semaphore.h>
#include <thread>

#include "../common/DataTypes.h"
#include "../common/IpcManager.h"
#include "../common/ThreadSafeQueue.h"
#include "../common/PerformanceLogger.h"
#include "core/VioManager.h"
#include "core/VioManagerOptions.h"
#include "state/State.h"
#include "utils/opencv_yaml_parse.h"
#include "utils/print.h"

using namespace std;
using namespace ov_core;
using namespace ov_msckf;

// Global flag to stop threads
atomic<bool> stop_flag(false);

/**
 * @brief Signal handler to ensure graceful shutdown.
 * @param signum Signal number.
 */
void signalHandler(int signum) {
  cout << "\n[VINS Process] Interrupt signal (" << signum << ") received.\n";
  stop_flag = true;
}

/**
 * @brief Thread for reading IMU data from Message Queue.
 * @param mq IMU message queue descriptor.
 * @param queue Output queue to store received IMU data.
 */
void imu_read_thread(mqd_t mq, ThreadSafeQueue<ImuDataPacket> *queue) {
  while (!stop_flag) {
    ImuDataPacket packet;
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_sec += 1; // Wait for at most 1 second

    ssize_t bytes_read = mq_timedreceive(mq, (char *)&packet, sizeof(packet), NULL, &ts);
    if (bytes_read > 0) {
      queue->push(packet);
    } else if (bytes_read == -1 && errno != ETIMEDOUT && errno != EINTR) {
      perror("mq_timedreceive");
      break;
    }
  }
  cout << "[VINS Process] IMU read thread stopped." << endl;
}

/**
 * @brief Thread for reading Camera data from Shared Memory.
 * @param sem Camera semaphore pointer.
 * @param ring_buffer Pointer to the shared memory ring buffer.
 * @param queue Output queue to store received camera data.
 */
void camera_read_thread(sem_t *sem, ShmRingBuffer *ring_buffer, ThreadSafeQueue<CameraDataPacket> *queue) {
  while (!stop_flag) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_sec += 1; // Wait for at most 1 second

    if (sem_timedwait(sem, &ts) == 0) {
      if (ring_buffer->read_idx != ring_buffer->write_idx) {
        CameraDataPacket packet = ring_buffer->packets[ring_buffer->read_idx];
        queue->push(packet);
        ring_buffer->read_idx = (ring_buffer->read_idx + 1) % ShmRingBuffer::BUFFER_SIZE;
      }
    } else if (errno != ETIMEDOUT && errno != EINTR) {
      perror("sem_timedwait");
      break;
    }
  }
  cout << "[VINS Process] Camera read thread stopped." << endl;
}

int main(int argc, char **argv) {
  if (argc < 3) {
    cerr << "Usage: " << argv[0] << " <path_to_config.yaml> <log_dir>" << endl;
    return EXIT_FAILURE;
  }
  string config_path = argv[1];
  string log_dir = argv[2];

  signal(SIGINT, signalHandler);

  // Initialize OpenVINS VioManager
  auto parser = std::make_shared<ov_core::YamlParser>(config_path);
  string verbosity = "INFO";
  parser->parse_config("verbosity", verbosity);
  ov_core::Printer::setPrintLevel(verbosity);

  VioManagerOptions params;
  params.print_and_load(parser);
  auto sys = std::make_shared<VioManager>(params);
  cout << "[VINS Process] VioManager initialized." << endl;

  // Setup IPC
  IpcManager ipc;
  mqd_t imu_mq = ipc.open_imu_mq(true);
  ShmRingBuffer *ring_buffer = (ShmRingBuffer *)ipc.open_cam_shm(true, sizeof(ShmRingBuffer));
  ring_buffer->write_idx = 0;
  ring_buffer->read_idx = 0;
  sem_t *sem = ipc.open_cam_sem(true);
  sem_t *ready_sem = ipc.open_ready_sem(true);

  // Signal readiness via semaphore
  sem_post(ready_sem);

  // Queues for data buffering
  ThreadSafeQueue<ImuDataPacket> imu_queue;
  ThreadSafeQueue<CameraDataPacket> camera_queue;

  // Start read threads
  thread imu_thread(imu_read_thread, imu_mq, &imu_queue);
  thread cam_thread(camera_read_thread, sem, ring_buffer, &camera_queue);

  // Trajectory logging
  ofstream traj_file(log_dir + "/trajectory.txt");
  PerformanceLogger perf_logger;

  cout << "[VINS Process] System ready. Waiting for data..." << endl;

  // Buffer some IMU data before starting
  this_thread::sleep_for(chrono::seconds(1));

  // Main processing loop
  double last_imu_time = -1.0;
  while (!stop_flag) {
    // 1. Wait for at least one camera pair to be available
    if (camera_queue.size() < 2) {
      this_thread::sleep_for(chrono::milliseconds(1));
      continue;
    }

    // 2. Get the next camera pair timestamp (without popping yet)
    auto p1_opt = camera_queue.try_pop();
    auto p2_opt = camera_queue.try_pop();
    if (!p1_opt || !p2_opt)
      continue;

    auto &p1 = *p1_opt;
    auto &p2 = *p2_opt;

    if (abs(p1.timestamp - p2.timestamp) > 1e-6) {
      // Not a pair, skip p1 and try again with p2 as the potential first of next pair
      continue;
    }
    double cam_time = p1.timestamp;

    // 3. Feed all IMU data up to this camera timestamp
    // We might need to wait for IMU data to arrive if it's lagging
    bool imu_caught_up = (last_imu_time != -1.0 && last_imu_time >= cam_time);
    while (!stop_flag && !imu_caught_up) {
      if (imu_queue.empty()) {
        this_thread::sleep_for(chrono::milliseconds(1));
      }
      while (!imu_queue.empty()) {
        auto imu_packet = imu_queue.pop();
        ImuData data;
        data.timestamp = imu_packet.timestamp;
        data.wm << imu_packet.wm[0], imu_packet.wm[1], imu_packet.wm[2];
        data.am << imu_packet.am[0], imu_packet.am[1], imu_packet.am[2];
        sys->feed_measurement_imu(data);
        last_imu_time = data.timestamp;
        if (last_imu_time >= cam_time) {
          imu_caught_up = true;
        }
      }
    }

    // 4. Feed the camera pair
    CameraData message;
    message.timestamp = cam_time;
    message.sensor_ids.push_back(p1.cam_id);
    message.images.push_back(cv::Mat(p1.height, p1.width, CV_8UC1, p1.data).clone());
    message.masks.push_back(cv::Mat::zeros(p1.height, p1.width, CV_8UC1));

    message.sensor_ids.push_back(p2.cam_id);
    message.images.push_back(cv::Mat(p2.height, p2.width, CV_8UC1, p2.data).clone());
    message.masks.push_back(cv::Mat::zeros(p2.height, p2.width, CV_8UC1));

    perf_logger.start_frame();
    sys->feed_measurement_camera(message);
    perf_logger.end_frame();

    // 5. Log status and trajectory
    if (sys->initialized()) {
      static bool first_init = true;
      if (first_init) {
        cout << "[VINS Process] System Initialized!" << endl;
        first_init = false;
      }
      std::shared_ptr<ov_msckf::State> state = sys->get_state();
      Eigen::Vector3d pos = state->_imu->pos();
      Eigen::Vector4d quat = state->_imu->quat();
      traj_file << fixed << setprecision(15) << message.timestamp << " " << pos.x() << " " << pos.y() << " " << pos.z() << " " << quat.x()
                << " " << quat.y() << " " << quat.z() << " " << quat.w() << endl;
      traj_file.flush();
    } else {
      static int fail_count = 0;
      if (++fail_count % 20 == 0) {
        cout << "[VINS Process] Waiting for initialization... (Camera timestamp: " << fixed << setprecision(3) << message.timestamp << ")"
             << endl;
      }
    }
  }

  // Cleanup
  imu_thread.join();
  cam_thread.join();
  mq_close(imu_mq);
  sem_close(sem);
  sem_close(ready_sem);
  traj_file.close();
  IpcManager::cleanup_all();

  return EXIT_SUCCESS;
}
