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
ROUNDS=${ROUNDS:-1} # 巡逻轮数，透传给 launch 的 max_rounds，决定日志终句何时出现
IMG_DIR=$WS/patrol_images # 图片落盘目录，与 launch 中 image_capture_node 的 img_save_path 一致

GAZEBO_PID=
NAV2_PID=
PATROL_PID=
CAPTURE_PID=
TEARDOWN_DONE=0
TEARDOWN_DIRTY= # 收摊复检结果，非空表示仍有残留，S7 据此返回非 0
RECOVER=${RECOVER:-0} # 1=发现本工作区残留时自动清理后再跑；0=只报告并退出（默认，避免误清手动实例）
CLEAN_ONLY=0 # 1=只做清理+复检后退出，不启动任何节点（--clean-only 触发）
[ "${1:-}" = "--clean-only" ] && CLEAN_ONLY=1 # 显式恢复入口，只清不跑

log() { echo "[INFO] $*"; }
fail() { # $1 步骤 $2 原因 $3 退出码
  echo "[FAIL] step=$1 reason=$2 exit=$3" | tee -a "$FAIL_LOG"
  exit "$3"
}

topics_present() { # $1 话题名（精确匹配）
  ros2 topic list 2>/dev/null | grep -qx -- "$1"
}

topic_has_publisher() { # $1 话题名；仅订阅者也会让话题出现在列表，故按发布者计数判定
  local n
  n=$(ros2 topic info "$1" 2>/dev/null | awk '/^Publisher count:/{print $3}')
  [ "${n:-0}" -gt 0 ] 2>/dev/null
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

wait_topics_gone() { # $1 超时秒，默认 20；每 0.5 s 轮询
  local timeout=${1:-20} deadline=$((SECONDS + timeout))
  while [ $SECONDS -lt $deadline ]; do
    if ! topic_has_publisher /scan && ! topic_has_publisher /amcl_pose; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

wait_groups_gone() { # $1 超时秒，默认 10；四个进程组内均无存活成员则返回 0
  # 僵尸进程不算存活：其 pgid 仍挂在 ps 里，但父进程(本脚本)退出后即被回收，不构成残留
  local timeout=${1:-10} deadline=$((SECONDS + timeout)) alive pid pgids
  while [ $SECONDS -lt $deadline ]; do
    pgids=$(ps -eo pgid=,stat= 2>/dev/null | awk '$2 !~ /Z/ {print $1}' | tr -d ' ')
    alive=0
    for pid in "$PATROL_PID" "$NAV2_PID" "$GAZEBO_PID" "$CAPTURE_PID"; do
      [ -n "$pid" ] || continue
      printf '%s\n' "$pgids" | grep -qx -- "$pid" && alive=1
    done
    [ "$alive" -eq 0 ] && return 0
    sleep 0.5
  done
  return 1
}

teardown_verify() { # 收摊复检：进程组、话题、共享内存三项都干净才算真收干净
  local dirty=""
  # 未启动过任何进程（如早期 fail）时无需复检，避免把外部残留实例算到本次头上
  if [ -n "$GAZEBO_PID$NAV2_PID$PATROL_PID$CAPTURE_PID" ]; then
    wait_groups_gone 10 || dirty="${dirty}${dirty:+,}proc_group_alive"
    # KILL 后再给 ROS graph 一点更新时间，避免 daemon 缓存未刷新造成误报
    wait_topics_gone 5 || dirty="${dirty}${dirty:+,}topics_published"
    compgen -G "/dev/shm/gz*" >/dev/null 2>&1 && dirty="${dirty}${dirty:+,}shm_gz"
    compgen -G "/dev/shm/rmw*" >/dev/null 2>&1 && dirty="${dirty}${dirty:+,}shm_rmw"
  fi
  if [ -n "$dirty" ]; then
    TEARDOWN_DIRTY=$dirty
    log "cleanup verify: DIRTY ($dirty)"
    echo "[DIRTY] teardown:$dirty" >> "$FAIL_LOG"
    return 1
  fi
  log "cleanup verify: clean (procs gone, topics gone, shm clear)"
  return 0
}

residual_pids() { # 只认命令行含本工作区指纹的进程，避免误杀别的工作区实例
  # 指纹取 world 路径/params 路径/包名：均为本仓库独有，比纯进程名(gzserver)精确
  pgrep -f -- "robocup_home\.world|nav2_bringup|autopartol_robot|image_capture_node|partol_node|capture_truth_pose" 2>/dev/null \
    | grep -vx -- "$$" || true # 排除脚本自身，防匹配到自己的命令行
}

print_residual() { # 打印残留进程详情，便于远程判断归属；有残留返回 0
  local p has=0
  for p in $(residual_pids); do
    has=1
    ps -o pid=,ppid=,pgid=,stat=,lstart=,cmd= -p "$p" 2>/dev/null | head -1
  done
  [ "$has" -eq 1 ]
}

pkill_pgid() { # $1 PID $2 TERM|KILL；按该进程的真实 pgid 整组发信号
  local p=$1 sig=$2 pgid
  [ -n "$p" ] || return 0
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  # 用真实 pgid 而非 $p：残留进程未必是组首，用 $p 会杀不到同组兄弟
  if [ -n "$pgid" ]; then
    kill -"$sig" -- "-$pgid" 2>/dev/null
  else
    kill -"$sig" "$p" 2>/dev/null
  fi
}

recover_stale() { # 清理本工作区残留并复检；成功返回 0
  local pids p deadline
  pids=$(residual_pids)
  [ -n "$pids" ] || return 1
  for p in $pids; do pkill_pgid "$p" TERM; done # 先 TERM 给优雅退出机会
  sleep 5
  for p in $pids; do pkill_pgid "$p" KILL; done # 再 KILL 兜底
  rm -rf /dev/shm/gz* /dev/shm/rmw* 2>/dev/null
  # 复检：wait_groups_gone 依据本脚本记录的 PID，此刻为空，故按残留指纹单独轮询
  deadline=$((SECONDS + 10))
  while [ $SECONDS -lt $deadline ]; do
    [ -z "$(residual_pids)" ] && break
    sleep 0.5
  done
  [ -z "$(residual_pids)" ] || return 1
  wait_topics_gone 5 || return 1
  return 0
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
  wait_topics_gone || log "teardown: TERM 后 20s 内话题未消失，转 KILL"
  for pid in "$PATROL_PID" "$NAV2_PID" "$GAZEBO_PID" "$CAPTURE_PID"; do
    signal_pid "$pid" KILL
  done
  rm -rf /dev/shm/gz* /dev/shm/rmw* 2>/dev/null
  teardown_verify # 收摊后复检，结果记入 TEARDOWN_DIRTY
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
grep -q "gazebo_ros_state" "$INST_WORLD" || fail S2 "install_stale:world_plugin_missing" 2
# Python 包在 --symlink-install 下不落实体文件（只有 egg-link 指向 build/），
# 故按运行时真实导入路径解析，取不到再兜底到源码目录
INST_NODE=$(python3 -c "import autopartol_robot,os;print(os.path.join(os.path.dirname(autopartol_robot.__file__),'partol_node.py'))" 2>/dev/null)
[ -n "$INST_NODE" ] && [ -f "$INST_NODE" ] || INST_NODE=$WS/src/autopartol_robot/autopartol_robot/partol_node.py
log "partol_node source: $INST_NODE"
grep -q "need_nl" "$INST_NODE" || fail S2 "install_stale:newline_guard_missing" 2

# 前置检查：已有发布者说明有残留或别的实例
# （仅订阅者会让话题出现在列表但无发布者，如采集脚本/监控工具，不算残留）
if topic_has_publisher /scan || topic_has_publisher /amcl_pose; then
  log "stale detected: scan_or_amcl_published"
  # 无论清不清，先打印残留详情：远程看一眼就知道是什么、什么时候起的
  print_residual || log "stale source: 命令行指纹不匹配本工作区，仅报告不清"
  if [ "$CLEAN_ONLY" -eq 1 ] || [ "$RECOVER" -eq 1 ]; then
    log "recover: 清理本工作区残留"
    if recover_stale; then
      log "recover: 成功，继续"
    else
      print_residual
      fail S2 "stale_unrecoverable" 5 # 清了还脏：残留不归我们或杀不掉，需人工介入
    fi
  else
    log "to clean: bash $WS/scripts/run_one_experiment.sh --clean-only"
    log "to auto-recover: RECOVER=1 bash $WS/scripts/run_one_experiment.sh"
    fail S2 "stale_ros_graph:scan_or_amcl_published" 5
  fi
fi

if [ "$CLEAN_ONLY" -eq 1 ]; then # 仅清理模式：已确认无残留，不启动任何节点
  log "clean-only done: 无残留"
  exit 0
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
# 跑前图片快照：本轮新图 = 跑后 - 跑前，避免历史 487 个文件干扰
imgs_before=$(find "$IMG_DIR" -maxdepth 1 -name '*.png' -type f 2>/dev/null | sort)
log "images before patrol: $(printf '%s\n' "$imgs_before" | grep -c '\.png$' || true)"
setsid python3 "$CAPTURE" --watch --json "$LOG_DIR/pose_cache.json" > "$LOG_DIR/pose_watch.log" 2>&1 &
CAPTURE_PID=$!
sleep 2

log "launching patrol (rounds=$ROUNDS)"
setsid ros2 launch autopartol_robot autopartol.launch.py max_rounds:="$ROUNDS" > "$LOG_DIR/patrol.log" 2>&1 &
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

# 轮数校验：日志中"第N轮完成"条数应达到指定轮数，防止中途被切断却因终句误判为完成
rounds_done=$(grep -c '轮完成' "$PATROL_LOG" 2>/dev/null || true)
[ "${rounds_done:-0}" -ge "$ROUNDS" ] || fail S5 "rounds_short:done=${rounds_done:-0} want=$ROUNDS" 6

# 图片核验：用跑前/跑后快照差集，不用日志"图片保存成功"计数
# 原因：record_img 是 call_async 异步调用，末张图的 imwrite 与回调都发生在日志终句之后，
#       进程随即退出，导致"图片保存成功"少打一条（实测 10 张图只打 9 条），按日志核会误报
sleep 3 # 等待异步 imwrite 落盘
imgs_after=$(find "$IMG_DIR" -maxdepth 1 -name '*.png' -type f 2>/dev/null | sort)
new_imgs=$(comm -13 <(printf '%s\n' "$imgs_before") <(printf '%s\n' "$imgs_after") | grep -c '\.png$' || true)
# 期望图片数取 CSV 最后一行的 succeeded（第5列）：掉一个巡逻点就该少一张图，不能固定比 10
succ=$(grep -v '^$' "$CSV" | tail -n 1 | awk -F, '{print $5}' | tr -d ' \r')
# 零字节图检查：收尾时整组 TERM 可能把 imwrite 掐断，留下空文件
zero_imgs=$(comm -13 <(printf '%s\n' "$imgs_before") <(printf '%s\n' "$imgs_after") \
  | grep '\.png$' | while read -r f; do [ -s "$f" ] || echo x; done | wc -l | tr -d ' ')
[ "${zero_imgs:-0}" -eq 0 ] || fail S5 "image_zero_byte:count=$zero_imgs" 6
[ "${new_imgs:-0}" -eq "${succ:-0}" ] || fail S5 "image_count_mismatch:new=$new_imgs succ=$succ" 6
log "images verified: new=$new_imgs succ=$succ zero=$zero_imgs"

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

# S7 结束：显式收摊并复检，收不干净则返回非 0（TEARDOWN_DONE 保证 trap 不会重复执行）
log "log dir: $LOG_DIR"
log "summary: rounds=$rounds_done images=$new_imgs/$succ csv_rows=$rows_before->$rows_now"
teardown
[ -z "$TEARDOWN_DIRTY" ] || fail S7 "teardown_dirty:$TEARDOWN_DIRTY" 8
log "run_one_experiment done"
exit 0