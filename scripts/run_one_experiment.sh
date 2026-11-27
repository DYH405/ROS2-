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

GAZEBO_PID=
NAV2_PID=
PATROL_PID=
CAPTURE_PID=
TEARDOWN_DONE=0

log() { echo "[INFO] $*"; }
fail() { # $1 步骤 $2 原因 $3 退出码
  echo "[FAIL] step=$1 reason=$2 exit=$3" | tee -a "$FAIL_LOG"
  exit "$3"
}

topics_present() { # $1 话题名（精确匹配）
  ros2 topic list 2>/dev/null | grep -qx -- "$1"
}

collect_tree() { # 递归打印 PID 及其所有子孙
  local p=$1 c
  echo "$p"
  for c in $(pgrep -P "$p" 2>/dev/null); do
    collect_tree "$c"
  done
}

same_group() { # 记录的 PID 是否自成会话/进程组（setsid 生效）
  local pid=$1 pgid sid
  pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
  sid=$(ps -o sid= -p "$pid" 2>/dev/null | tr -d ' ')
  [ -n "$pgid" ] && [ "$pgid" = "$pid" ] && [ "$sid" = "$pid" ]
}

signal_pid() { # $1 PID $2 TERM|KILL
  local pid=$1 sig=$2 p
  [ -n "$pid" ] || return 0
  # 同组：按进程组整组发；不同组：退化为按进程树逐个发
  if same_group "$pid" || ps -eo pgid= 2>/dev/null | tr -d ' ' | grep -qx -- "$pid"; then
    kill -"$sig" -- "-$pid" 2>/dev/null
  else
    for p in $(collect_tree "$pid"); do
      kill -"$sig" "$p" 2>/dev/null
    done
  fi
}

wait_topics_gone() { # 每 0.5 s 轮询，最多 20 s
  local deadline=$((SECONDS + 20))
  while [ $SECONDS -lt $deadline ]; do
    if ! topics_present /scan && ! topics_present /amcl_pose; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

teardown() {
  [ "$TEARDOWN_DONE" -eq 1 ] && return 0
  TEARDOWN_DONE=1
  trap - EXIT INT TERM
  log "teardown: TERM patrol -> nav2 -> gazebo"
  signal_pid "$PATROL_PID" TERM
  signal_pid "$NAV2_PID" TERM
  signal_pid "$GAZEBO_PID" TERM
  signal_pid "$CAPTURE_PID" TERM
  wait_topics_gone || log "teardown: /scan 或 /amcl_pose 20s 内未消失，转 KILL"
  for pid in "$PATROL_PID" "$NAV2_PID" "$GAZEBO_PID" "$CAPTURE_PID"; do
    signal_pid "$pid" KILL
  done
  rm -rf /dev/shm/gz* /dev/shm/rmw* 2>/dev/null
  log "cleanup done"
}
trap teardown EXIT
trap 'teardown; exit 130' INT
trap 'teardown; exit 143' TERM

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

# 前置检查：不按名字全局杀；已有仿真图说明有残留/别的实例，直接退出
if topics_present /scan || topics_present /amcl_pose; then
  fail S2 "stale_ros_graph:scan_or_amcl_present" 5
fi

log "launching gazebo"
setsid ros2 launch pkg03_gazebo_20260814 gazebo_test.launch.py > "$LOG_DIR/gazebo.log" 2>&1 &
GAZEBO_PID=$!
sleep 3

log "launching nav2"
setsid ros2 launch nav2_bringup bringup_launch.py \
  use_sim_time:=True \
  map:="$MAP" \
  params_file:="$NAV2_PARAMS" > "$LOG_DIR/nav2.log" 2>&1 &
NAV2_PID=$!

# S3 就绪等待
for topic in $READY_TOPICS; do
  wait_for_topic "$topic" "$READY_TIMEOUT" || fail S3 "topic_missing:$topic" 4
done
wait_for_action navigate_to_pose "$ACTION_TIMEOUT" || fail S3 "action_missing:navigate_to_pose" 4

# S4 先起末点采集（缓存/amcl_pose），再跑一轮巡逻
rows_before=$(csv_rows "$CSV")
log "csv rows before patrol: $rows_before"
setsid python3 "$CAPTURE" --watch --json "$LOG_DIR/pose_cache.json" > "$LOG_DIR/pose_watch.log" 2>&1 &
CAPTURE_PID=$!
sleep 2

log "launching patrol"
setsid ros2 launch autopartol_robot autopartol.launch.py > "$LOG_DIR/patrol.log" 2>&1 &
PATROL_PID=$!

# S5 等待巡逻结束：以日志终句为准（在 CSV 写入之后、while 循环之外，max_rounds 改几都成立）
PATROL_LOG=$LOG_DIR/patrol.log
patrol_done=0
deadline=$((SECONDS + PATROL_TIMEOUT))
while [ $SECONDS -lt $deadline ]; do
  if grep -q "巡逻结束，全程统计" "$PATROL_LOG" 2>/dev/null; then
    patrol_done=1
    break
  fi
  if ! kill -0 "$PATROL_PID" 2>/dev/null; then
    sleep 1
    grep -q "巡逻结束，全程统计" "$PATROL_LOG" 2>/dev/null && patrol_done=1
    [ "$patrol_done" -eq 1 ] || fail S5 "patrol_exited_early" 6
    break
  fi
  sleep 2
done
[ "$patrol_done" -eq 1 ] || fail S5 "patrol_timeout:${PATROL_TIMEOUT}s" 6
# CSV 只做辅助校验，不再决定何时退出
rows_now=$(csv_rows "$CSV")
[ "$rows_now" -gt "$rows_before" ] || fail S5 "csv_no_new_row:rows=$rows_now" 6
log "patrol finished: rows $rows_before -> $rows_now"

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