/**
 * @file IpcManager.h
 * @brief Management of Inter-Process Communication (IPC).
 */

#ifndef IPC_MANAGER_H
#define IPC_MANAGER_H

#include <string>
#include <fcntl.h>
#include <sys/stat.h>
#include <mqueue.h>
#include <sys/mman.h>
#include <sys/eventfd.h>
#include <semaphore.h>
#include <unistd.h>
#include <stdexcept>
#include <cstring>
#include <iostream>
#include <cstdio>

#include "DataTypes.h"

/** @brief Name of the IMU message queue. */
const char* const IMU_MQ_NAME = "/vins_imu_mq";
/** @brief Name of the camera shared memory. */
const char* const CAM_SHM_NAME = "/vins_cam_shm";
/** @brief Name of the camera semaphore. */
const char* const CAM_SEM_NAME = "/vins_cam_sem";
/** @brief Name of the readiness semaphore. */
const char* const READY_SEM_NAME = "/vins_ready_sem";

/**
 * @class IpcManager
 * @brief Class responsible for setting up and managing IPC resources.
 */
class IpcManager {
public:
    /** @brief Constructor. */
    IpcManager() = default;

    /** @brief Destructor. Clean up resources if necessary. */
    ~IpcManager() {
        // Resources are usually unlinked by the main process or explicitly.
    }

    /**
     * @brief Create or open the IMU message queue.
     * @param is_server True if this is the creating process.
     * @return The message queue descriptor.
     */
    mqd_t open_imu_mq(bool is_server) {
        struct mq_attr attr;
        attr.mq_flags = 0;
        attr.mq_maxmsg = 10;
        attr.mq_msgsize = sizeof(ImuDataPacket);
        attr.mq_curmsgs = 0;

        int flags = is_server ? (O_CREAT | O_RDWR) : O_RDONLY;
        if (is_server) {
            mq_unlink(IMU_MQ_NAME);
        }
        mqd_t mq = mq_open(IMU_MQ_NAME, flags, 0666, &attr);
        if (mq == (mqd_t)-1) {
            perror("mq_open imu");
            throw std::runtime_error("Failed to open IMU message queue");
        }
        return mq;
    }

    /**
     * @brief Create or open the camera shared memory.
     * @param is_server True if this is the creating process.
     * @param size The size of the shared memory region.
     * @return Pointer to the shared memory region.
     */
    void* open_cam_shm(bool is_server, size_t size) {
        int flags = is_server ? (O_CREAT | O_RDWR) : O_RDWR;
        if (is_server) shm_unlink(CAM_SHM_NAME);
        int shm_fd = shm_open(CAM_SHM_NAME, flags, 0666);
        if (shm_fd == -1) {
            perror("shm_open camera");
            throw std::runtime_error("Failed to open Camera shared memory");
        }

        if (is_server && ftruncate(shm_fd, size) == -1) {
            perror("ftruncate camera");
            throw std::runtime_error("Failed to ftruncate Camera shared memory");
        }

        void* ptr = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
        if (ptr == MAP_FAILED) {
            perror("mmap camera");
            throw std::runtime_error("Failed to mmap Camera shared memory");
        }
        close(shm_fd);
        return ptr;
    }

    /**
     * @brief Create or open the camera semaphore.
     * @param is_server True if this is the creating process.
     * @return The semaphore pointer.
     */
    sem_t* open_cam_sem(bool is_server) {
        if (is_server) sem_unlink(CAM_SEM_NAME);
        sem_t* sem = sem_open(CAM_SEM_NAME, is_server ? O_CREAT : 0, 0666, 0);
        if (sem == SEM_FAILED) {
            perror("sem_open camera");
            throw std::runtime_error("Failed to open Camera semaphore");
        }
        return sem;
    }

    /**
     * @brief Create or open the readiness semaphore.
     * @param is_server True if this is the creating process.
     * @return The semaphore pointer.
     */
    sem_t* open_ready_sem(bool is_server) {
        if (is_server) sem_unlink(READY_SEM_NAME);
        sem_t* sem = sem_open(READY_SEM_NAME, is_server ? O_CREAT : 0, 0666, 0);
        if (sem == SEM_FAILED) {
            perror("sem_open readiness");
            throw std::runtime_error("Failed to open Readiness semaphore");
        }
        return sem;
    }

    /**
     * @brief Static method to unlink all IPC resources.
     */
    static void cleanup_all() {
        mq_unlink(IMU_MQ_NAME);
        shm_unlink(CAM_SHM_NAME);
        sem_unlink(CAM_SEM_NAME);
        sem_unlink(READY_SEM_NAME);
    }
};

#endif // IPC_MANAGER_H
