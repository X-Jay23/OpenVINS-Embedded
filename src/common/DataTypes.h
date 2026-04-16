/**
 * @file DataTypes.h
 * @brief Common data structures for the OpenVINS simulation project.
 * 
 * This file defines the structures for IMU and Camera data that are shared between
 * the different processes using IPC (Message Queues and Shared Memory).
 */

#ifndef DATA_TYPES_H
#define DATA_TYPES_H

#include <Eigen/Core>
#include <opencv2/core.hpp>

/**
 * @struct ImuDataPacket
 * @brief A packet of IMU data for transmission via Message Queue.
 * @note This structure must have a fixed size to be used in a POSIX message queue.
 */
struct ImuDataPacket {
    double timestamp;  ///< Original double-type timestamp from the dataset (seconds)
    double wm[3];      ///< Angular velocity (rad/s)
    double am[3];      ///< Linear acceleration (m/s^2)
};

/**
 * @struct CameraDataPacket
 * @brief A packet of Camera data for transmission via Shared Memory.
 * @note Images are fixed size (752x480) for the EuRoC MAV dataset.
 */
struct CameraDataPacket {
    double timestamp;         ///< Original double-type timestamp from the dataset (seconds)
    int cam_id;               ///< Camera sensor ID (0 or 1)
    int width;                ///< Image width (pixels)
    int height;               ///< Image height (pixels)
    unsigned char data[752 * 480]; ///< Raw image data (grayscale)
};

/**
 * @struct ShmRingBuffer
 * @brief Ring buffer structure for camera data in shared memory.
 */
struct ShmRingBuffer {
    static constexpr int BUFFER_SIZE = 5; ///< Number of frames to buffer
    int write_idx;                        ///< Current write index
    int read_idx;                         ///< Current read index
    CameraDataPacket packets[BUFFER_SIZE]; ///< Array of camera data packets
};

#endif // DATA_TYPES_H
