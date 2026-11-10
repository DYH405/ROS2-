#!/bin/bash

GAZEBO_SH_PATH=~/ros2_ws/src/pkg03_gazebo_20260814/scripts/gazebo.sh

cleanup() {
    echo ""
    echo "[Ctrl+C] 正在关闭所有进程..."
    echo "终止 gazebo.sh..."
    kill $GAZEBO_SH_PID 2>/dev/null
    wait $GAZEBO_SH_PID 2>/dev/null
    echo "所有进程已关闭"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "第一步：启动 Gazebo + Nav2 + RViz2 (gazebo.sh)..."
$GAZEBO_SH_PATH &
GAZEBO_SH_PID=$!

echo "第二步：等待导航就绪 (10秒)..."
sleep 10

echo "第三步：启动巡航..."
source ~/ros2_ws/install/setup.bash
ros2 launch autopartol_robot autopartol.launch.py

echo "巡航已结束，清理所有进程..."
cleanup