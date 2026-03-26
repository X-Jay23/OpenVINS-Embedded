cmake_minimum_required(VERSION 3.3)
project(ov_msckf)

# Library sources
set(LIBRARY_SOURCES
    src/dummy.cpp
    src/update/UpdaterMSCKF.cpp
    src/update/UpdaterHelper.cpp
    src/update/UpdaterSLAM.cpp
    src/update/UpdaterZeroVelocity.cpp
    src/state/State.cpp
    src/state/StateHelper.cpp
    src/state/Propagator.cpp
    src/core/VioManagerHelper.cpp
    src/core/VioManager.cpp
    src/sim/Simulator.cpp
)

file(GLOB_RECURSE LIBRARY_HEADERS "src/*.h")

# Build library
add_library(ov_msckf_lib SHARED ${LIBRARY_SOURCES} ${LIBRARY_HEADERS})
target_include_directories(ov_msckf_lib PUBLIC src/)
target_link_libraries(ov_msckf_lib
    ov_init_lib
    ov_core_lib
    ${OpenCV_LIBRARIES}
    ${Boost_LIBRARIES}
    Eigen3::Eigen
)
