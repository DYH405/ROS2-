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
RVIZ_PID=
TEARDOWN_DONE=0
TEARDOWN_DIRTY= # 收摊复检结果，非空表示仍有残留，S7 据此返回非 0
RECOVER=${RECOVER:-0} # 1=发现本工作区残留时自动清理后再跑；0=只报告并退出（默认，避免误清手动实例）
CLEAN_ONLY=0 # 1=只做清理+复检后退出，不启动任何节点（--clean-only 触发）
RVIZ=${RVIZ:-1} # 1=启动 RViz2 可视化（默认，与 gazebo.sh 一致）；0=不启动
RVIZ_WARMUP=${RVIZ_WARMUP:-15} # 起巡逻前等 RViz 渲染就绪的上限秒数，见 S4 预热段注释

log() { echo "[INFO] $*"; }
fail() { # $1 步骤 $2 原因 $3 退出码
  echo "[FAIL] step=$1 reason=$2 exit=$3" | tee -a "$FAIL_LOG"
  exit "$3"
}

log "log dir: $LOG_DIR" # 一开始就给出日志位置，便于另开终端 tail -f 观察进度

topics_present() { # $1 话题名（精确匹配）
  ros2 topic list 2>/dev/null | grep -qx -- "$1"
}

# 参数解析：--no-rviz 沿用 gazebo.sh/gazebo_ekf.sh 既有约定；--clean-only 为恢复入口
for arg in "$@"; do
  case $arg in
    --no-rviz) RVIZ=0 ;; # 显式关闭可视化
    --clean-only) CLEAN_ONLY=1 ;; # 只清不跑
    *) log "warning: 未知参数已忽略: $arg" ;; # 不致命，仅提示，避免拼错参数被静默吞掉
  esac
done

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

wait_topics_gone() { # $1 首轮超时秒(默认 20) $2 二次确认秒(默认 8，0=不做二次确认)
  # 必须分行赋值：local 同一行多个赋值时，后面 $((...)) 展开发生在前面变量生效之前，
  # 配合 set -u 会报「timeout: 未绑定的变量」
  local timeout=${1:-20}
  local confirm=${2:-8}
  local deadline
  deadline=$((SECONDS + timeout))
  while [ $SECONDS -lt $deadline ]; do
    if ! topic_has_publisher /scan && ! topic_has_publisher /amcl_pose; then
      return 0
    fi
    sleep 0.5
  done
  # 首轮超时不等于脏，必须二次确认后才允许判脏。[2026-11-28 A 组] 依据连续两次实跑实测：
  #   run_one_20261128_004741 收摊报 DIRTY(topics_published) 退出 8；
  #   run_one_20261128_005242 开跑时 S2 的 stale 检查（同样调 topic_has_publisher）
  #   没有报 scan_or_amcl_published，收摊复检也 clean。同一套环境在约 30 s 内从
  #   「有发布者」变成「无发布者」，中间没有任何进程被重新拉起 —— 只能是缓存剔除，不是残留。
  # 机制（为什么不采信首轮结果）：
  #   1) topic_has_publisher 读的是 ros2 daemon 的图缓存。进程被 KILL 后，DDS 参与者要等
  #      租约到期才会从缓存里剔除，这段时间 ros2 topic info 仍报 Publisher count >= 1；
  #   2) 每次 ros2 topic info 都要新起一个 CLI 进程（实测约 1 s），首轮 5 s 的预算
  #      实际只采到 2~3 个样本，采样窗口比缓存剔除时间还短。
  # 二次确认的做法：ros2 daemon stop 丢掉缓存，下一次 ros2 调用会自启一个空图的新 daemon，
  #   此时再报发布者就只可能是真的还有进程在发。
  # 为什么不是 --no-daemon：Humble 的 ros2topic 动词没有该选项，只能停 daemon 重建。
  # 为什么不是把首轮超时从 5 s 加长到 20 s：剔除时间取决于租约，不可控；加长只是把误报
  #   挪后，遇到租约更长仍误报，且每次收摊都白等。
  # 代价（必须知道的副作用）：确认窗口内新 daemon 若还没建完图，可能把真实发布者漏判成 0。
  #   兜底在 S2：下一次开跑先查 scan_or_amcl_published，那时 daemon 已热，真实残留照样被拦住。
  [ "$confirm" -gt 0 ] || return 1
  ros2 daemon stop >/dev/null 2>&1
  sleep 1
  # 预热一次：这条调用会等新 daemon 起来并建完首轮图。缺这一步时，确认窗第一轮很可能
  #   拿到「还没发现任何参与者」的空图，把真实发布者读成 0，等于用假阴性换掉了假阳性。
  ros2 topic list >/dev/null 2>&1
  deadline=$((SECONDS + confirm))
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
  # 分行赋值原因同 wait_topics_gone，避免 set -u 下未绑定变量
  local timeout=${1:-10}
  local deadline=$((SECONDS + timeout))
  local alive pid pgids
  while [ $SECONDS -lt $deadline ]; do
    pgids=$(ps -eo pgid=,stat= 2>/dev/null | awk '$2 !~ /Z/ {print $1}' | tr -d ' ')
    alive=0
    for pid in "$RVIZ_PID" "$PATROL_PID" "$NAV2_PID" "$GAZEBO_PID" "$CAPTURE_PID"; do
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
  if [ -n "$GAZEBO_PID$NAV2_PID$PATROL_PID$CAPTURE_PID$RVIZ_PID" ]; then
    wait_groups_gone 10 || dirty="${dirty}${dirty:+,}proc_group_alive"
    # 进程组还在时跳过话题判定：发布者必然还在，判出来只是把同一个根因写成两个脏项，
    #   让人误以为有两个独立故障，实际处置动作只有「再杀一次」这一个。
    #   进程组已清空才查话题，此时仍报发布者才是真需要人看的情况（别的实例占了同一组话题）。
    # 首轮预算 12 s 而不是 5 s 的依据：每次 ros2 topic info 新起 CLI 约 1 s，
    #   wait_topics_gone 每轮要查 /scan 与 /amcl_pose 两个话题，5 s 只够 2~3 个样本；
    #   12 s 约 6 个样本，覆盖 KILL 后正常退出（非缓存）的那一小段抖动。
    #   超出后不再延长首轮，改由 wait_topics_gone 内部的 daemon 重建做二次确认，见该函数注释。
    if [ -z "$dirty" ]; then
      wait_topics_gone 12 || dirty="${dirty}${dirty:+,}topics_published"
    fi
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
  # 首轮 12 s 与 teardown_verify 取同一个值：这里的调用场景（上一次被硬杀、daemon 缓存里
  #   还留着已死参与者）与收摊复检完全同类，预算取小会让「连着跑第二次」在清理环节假失败。
  #   超时后由 wait_topics_gone 内部停 daemon 重建图再确认，见该函数注释。
  wait_topics_gone 12 || return 1
  return 0
}

teardown() {
  [ "$TEARDOWN_DONE" -eq 1 ] && return 0
  TEARDOWN_DONE=1
  trap - EXIT INT TERM
  # 本脚本一个进程都没启动（如 --clean-only 正常结束、S2 早期失败）：无物可收，直接返回，
  # 避免打出误导性的 TERM 日志，也避免把外部实例误算到本次
  if [ -z "$GAZEBO_PID$NAV2_PID$PATROL_PID$CAPTURE_PID$RVIZ_PID" ]; then
    log "teardown: nothing started by this run, skip"
    return 0
  fi
  log "teardown: TERM rviz -> patrol -> nav2 -> gazebo"
  signal_pid "$RVIZ_PID" TERM # 先关可视化：避免它订阅着正在消亡的话题刷一堆错误
  signal_pid "$PATROL_PID" TERM
  signal_pid "$NAV2_PID" TERM
  signal_pid "$GAZEBO_PID" TERM
  signal_pid "$CAPTURE_PID" TERM
  # 这里刻意保留二次确认（默认 8 s）：只有「停 daemon 重建图后仍报发布者」才打转 KILL 日志，
  #   否则这句话会把「缓存还没剔除」误写成「TERM 没生效」，掩盖真实原因。
  # 代价：TERM 真没生效时多花约 10 s（2 s 停 daemon + 8 s 确认窗），只在慢路径上出现。
  wait_topics_gone || log "teardown: TERM 后 20s + daemon 重建确认仍报发布者，转 KILL"
  for pid in "$RVIZ_PID" "$PATROL_PID" "$NAV2_PID" "$GAZEBO_PID" "$CAPTURE_PID"; do
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
sleep 2.5 # 对齐 gazebo.sh：等 Nav2 内部组件把 /scan /map /tf 发布起来，RViz 才有东西可订阅

# S2.5 启动可视化：刻意排在 S3 就绪检查之前，顺序与 gazebo.sh 一致
#   （gazebo.sh 为 gazebo -> sleep3 -> nav2 -> sleep2.5 -> rviz -> 最后才起巡逻）
# 为什么必须提前，而不是放在巡逻启动前几秒：
#   rviz2 启动瞬间要做三件重活——编译 GLSL 着色器、上传 202x161 地图 swatch、填满 TF 缓存，
#   CPU 会有一个明显峰值。若这个峰值正好压在 patrol 的 init_robot_pose 上
#   （waitUntilNav2Active 要连续查 TF 与 costmap），实测会让 scan/TF 消息积压超过
#   TF 缓存 10 s 窗口，costmap 整帧丢弃（日志刷 "timestamp earlier than all the data
#   in the transform cache"），巡逻永久等不到激活，表现为「半天不开始巡航」。
#   提前到 S3 之前，让 RViz 的初始化与 S3 的就绪等待重叠，巡逻启动时它已稳定。
if [ "$RVIZ" -eq 1 ]; then
  if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    log "rviz: 无图形环境(DISPLAY 未设置)，跳过可视化；如需远程请看日志或改用 RViz 远程连接"
  else
    log "launching rviz2"
    setsid ros2 run rviz2 rviz2 \
      -d /opt/ros/humble/share/nav2_bringup/rviz/nav2_default_view.rviz \
      --ros-args -p use_sim_time:=true > "$LOG_DIR/rviz.log" 2>&1 &
    RVIZ_PID=$!
    sleep 2.5
    # 启动失败要立刻说出来，而不是留一个死进程让人以为在看画面
    if kill -0 "$RVIZ_PID" 2>/dev/null; then
      log "rviz2 up: pid=$RVIZ_PID"
    else
      log "rviz2 exited early, see $LOG_DIR/rviz.log"
      RVIZ_PID=
    fi
  fi
else
  log "rviz: 已按 --no-rviz 关闭可视化"
fi

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

# S4.5 RViz 预热确认：等主地图渲染完成再起巡逻
# 判据用日志探针而非固定 sleep：rviz.log 出现 "Trying to create a map" 说明主地图 swatch
#   已上传，GLSL 编译与地图加载这两个 CPU 峰值已过；此时起巡逻不会与它抢资源。
# 为什么设上限而非无限等：RViz 慢不该阻断实验，超时仍继续，只记录告警便于事后归因。
# 为什么上限取 15 s：实测 RViz 从启动到打出该行约 2~6 s（含 GLSL 报错重试），
#   15 s 留 2 倍余量；再长说明 RViz 异常，继续等也无意义。
if [ -n "$RVIZ_PID" ]; then
  rviz_deadline=$((SECONDS + RVIZ_WARMUP))
  while [ $SECONDS -lt $rviz_deadline ]; do
    grep -q "Trying to create a map" "$LOG_DIR/rviz.log" 2>/dev/null && break
    sleep 0.5
  done
  if grep -q "Trying to create a map" "$LOG_DIR/rviz.log" 2>/dev/null; then
    log "rviz warmup done: 主地图已渲染"
  else
    log "rviz warmup timeout ${RVIZ_WARMUP}s: 地图未渲染完成，继续跑（RViz 慢不应阻断实验）"
  fi
fi

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