#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
urg_node2_source=${URG_NODE2_SOURCE:-"$repo_root/urg_node2"}
rt_support_source=${ROS_RT_SUPPORT_SOURCE:-"$repo_root/../ros2_realtime_support"}
urg_node2_patch="$repo_root/patches/urg_node2_rt.patch"
rt_support_patch="$repo_root/patches/ros2-realtime-support-no-mimick.patch"
for source_dir in "$urg_node2_source" "$rt_support_source"; do
  if [[ ! -d "$source_dir" ]]; then
    echo "Source directory not found: $source_dir" >&2
    exit 1
  fi
done
if [[ ! -f "$urg_node2_source/urg_library/current/src/urg_sensor.c" ]]; then
  echo "Initialize the urg_library submodule in $urg_node2_source first" >&2
  exit 1
fi
apply_patch_once() {
  local source_dir=$1 patch_file=$2
  if [[ ! -f "$patch_file" ]]; then
    echo "Patch file not found: $patch_file" >&2
    exit 1
  fi
  if git -C "$source_dir" apply --check "$patch_file" >/dev/null 2>&1; then
    git -C "$source_dir" apply "$patch_file"
    echo "Applied $(basename "$patch_file") to $source_dir"
  elif git -C "$source_dir" apply --reverse --check "$patch_file" >/dev/null 2>&1; then
    echo "Already applied: $(basename "$patch_file") in $source_dir"
  else
    echo "Patch cannot be applied cleanly: $patch_file in $source_dir" >&2
    exit 1
  fi
}
apply_patch_once "$urg_node2_source" "$urg_node2_patch"
apply_patch_once "$rt_support_source" "$rt_support_patch"
cd "$repo_root"

target_sysroot=${URG_RT_SYSROOT:-"$HOME/ros2-realtime-cross-pi-jazzy/sysroot"}
export URG_RT_SYSROOT="$target_sysroot"
target_ros="$target_sysroot/opt/ros/jazzy"
export ROS_DISTRO=jazzy ROS_VERSION=2 ROS_PYTHON_VERSION=3
export AMENT_PREFIX_PATH="$target_ros"
export CMAKE_PREFIX_PATH="$target_ros"
export PYTHONPATH="$target_ros/lib/python3.12/site-packages"
export PKG_CONFIG_SYSROOT_DIR="$target_sysroot"
export PKG_CONFIG_LIBDIR="$target_sysroot/usr/lib/aarch64-linux-gnu/pkgconfig:$target_sysroot/usr/share/pkgconfig"
export CMAKE_BUILD_PARALLEL_LEVEL="${RT_BUILD_JOBS:-4}"
unset PKG_CONFIG_PATH COLCON_PREFIX_PATH LD_LIBRARY_PATH

colcon --log-base "$repo_root/log" build \
  --base-paths "$urg_node2_source" "$rt_support_source" \
  --packages-up-to urg_node2 \
  --executor sequential \
  --cmake-clean-cache \
  --build-base "$repo_root/build" \
  --install-base "$repo_root/install" \
  --merge-install \
  --cmake-args \
    "-DCMAKE_TOOLCHAIN_FILE=$repo_root/cmake/aarch64.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS:BOOL=ON \
    -DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,defs \
    -DCMAKE_EXE_LINKER_FLAGS=-Wl,-z,defs \
    -DBUILD_TESTING:BOOL=OFF \
    -DBUILD_COMP_TESTING:BOOL=OFF \
    -DPython3_EXECUTABLE=/usr/bin/python3 \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
