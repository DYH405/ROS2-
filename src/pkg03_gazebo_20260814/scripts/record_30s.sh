#!/bin/bash
# Record ROS2 bag for 30 seconds

RECORD_PID=""
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
    local confirm_count=0 # confirm: 确认
    local confirm_threshold=10 

    echo "[INFO] 监听中 $topic 消失时停止录制..."
    while true; do
        if ! ros2 topic list 2>/dev/null | grep -q "$topic"; then
            confirm_count=$((confirm_count + 1))
            echo "[WARN] $topic 未检测到 ($confirm_count/$confirm_threshold)"
            if [ $confirm_count -ge $confirm_threshold ]; then
            echo "[OK] $topic 已消失 (连续${confirm_threshold}次未检测到)"
            return 0
            fi
        else
            confirm_count=0
        fi
        sleep $check_interval
    done
}
clean_up(){ # 清理函数
    echo ""
    echo "[Ctrl+C] 正在停止录制..."
    kill $RECORD_PID 2>/dev/null # /dev/null: 丢入黑洞，不显示错误信息
    sleep 2 
    kill -9 $RECORD_PID 2>/dev/null # -9: 强制杀掉，不等待进程结束
    echo "录制已停止"
    exit 0 # 成功
}
trap clean_up SIGINT SIGTERM # 注册信号处理函数，当Ctrl+C或SIGTERM信号触发时调用clean_up函数

WAIT_MODE="false"
while getopts "w" opt;do # 解析命令行参数-用来控制模式
    case $opt in 
    w) WAIT_MODE="true" ;;
    \?) echo "用法：$0 [-w] -w: 监听话题消失自动停止"; exit 1 ;;
    esac
done

echo "===== 开始等待话题 ====="
wait_for_topic /odom 30 || exit 1
wait_for_topic /scan 30 || exit 1
wait_for_topic /cmd_vel 30 || exit 1

# 继续执行后续命令
DATE=$(date +%Y%m%d_%H%M%S)

source /opt/ros/humble/setup.bash

BAG_ROOT="$HOME/ros2_ws/bag_data"
mkdir -p "$BAG_ROOT"
cd "$BAG_ROOT" || exit 1

ros2 bag record \
-o "bag_${DATE}" \
/scan \
/tf \
/tf_static \
/cmd_vel \
/odom \
/plan \
/amcl_pose \
/imu/data \
/clock \
/navigate_to_pose/_action/status & # 后台运行，记录进程ID
RECORD_PID=$!

# 双模式选择
if [ "$WAIT_MODE" = "true" ]; then
    wait_for_topic_gone /odom
    sleep 2
    kill $RECORD_PID 2>/dev/null # /dev/null: 丢入黑洞，不显示错误信息
else
    echo "录制中...按 Ctrl+C 停止"
    wait $RECORD_PID
fi  


echo "Bag recording completed."