#ifndef EUROC_DATA_LOADER_H
#define EUROC_DATA_LOADER_H

#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <map>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <chrono>

#include <Eigen/Eigen>
#include <opencv2/opencv.hpp>

#include "utils/sensor_data.h"

namespace ov_core {

class EuRoCDataLoader {
public:
    EuRoCDataLoader(const std::string& dataset_path) : dataset_path_(dataset_path) {
        if (dataset_path_.back() != '/') dataset_path_ += "/";
    }

    bool load_imu_data(std::vector<ImuData>& imu_data) {
        std::string imu_file = dataset_path_ + "imu0/data.csv";
        std::ifstream file(imu_file);
        if (!file.is_open()) return false;

        std::string line;
        std::getline(file, line); // skip header
        while (std::getline(file, line)) {
            if (line[0] == '#') continue;
            std::stringstream ss(line);
            std::string field;
            std::vector<double> values;
            while (std::getline(ss, field, ',')) {
                values.push_back(std::stod(field));
            }
            if (values.size() < 7) continue;

            ImuData data;
            data.timestamp = values[0] * 1e-9;
            data.wm << values[1], values[2], values[3];
            data.am << values[4], values[5], values[6];
            imu_data.push_back(data);
        }
        return true;
    }

    bool load_cam_filenames(int cam_id, std::map<double, std::string>& cam_filenames) {
        std::string cam_file = dataset_path_ + "cam" + std::to_string(cam_id) + "/data.csv";
        std::ifstream file(cam_file);
        if (!file.is_open()) return false;

        std::string line;
        std::getline(file, line); // skip header
        while (std::getline(file, line)) {
            if (line[0] == '#') continue;
            size_t comma = line.find(',');
            if (comma == std::string::npos) continue;
            double timestamp = std::stod(line.substr(0, comma)) * 1e-9;
            std::string filename = line.substr(comma + 1);
            // remove carriage return if present
            if (!filename.empty() && filename.back() == '\r') filename.pop_back();
            cam_filenames[timestamp] = filename;
        }
        return true;
    }

    cv::Mat get_image(int cam_id, const std::string& filename) {
        std::string path = dataset_path_ + "cam" + std::to_string(cam_id) + "/data/" + filename;
        return cv::imread(path, cv::IMREAD_GRAYSCALE);
    }

    bool get_image_direct(int cam_id, const std::string& filename, cv::Mat& dst) {
        std::string path = dataset_path_ + "cam" + std::to_string(cam_id) + "/data/" + filename;
        
        // 1. Read file into a buffer
        std::ifstream file(path, std::ios::binary | std::ios::ate);
        if (!file.is_open()) return false;
        std::streamsize size = file.tellg();
        file.seekg(0, std::ios::beg);
        
        std::vector<uchar> buffer(size);
        if (!file.read((char*)buffer.data(), size)) return false;

        // 2. Decode into preallocated dst
        // imdecode will reuse memory if size and type match.
        cv::imdecode(buffer, cv::IMREAD_GRAYSCALE, &dst);
        return true;
    }

private:
    std::string dataset_path_;
};

} // namespace ov_core

#endif // EUROC_DATA_LOADER_H
