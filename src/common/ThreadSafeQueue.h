/**
 * @file ThreadSafeQueue.h
 * @brief Template class for a thread-safe bounded blocking queue.
 */

#ifndef THREAD_SAFE_QUEUE_H
#define THREAD_SAFE_QUEUE_H

#include <vector>
#include <mutex>
#include <condition_variable>
#include <optional>

/**
 * @class ThreadSafeQueue
 * @brief A thread-safe fixed-size bounded blocking queue.
 */
template <typename T>
class ThreadSafeQueue {
public:
    /** 
     * @brief Constructor.
     * @param max_size The maximum number of elements in the buffer.
     */
    explicit ThreadSafeQueue(size_t max_size = 100) 
        : data_(max_size), max_size_(max_size), head_(0), tail_(0), count_(0) {}

    /** 
     * @brief Push an item into the buffer.
     * Blocks if the buffer is full (backpressure).
     */
    void push(T value) {
        std::unique_lock<std::mutex> lock(mutex_);
        // Wait if full - this is the "Backpressure"
        cond_push_.wait(lock, [this] { return count_ < max_size_; });
        
        data_[head_] = std::move(value);
        head_ = (head_ + 1) % max_size_;
        count_++;
        
        cond_pop_.notify_one();
    }

    /**
     * @brief Pop an item from the buffer, blocking until one is available.
     * @return The popped item.
     */
    T pop() {
        std::unique_lock<std::mutex> lock(mutex_);
        cond_pop_.wait(lock, [this] { return count_ > 0; });
        
        T value = std::move(data_[tail_]);
        tail_ = (tail_ + 1) % max_size_;
        count_--;
        
        cond_push_.notify_one();
        return value;
    }

    /**
     * @brief Try to pop an item from the buffer without blocking.
     */
    std::optional<T> try_pop() {
        std::lock_guard<std::mutex> lock(mutex_);
        if (count_ == 0) {
            return std::nullopt;
        }
        
        T value = std::move(data_[tail_]);
        tail_ = (tail_ + 1) % max_size_;
        count_--;
        
        cond_push_.notify_one();
        return value;
    }

    /** @brief Check if the buffer is empty. */
    bool empty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_ == 0;
    }

    /** @brief Get the current number of elements in the buffer. */
    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_;
    }

private:
    std::vector<T> data_;
    size_t max_size_;
    size_t head_;
    size_t tail_;
    size_t count_;
    mutable std::mutex mutex_;
    std::condition_variable cond_pop_;
    std::condition_variable cond_push_;
};

#endif // THREAD_SAFE_QUEUE_H
