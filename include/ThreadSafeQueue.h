/**
 * @file ThreadSafeQueue.h
 * @brief Template class for a thread-safe queue.
 */

#ifndef THREAD_SAFE_QUEUE_H
#define THREAD_SAFE_QUEUE_H

#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>

/**
 * @class ThreadSafeQueue
 * @brief A thread-safe queue implementation using std::mutex and std::condition_variable.
 * @tparam T The type of data to store in the queue.
 */
template <typename T>
class ThreadSafeQueue {
public:
    /** @brief Push an item into the queue. */
    void push(T value) {
        std::lock_guard<std::mutex> lock(mutex_);
        queue_.push(std::move(value));
        cond_.notify_one();
    }

    /**
     * @brief Pop an item from the queue, blocking until one is available.
     * @return The popped item.
     */
    T pop() {
        std::unique_lock<std::mutex> lock(mutex_);
        cond_.wait(lock, [this] { return !queue_.empty(); });
        T value = std::move(queue_.front());
        queue_.pop();
        return value;
    }

    /**
     * @brief Try to pop an item from the queue without blocking.
     * @return An optional containing the item if the queue was not empty.
     */
    std::optional<T> try_pop() {
        std::lock_guard<std::mutex> lock(mutex_);
        if (queue_.empty()) {
            return std::nullopt;
        }
        T value = std::move(queue_.front());
        queue_.pop();
        return value;
    }

    /** @brief Check if the queue is empty. */
    bool empty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.empty();
    }

    /** @brief Get the size of the queue. */
    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.size();
    }

private:
    std::queue<T> queue_;
    mutable std::mutex mutex_;
    std::condition_variable cond_;
};

#endif // THREAD_SAFE_QUEUE_H
