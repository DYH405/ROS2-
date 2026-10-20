#!/bin/bash

cleanup() {
  echo ""
  echo "[Ctrl+C] 正在关闭所有进程..."
 
  echo "关闭 RViz2..."
  kill $RVIZ2_PID 2>/dev/null
 
  echo "优雅终止 Nav2 父进程..."
  pkill -15 -f "nav2_bringup"
  sleep 1.5
  echo "强杀顽固容器组件..."
  pkill -9 -f "nav2_container"
 
  echo "关闭 Gazebo..."
  kill $GAZEBO_PID 2>/dev/null
  sleep 2
 
  kill -9 $RVIZ2_PID 2>/dev/null
  kill -9 $GAZEBO_PID 2>/dev/null
  pkill -9 -f gzserver 2>/dev/null
  pkill -9 -f gzclient 2>/dev/null
 
  rm -rf /dev/shm/gz* /dev/shm/rmw*
  echo "所有进程已关闭，共享内存已清理"
  exit 0
}
 
trap cleanup SIGINT SIGTERM
 
pkill -9 -f gzserver 2>/dev/null
pkill -9 -f gzclient 2>/dev/null
rm -rf /dev/shm/gz* /dev/shm/rmw*
sleep 1

cd ~/ros2_ws
source install/setup.bash

ros2 launch pkg03_gazebo_20260814 gazebo_test.launch.py headless:=true & # True，不显示 GUI=可视化
GAZEBO_PID=$!
sleep 3


ros2 launch nav2_bringup bringup_launch.py \
  use_sim_time:=True \
  map:=/home/robot/ros2_ws/src/pkg03_gazebo_20260814/maps/my_map.yaml \
  params_file:=/home/robot/ros2_ws/src/pkg03_gazebo_20260814/config/nav2_params_hybrid.yaml &
NAV2_PID=$!
sleep 2.5

ros2 run rviz2 rviz2 \
  -d /opt/ros/humble/share/nav2_bringup/rviz/nav2_default_view.rviz \
  --ros-args -p use_sim_time:=true &
RVIZ2_PID=$!

echo "所有服务已启动 (Gazebo=$GAZEBO_PID, Nav2=$NAV2_PID, RViz2=$RVIZ2_PID)"
echo "按 Ctrl+C 关闭所有进程"
wait