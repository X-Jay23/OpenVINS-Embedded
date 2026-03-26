cmake_minimum_required(VERSION 3.10)
project(open_vins)

# Set C++ standard
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Enable optimizations
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -fsee -fomit-frame-pointer -fno-signed-zeros -fno-math-errno -funroll-loops")

# Dependencies
find_package(Eigen3 REQUIRED)
find_package(OpenCV REQUIRED)
find_package(Boost REQUIRED COMPONENTS system filesystem thread date_time)

# Common definitions
add_definitions(-DROS_AVAILABLE=0)
add_definitions(-DENABLE_ARUCO_TAGS=0)

# Include directories
include_directories(
    src
    ${EIGEN3_INCLUDE_DIR}
    ${Boost_INCLUDE_DIRS}
    ${YAML_CPP_INCLUDE_DIR}
)

# Subdirectories
add_subdirectory(src/ov_core)
add_subdirectory(src/ov_init)
add_subdirectory(src/ov_msckf)

# Main executable
add_executable(vins_node src/main.cpp)
target_link_libraries(vins_node
    ov_msckf_lib
    ov_init_lib
    ov_core_lib
    ${OpenCV_LIBRARIES}
    ${Boost_LIBRARIES}
)
