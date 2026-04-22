cmake_minimum_required(VERSION 3.10)
project(open_vins)


# 自动生成 compile_commands.json，供 clangd 等语言服务器使用
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Enable optimizations
set(CMAKE_BUILD_TYPE Release)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -march=native")

# Dependencies
find_package(Eigen3 REQUIRED)
find_package(OpenCV REQUIRED)
find_package(Boost REQUIRED COMPONENTS system filesystem thread date_time)

# Common definitions
add_definitions(-DROS_AVAILABLE=0)
add_definitions(-DENABLE_ARUCO_TAGS=0)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/core/ov_core/src
    ${CMAKE_CURRENT_SOURCE_DIR}/core/ov_init/src
    ${CMAKE_CURRENT_SOURCE_DIR}/core/ov_msckf/src
    ${EIGEN3_INCLUDE_DIR}
    ${Boost_INCLUDE_DIRS}
    ${YAML_CPP_INCLUDE_DIR}
)

# Subdirectories for libraries
add_subdirectory(core/ov_core)
add_subdirectory(core/ov_init)
add_subdirectory(core/ov_msckf)

# --- VINS Main Process ---
add_executable(vins apps/vins/main.cpp)
target_link_libraries(vins
    ov_msckf_lib
    ov_init_lib
    ov_core_lib
    ${OpenCV_LIBRARIES}
    ${Boost_LIBRARIES}
    pthread
    rt
)

# --- IMU Process ---
add_executable(imu_process apps/imu/main.cpp)
target_link_libraries(imu_process
    ${OpenCV_LIBRARIES}
    pthread
    rt
)

# --- Camera Process ---
add_executable(camera_process apps/camera/main.cpp)
target_link_libraries(camera_process
    ${OpenCV_LIBRARIES}
    pthread
    rt
)

# --- Standalone Simulation ---
add_executable(vins_sim apps/vins/vins_sim.cpp)
target_link_libraries(vins_sim
    ov_msckf_lib
    ov_init_lib
    ov_core_lib
    ${OpenCV_LIBRARIES}
    ${Boost_LIBRARIES}
    pthread
    rt
)
