// src/common/PerformanceLogger.h
#ifndef PERFORMANCE_LOGGER_H
#define PERFORMANCE_LOGGER_H

#include <chrono>
#include <iostream>
#include <vector>
#include <numeric>

class PerformanceLogger {
public:
    PerformanceLogger() {}
    
    ~PerformanceLogger() {
        if (!frame_times_.empty()) {
            double sum = std::accumulate(frame_times_.begin(), frame_times_.end(), 0.0);
            double avg = sum / frame_times_.size();
            std::cout << "\n============================================\n";
            std::cout << "[Performance] VINS Process Timing Summary\n";
            std::cout << "Total Frames Processed : " << frame_times_.size() << "\n";
            std::cout << "Average Time per Frame : " << avg << " ms\n";
            std::cout << "============================================\n\n";
        }
    }

    void start_frame() {
        start_time_ = std::chrono::high_resolution_clock::now();
    }

    void end_frame() {
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> duration = end_time - start_time_;
        frame_times_.push_back(duration.count());
    }

private:
    std::chrono::time_point<std::chrono::high_resolution_clock> start_time_;
    std::vector<double> frame_times_;
};

#endif // PERFORMANCE_LOGGER_H
