cmake_minimum_required(VERSION 3.3)
project(ov_core)

# Library sources
set(LIBRARY_SOURCES
    src/dummy.cpp
    src/cpi/CpiV1.cpp
    src/cpi/CpiV2.cpp
    src/sim/BsplineSE3.cpp
    src/track/TrackBase.cpp
    src/track/TrackAruco.cpp
    src/track/TrackDescriptor.cpp
    src/track/TrackKLT.cpp
    src/track/TrackSIM.cpp
    src/types/Landmark.cpp
    src/feat/Feature.cpp
    src/feat/FeatureDatabase.cpp
    src/feat/FeatureInitializer.cpp
    src/utils/print.cpp
)

file(GLOB_RECURSE LIBRARY_HEADERS "src/*.h")

# Build library
add_library(ov_core_lib SHARED ${LIBRARY_SOURCES} ${LIBRARY_HEADERS})
target_include_directories(ov_core_lib PUBLIC src/)
target_link_libraries(ov_core_lib
    ${OpenCV_LIBRARIES}
    ${Boost_LIBRARIES}
    Eigen3::Eigen
)
