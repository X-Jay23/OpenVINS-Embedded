# 目标系统设定
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

# 交叉编译器位置
set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

# 定义 Sysroot 路径
set(RK3568_SYSROOT /home/jay/rk3568_workspace/sysroot)
set(CMAKE_SYSROOT ${RK3568_SYSROOT})

# 寻找库和头文件的策略
# 只在 Sysroot 里找库和头文件，不要去主机目录找
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# 针对 Pkg-config 的额外优化（OpenCV 常用）
set(ENV{PKG_CONFIG_SYSROOT_DIR} ${RK3568_SYSROOT})
set(ENV{PKG_CONFIG_LIBDIR} ${RK3568_SYSROOT}/usr/lib/aarch64-linux-gnu/pkgconfig)

# 解决库的搜索优先级和间接依赖问题
# 1. 使用 -L 强制优先搜索 Sysroot 路径，避免错用主机的旧版 Glibc
# 2. 使用 -Wl,-rpath-link 处理库的间接依赖
set(PRIORITY_LIB_FLAGS "-L${RK3568_SYSROOT}/lib/aarch64-linux-gnu -L${RK3568_SYSROOT}/usr/lib/aarch64-linux-gnu")
set(LINK_FLAGS "${PRIORITY_LIB_FLAGS} -Wl,-rpath-link,${RK3568_SYSROOT}/lib/aarch64-linux-gnu:${RK3568_SYSROOT}/usr/lib/aarch64-linux-gnu")

set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${LINK_FLAGS}" CACHE STRING "" FORCE)
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${LINK_FLAGS}" CACHE STRING "" FORCE)
set(CMAKE_MODULE_LINKER_FLAGS "${CMAKE_MODULE_LINKER_FLAGS} ${LINK_FLAGS}" CACHE STRING "" FORCE)
