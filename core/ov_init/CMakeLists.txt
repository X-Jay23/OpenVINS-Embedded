cmake_minimum_required(VERSION 3.3)
project(ov_init)

# Find Ceres
find_package(Ceres REQUIRED)

# Library sources
set(LIBRARY_SOURCES
    src/dummy.cpp
    src/init/InertialInitializer.cpp
    src/static/StaticInitializer.cpp
    src/ceres/Factor_ImageReprojCalib.cpp
    src/ceres/State_JPLQuatLocal.cpp
    src/ceres/Factor_ImuCPIv1.cpp
    src/ceres/Factor_GenericPrior.cpp
    src/sim/SimulatorInit.cpp
    src/dynamic/DynamicInitializer.cpp
)

file(GLOB_RECURSE LIBRARY_HEADERS "src/*.h")

# Build library
add_library(ov_init_lib SHARED ${LIBRARY_SOURCES} ${LIBRARY_HEADERS})
target_include_directories(ov_init_lib PUBLIC src/)
target_link_libraries(ov_init_lib
    ov_core_lib
    ${OpenCV_LIBRARIES}
    ${Boost_LIBRARIES}
    Eigen3::Eigen
    ${CERES_LIBRARIES}
)
