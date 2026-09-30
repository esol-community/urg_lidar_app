#!/usr/bin/env bash
set -eo pipefail

run_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source /opt/ros/jazzy/setup.bash
source "$run_root/install/local_setup.bash"
export ROS_DOMAIN_ID=203
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
mkdir -p "$run_root/ros-logs"
export ROS_LOG_DIR="$run_root/ros-logs"
exec ros2 launch urg_node2 urg_node2.launch.py
