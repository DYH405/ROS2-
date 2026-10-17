#!/bin/bash
# Record ROS2 bag for 30 seconds

wait_for_topic() { # 话题就绪检测函数
    local topic=$1 # $1: 第一个参数，local: 本地变量
    local timeout=${2:-30} # $2: 第二个参数，默认值为30秒
    local elapsed=0 # elapse: 过去，流逝

    while [ $elapsed -lt $timeout ]; do # -lt: less than-小于
        if ros2 topic list | grep -q "$topic";then # grep：全局搜索， -q：静默模式，只返回1/0
            echo "[ok] $topic 已就绪 (等待${elapsed}秒)"
            return 0 # 成功
        fi # if语句完结
        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo "[FAIL] 等待 $topic 话题超时 ($timeout 秒)"
    return 1 # 失败
}

wait_for_topic_gone() { # 话题消失检测函数
    local topic=$1 # $1: 第一个参数，local: 本地变量
    local check_interval=2 # interval: 间隔

    echo "[INFO] 监听中 $topic 消失时停止录制..."
    while true; do
        if ! ros2 topic list | grep -q "$topic"; then
            echo "[OK] $topic 已消失，导航结束"
            return 0
        fi
        sleep $check_interval
    done
}
clean_up(){
    echo""
}
echo "===== 开始等待话题 ====="
wait_for_topic /odom 30 || exit 1
wait_for_topic /scan 30 || exit 1
wait_for_topic /cmd_vel 30 || exit 1

# 继续执行后续命令
DURATION=30
DATE=$(date +%Y%m%d_%H%M%S)

source /opt/ros/humble/setup.bash

BAG_ROOT="$HOME/ros2_ws/bag_data"
mkdir -p "$BAG_ROOT"
cd "$BAG_ROOT" || exit 1

echo "Recording bag for ${DURATION} seconds..."

timeout --signal=INT --kill-after=5s --foreground "${DURATION}s" \
ros2 bag record \
-o "bag_${DATE}" \
/scan \
/tf \
/tf_static \
/cmd_vel \
/odom \
/plan \
/amcl_pose


echo "Bag recording completed."