#!/bin/bash
# 单次端到端实验：重启Gazebo -> 等就绪 -> 跑一轮巡逻 -> 落CSV -> 采真值末点 -> 关仿真
set -u

WS=/home/robot/ros2_ws
CSV=$WS/experiment_logs/patrol_runs.csv
TRUTH_CSV=$WS/experiment_logs/truth_last_pose.csv
MAP=$WS/src/pkg03_gazebo_20260814/maps/my_map.yaml
NAV2_PARAMS=$WS/src/pkg03_gazebo_20260814/config/nav2_params_hybrid.yaml
CAPTURE=$WS/scripts/capture_truth_pose.py

RUN_TS=$(date +%Y%m%d_%H%M%S)
LOG_DIR=$WS/experiment_logs/run_one_$RUN_TS
mkdir -p "$LOG_DIR"
FAIL_LOG=$LOG_DIR/fail.log

READY_TIMEOUT=${READY_TIMEOUT:-60}
ACTION_TIMEOUT=${ACTION_TIMEOUT:-120}
PATROL_TIMEOUT=${PATROL_TIMEOUT:-900}
READY_TOPICS=${READY_TOPICS:-"/scan /odom /cmd_vel"}

PIDS=()

log() { echo "[INFO] $*"; }
fail() { # $1 步骤 $2 原因 $3 退出码
  echo "[FAIL] step=$1 reason=$2 exit=$3" | tee -a "$FAIL_LOG"
  exit "$3"
}

cleanup() {
  pkill -15 -f "nav2_bringup" 2>/dev/null
  sleep 1
  pkill -9 -f "nav2_container" 2>/dev/null
  # D11 修正：区分两个阶段，避免并发时按名字全局杀误伤别的实例。
  #   PIDS 为空 = S1 开跑前的「清残留」，此时本脚本还没启动任何节点，
  #              按名字全局清扫是安全的（用于清掉上一轮被强杀留下的孤儿）。
  #   PIDS 非空 = EXIT 收尾，只杀本轮 PID 派生出的子孙进程；
  #              原写法 pkill -9 -f partol_node 在批 1c 双实例并发时，
  #              打死了对方正在跑的巡逻节点，patrol_runs 因此出现 0/10 的畸形行。
  if [ ${#PIDS[@]} -eq 0 ]; then
    pkill -9 -f "partol_node" 2>/dev/null
    pkill -9 -f "speech_node" 2>/dev/null
  else
    for pid in ${PIDS[@]+"${PIDS[@]}"}; do
      pkill -9 -P "$pid" 2>/dev/null    # 先杀直接子进程（partol_node / speech_node 由 launch 派生）
    done
  fi
  for pid in ${PIDS[@]+"${PIDS[@]}"}; do
    kill -9 "$pid" 2>/dev/null
  done
  pkill -9 -f gzserver 2>/dev/null
  pkill -9 -f gzclient 2>/dev/null
  pkill -9 -f capture_truth_pose.py 2>/dev/null
  rm -rf /dev/shm/gz* /dev/shm/rmw* 2>/dev/null
  log "cleanup done"
}
trap cleanup EXIT INT TERM

wait_for_topic() { # $1 话题 $2 超时秒
  local topic=$1 timeout=${2:-60} elapsed=0
  while [ $elapsed -lt "$timeout" ]; do
    if ros2 topic list 2>/dev/null | grep -q -- "$topic"; then
      log "topic ready: $topic (${elapsed}s)"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

wait_for_action() { # $1 action名 $2 超时秒
  local name=$1 timeout=${2:-120} elapsed=0
  while [ $elapsed -lt "$timeout" ]; do
    if ros2 action list 2>/dev/null | grep -q -- "$name"; then
      log "action ready: $name (${elapsed}s)"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

csv_rows() { # 统计行数，文件不存在按0
  if [ -f "$1" ]; then wc -l < "$1" | tr -d ' '; else echo 0; fi
}

# S1 清理残留
cleanup
sleep 1

# S2 启动仿真与导航
cd "$WS" || fail S2 "workspace_missing" 2
set +u # setup.bash 内部裸引用 COLCON_TRACE，set -u 下会直接退出
source install/setup.bash || fail S2 "setup_bash_failed" 2
set -u
[ -f "$MAP" ] || fail S2 "map_missing:$MAP" 2
[ -f "$NAV2_PARAMS" ] || fail S2 "nav2_params_missing:$NAV2_PARAMS" 2
[ -f "$CAPTURE" ] || fail S2 "capture_script_missing:$CAPTURE" 2
INST_WORLD=$WS/install/pkg03_gazebo_20260814/share/pkg03_gazebo_20260814/worlds/robocup_home.world
INST_NODE=$WS/install/autopartol_robot/lib/python3.10/site-packages/autopartol_robot/partol_node.py
grep -q "gazebo_ros_state" "$INST_WORLD" || fail S2 "install_stale:world_plugin_missing" 2
grep -q "need_nl" "$INST_NODE" || fail S2 "install_stale:newline_guard_missing" 2

log "launching gazebo"
ros2 launch pkg03_gazebo_20260814 gazebo_test.launch.py > "$LOG_DIR/gazebo.log" 2>&1 &
PIDS+=($!)
sleep 3

log "launching nav2"
ros2 launch nav2_bringup bringup_launch.py \
  use_sim_time:=True \
  map:="$MAP" \
  params_file:="$NAV2_PARAMS" > "$LOG_DIR/nav2.log" 2>&1 &
PIDS+=($!)

# S3 就绪等待
for topic in $READY_TOPICS; do
  wait_for_topic "$topic" "$READY_TIMEOUT" || fail S3 "topic_missing:$topic" 4
done
wait_for_action navigate_to_pose "$ACTION_TIMEOUT" || fail S3 "action_missing:navigate_to_pose" 4

# S4 先起末点采集（缓存/amcl_pose），再跑一轮巡逻
rows_before=$(csv_rows "$CSV")
log "csv rows before patrol: $rows_before"
python3 "$CAPTURE" --watch --json "$LOG_DIR/pose_cache.json" > "$LOG_DIR/pose_watch.log" 2>&1 &
PIDS+=($!)
sleep 2

log "launching patrol"
ros2 launch autopartol_robot autopartol.launch.py > "$LOG_DIR/patrol.log" 2>&1 &
PATROL_PID=$!
PIDS+=($PATROL_PID)

# S5 等待本轮落盘
deadline=$((SECONDS + PATROL_TIMEOUT))
while [ $SECONDS -lt $deadline ]; do
  rows_now=$(csv_rows "$CSV")
  if [ "$rows_now" -gt "$rows_before" ]; then
    log "run recorded: rows $rows_before -> $rows_now"
    break
  fi
  kill -0 "$PATROL_PID" 2>/dev/null || fail S5 "patrol_exited_early" 6
  sleep 5
done
[ "$(csv_rows "$CSV")" -gt "$rows_before" ] || fail S5 "patrol_timeout:${PATROL_TIMEOUT}s" 6

# S6 采集真值末点与AMCL末点（必须在关仿真前）
log "capturing truth pose"
python3 "$CAPTURE" --finalize \
  --json "$LOG_DIR/pose_cache.json" \
  --csv "$TRUTH_CSV" \
  --patrol-csv "$CSV" > "$LOG_DIR/truth.log" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  cat "$LOG_DIR/truth.log" >> "$FAIL_LOG"
  fail S6 "truth_capture_failed:rc=$rc" 7
fi
tail -n 1 "$TRUTH_CSV"

# S7 结束（清理由trap执行）
log "run_one_experiment done"
exit 0