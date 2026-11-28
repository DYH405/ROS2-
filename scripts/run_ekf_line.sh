#!/bin/bash
# =============================================================================
# run.sh 的 EKF 同构副本（M3 验证专用）
#
# 与 run.sh 的唯一差异：GAZEBO_SH_PATH 指向 gazebo_ekf.sh，
# 后者起 ekf_test.launch.py（EKF 接管 odom -> base_footprint，输出 /odometry/filtered）。
# 三步流程（起底座 -> 等 10s -> 起巡逻）与 run.sh 完全一致。
#
# 另额外透传 "$@" 给 gazebo_ekf.sh，使 --no-rviz 可用：
#   ./run_ekf_line.sh --no-rviz
# 无参数时行为与 run.sh 完全相同。
# =============================================================================

GAZEBO_SH_PATH=~/ros2_ws/src/patrol_simulation/scripts/gazebo_ekf.sh

cleanup() {
    echo ""
    echo "[Ctrl+C] 正在关闭所有进程..."
    echo "终止 gazebo_ekf.sh..."
    kill $GAZEBO_SH_PID 2>/dev/null
    wait $GAZEBO_SH_PID 2>/dev/null
    echo "所有进程已关闭"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "第一步：启动 Gazebo + Nav2 + RViz2 (gazebo_ekf.sh)..."
$GAZEBO_SH_PATH "$@" &
GAZEBO_SH_PID=$!

echo "第二步：等待导航就绪 (10秒)..."
sleep 10

echo "第三步：启动巡航..."
source ~/ros2_ws/install/setup.bash
ros2 launch patrol_mission patrol.launch.py

echo "巡航已结束，清理所有进程..."
cleanup