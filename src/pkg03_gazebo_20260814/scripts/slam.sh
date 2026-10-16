#!/bin/bash

# 残留进程清理
cleanup() { 
  echo ""
  echo "[Ctrl+C] 正在关闭所有进程..."
 
  echo "关闭 RViz2..."
  kill $RVIZ2_PID 2>/dev/null

  echo "关闭 rqt_robot_steering..."
  kill $STEERING_PID 2>/dev/null  
 
  echo "优雅终止 SLAM Toolbox 父进程..."
  pkill -15 -f "slam_toolbox"
  sleep 1.5
  echo "强杀顽固容器组件..."
  pkill -9 -f "slam_toolbox_container"
 
  echo "关闭 Gazebo..."
  kill $GAZEBO_PID 2>/dev/null
  sleep 2
 
  kill -9 $RVIZ2_PID 2>/dev/null
  kill -9 $STEERING_PID 2>/dev/null  
  kill -9 $GAZEBO_PID 2>/dev/null
  pkill -9 -f gzserver 2>/dev/null
  pkill -9 -f gzclient 2>/dev/null
  pkill -9 -f rqt_robot_steering 2>/dev/null
 
  rm -rf /dev/shm/gz* /dev/shm/rmw*
  echo "所有进程已关闭，共享内存已清理"
  exit 0
}

trap cleanup SIGINT SIGTERM

pkill -9 -f gzserver 2>/dev/null
pkill -9 -f gzclient 2>/dev/null
rm -rf /dev/shm/gz* /dev/shm/rmw*
sleep 1
#-------------------------------------------------------------------------------------------------

cd ~/ros2_ws
source install/setup.bash
# 启动仿真环境
ros2 launch pkg03_gazebo_20260814 gazebo_test.launch.py headless:=true & # True，不显示 GUI=可视化
GAZEBO_PID=$!
sleep 3
#-------------------------------------------------------------------------------------------------

# 检查核心话题-1：/scan 话题是否存在
if ros2 topic list | grep -q "/scan"; then
  echo "[OK] /scan 话题已就绪"
else
  echo "[FAIL] /scan 话题未找到，请检查激光雷达"
fi
# 检查 /scan 是否有数据
if timeout 3 ros2 topic hz /scan 2>/dev/null | grep -q "average rate"; then
  echo "[OK] /scan 数据正常流动"
else
  echo "[FAIL] /scan 暂无数据，可能需要等待"
fi
# 检查核心话题-2：/odom 话题是否存在
if ros2 topic list | grep -q "/odom"; then
  echo "[OK] /odom 话题已就绪"
else
  echo "[FAIL] /odom 话题未找到，请检查机器人移动"
fi
# 检查 /odom 是否有数据
if timeout 3 ros2 topic hz /odom 2>/dev/null | grep -q "average rate"; then
  echo "[OK] /odom 数据正常流动"
else
  echo "[FAIL] /odom 暂无数据，可能需要等待"
fi
#-------------------------------------------------------------------------------------------------

# 启动 SLAM Toolbox
ros2 launch slam_toolbox online_async_launch.py use_sim_time:=true &
SLAM_TOOLBOX_PID=$!
sleep 2.5
# 检查 /map 话题是否存在
if ros2 topic list | grep -q "/map"; then
  echo "[OK] /map 话题已就绪"
else
  echo "[FAIL] /map 话题未找到,请检查SLAM Toolbox是否启动"
fi
# 启动 RViz2
ros2 run rviz2 rviz2 \
  -d /opt/ros/humble/share/slam_toolbox/config/slam_toolbox_default.rviz \
  --ros-args -p use_sim_time:=true &
RVIZ2_PID=$!
# 启动 rqt_robot_steering
ros2 run rqt_robot_steering rqt_robot_steering &
STEERING_PID=$!
# 防御性创建地图保存目录
mkdir -p ~/ros2_ws/src/pkg03_gazebo_20260814/maps
echo "===== SLAM建图模式已启动 ====="
echo "Gazebo=$GAZEBO_PID, SLAM=$SLAM_TOOLBOX_PID, RViz2=$RVIZ2_PID"
echo "请在RViz2中遥控机器人建图"
echo "建图完成后，运行以下命令保存地图："
echo " ros2 run nav2_map_server map_saver_cli -f ~/ros2_ws/src/pkg03_gazebo_20260814/maps/my_map --ros-args -p use_sim_time:=true"
echo "按 Ctrl+C 关闭所有进程"
wait