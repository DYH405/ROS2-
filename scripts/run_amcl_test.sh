#!/bin/bash
# =============================================================================
# AMCL 参数对照测试（单轮）
#
# 职责：
#   1) 互斥 + 残留检查：发现已有仿真/批量实验在跑就拒绝启动，绝不 pkill 别人的进程
#   2) 复用 gazebo.sh 启动 Gazebo + Nav2 + RViz2（与基线完全同构，RViz2 默认开启）
#   3) 记录本轮实际生效的 AMCL 参数 -> params_snapshot.txt
#      —— 没有这份快照，事后无法证明这一轮跑的是哪套配置
#   4) capture_truth_pose.py --watch 连续采样 -> pose_trace.csv
#      列: t_sec,gt_x,gt_y,gt_yaw,amcl_x,amcl_y,amcl_yaw（每 SAMPLE_PERIOD 秒一行）
#   5) 订阅 /behavior_tree_log -> bt_log.txt
#      —— 把 "Running Spin / Backing Up / Clearing costmap" 这类恢复行为
#         从终端文字变成可 grep 的记录，避免只靠肉眼
#   6) ros2 launch autopartol_robot autopartol.launch.py 启动真实巡航节点
#      —— 与批量实验完全同一条链路：10 个固定航点、单轮、失败重试 2 次，
#         不做任何自造的简化，保证本轮数据与既有 patrol_runs 可比
#   7) 巡逻结束后把新增的 patrol_runs 行抽到本轮目录，并把共享 CSV 还原
#      —— 避免把不同 AMCL 参数的记录混进批量实验数据集
#   8) Ctrl+C 时按 pose_trace.csv 算末点误差 -> summary.txt
#
# 用法：
#   TAG=baseline ~/ros2_ws/scripts/run_amcl_test.sh
#   TAG=zhit090  ~/ros2_ws/scripts/run_amcl_test.sh
#   HOLD=0      巡逻跑完即自动退出并出汇总（默认 1，保持仿真供人工观察）
#
# 输出目录：~/ros2_ws/experiment_logs/amcl_test/<时间戳>_<TAG>/
#   params_snapshot.txt  本轮生效参数 + yaml 校验和
#   pose_trace.csv       连续采样轨迹（核心数据）
#   bt_log.txt           行为树事件（恢复行为的机器可读证据）
#   patrol_run.csv       本轮巡逻在 patrol_runs.csv 中新增的行
#   patrol.log           巡航节点终端输出
#   summary.txt          末点误差汇总
#   run.log              本脚本执行流水
# 刻意与批量的 patrol_runs.csv / baseline_summary.csv 完全隔离，不污染既有数据
# =============================================================================
set -u

WS=/home/robot/ros2_ws

# ROS 环境：setup.bash 内部会引用未定义变量（COLCON_TRACE 等），临时关掉 set -u
set +u
[ -f /opt/ros/humble/setup.bash ] && source /opt/ros/humble/setup.bash
[ -f "$WS/install/setup.bash" ] && source "$WS/install/setup.bash"
set -u

GAZEBO_SH=$WS/src/pkg03_gazebo_20260814/scripts/gazebo.sh
CAPTURE=$WS/scripts/capture_truth_pose.py
NAV2_PARAMS=$WS/src/pkg03_gazebo_20260814/config/nav2_params_hybrid.yaml

TAG=${TAG:-manual}                      # 本轮标签，写进目录名，用于区分参数组
SAMPLE_PERIOD=${SAMPLE_PERIOD:-0.5}     # 采样周期(s)
READY_TIMEOUT=${READY_TIMEOUT:-90}      # 等话题/action 就绪的超时(s)
PATROL_TIMEOUT=${PATROL_TIMEOUT:-900}   # 一轮巡逻总超时(s)：10 个点，每点最多 60s×3 次重试
HOLD=${HOLD:-1}                         # 1=跑完保持仿真等 Ctrl+C；0=跑完自动退出

PATROL_CSV=$WS/experiment_logs/patrol_runs.csv   # 巡航节点默认落盘位置（共享给批量实验）

LOG_ROOT=$WS/experiment_logs/amcl_test
LOCK_FILE=$LOG_ROOT/.amcl_test.lock
RUN_TS=$(date +%Y%m%d_%H%M%S)
RUN_DIR=$LOG_ROOT/${RUN_TS}_${TAG}
TRACE=$RUN_DIR/pose_trace.csv
SNAPSHOT=$RUN_DIR/params_snapshot.txt
SUMMARY=$RUN_DIR/summary.txt
BT_LOG=$RUN_DIR/bt_log.txt
PATROL_COPY=$RUN_DIR/patrol_run.csv            # 本轮巡逻新增行的副本
PATROL_BAK=$RUN_DIR/patrol_runs.csv.bak        # 共享 CSV 原样备份

GAZEBO_SH_PID=''
WATCH_PID=''
BT_PID=''
PATROL_PID=''
ROWS_BEFORE=0                           # 巡逻前共享 CSV 行数，用于识别本轮新增行
LAUNCHED=0                              # 0=尚未启动任何进程，cleanup 据此跳过全局清理
FINALIZED=0

mkdir -p "$LOG_ROOT" || exit 1

log() { printf '%s\n' "$*" | tee -a "$RUN_DIR/run.log"; }

# ---------- 单实例互斥：同一时刻只允许一份测试 ----------
exec 9>"$LOCK_FILE" || { echo "[ABORT] 无法创建锁文件 $LOCK_FILE"; exit 1; }
if ! flock -n 9; then
  echo "[ABORT] 已有本脚本的另一实例在运行，退出"
  exit 1
fi

# ---------- 残留检查：只检查不清理，绝不误杀别人的进程 ----------
# gazebo.sh 内含 pkill -9 -f gzserver 与 rm -rf /dev/shm/gz*，均为全机匹配；
# 若此时批量实验在跑，启动它会直接打断对方，故此处先拒绝启动。
RESIDUAL=$(pgrep -af "gzserver|gzclient|nav2_container|nav2_bringup|run_one_experiment|run_batch_experiments" 2>/dev/null || true)
if [ -n "$RESIDUAL" ]; then
  echo "[ABORT] 检测到已有仿真或批量实验进程，拒绝启动（避免互相 pkill 误伤）："
  printf '%s\n' "$RESIDUAL"
  echo "        确认这些进程可以结束后再运行本脚本"
  exit 1
fi

mkdir -p "$RUN_DIR"
log "RUN_DIR=$RUN_DIR"
log "TAG=$TAG  SAMPLE_PERIOD=${SAMPLE_PERIOD}s"

# 巡逻前先备份共享 CSV 并记下行数，作为「本轮新增行」的基线
PATROL_CSV_EXISTED=0
if [ -f "$PATROL_CSV" ]; then
  cp -f "$PATROL_CSV" "$PATROL_BAK"
  ROWS_BEFORE=$(wc -l < "$PATROL_CSV" | tr -d ' ')
  PATROL_CSV_EXISTED=1
fi
log "[BASE] patrol_runs.csv 基线行数=$ROWS_BEFORE existed=$PATROL_CSV_EXISTED"

# ---------- 抽取本轮巡逻记录：共享 CSV 只增不减地混入不同参数组的数据 ----------
# 巡航节点把结果写死到 ~/ros2_ws/experiment_logs/patrol_runs.csv（yaml 里配置），
# 而该文件同时是批量实验的数据集。本函数把新增行复制到本轮目录，再把共享文件
# 还原成运行前的样子 —— 数据不丢（副本留在 run 目录），批量数据集不被污染。
harvest_patrol_row() {
  [ -f "$PATROL_CSV" ] || return 0
  local now
  now=$(wc -l < "$PATROL_CSV" | tr -d ' ')
  if [ "$now" -gt "$ROWS_BEFORE" ]; then
    tail -n $((now - ROWS_BEFORE)) "$PATROL_CSV" > "$PATROL_COPY"
    echo ""
    echo "[PATROL] 本轮新增 $((now - ROWS_BEFORE)) 行，已复制到 $PATROL_COPY"
    cat "$PATROL_COPY"
  else
    echo "[PATROL] 本轮未产生新记录（巡航可能超时或被中断）"
  fi
  if [ "$PATROL_CSV_EXISTED" -eq 1 ]; then
    cp -f "$PATROL_BAK" "$PATROL_CSV"       # 还原共享 CSV
    echo "[PATROL] 已还原 $PATROL_CSV 到运行前状态"
  else
    rm -f "$PATROL_CSV"                     # 原本不存在，删掉本轮新建的文件
    echo "[PATROL] 共享 CSV 原本不存在，已删除本轮新建文件"
  fi
}

# ---------- 汇总：只读 pose_trace.csv，不依赖仿真是否还在 ----------
finalize() {
  [ "$FINALIZED" -eq 1 ] && return 0
  FINALIZED=1
  if [ ! -f "$TRACE" ]; then
    echo "[SUMMARY] 未产生 $TRACE，跳过汇总"
    harvest_patrol_row
    return 0
  fi
  python3 - "$TRACE" > "$SUMMARY" 2>&1 <<'PY'
import csv, math, sys

def yaw_err(a, b):                      # 角度差归一化到 [-180,180]，避免 ±pi 跳变假象
    d = math.degrees(a - b)
    return (d + 180.0) % 360.0 - 180.0

rows = []
with open(sys.argv[1], encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f):
        try:
            rows.append((float(r['t_sec']), float(r['gt_x']), float(r['gt_y']),
                         float(r['gt_yaw']), float(r['amcl_x']),
                         float(r['amcl_y']), float(r['amcl_yaw'])))
        except (KeyError, ValueError, TypeError):
            continue                   # 采样早期 amcl 未到，整行空，跳过

if not rows:
    print('[FAIL] pose_trace.csv 中没有同时含 gt 与 amcl 的完整行')
    raise SystemExit(0)

dur = rows[-1][0] - rows[0][0]
print('采样行数 = %d   时长 = %.1f s' % (len(rows), dur))

maxpos, maxpos_t = 0.0, 0.0
ymin, ymax = 999.0, -999.0
for t, gx, gy, gyaw, ax, ay, ayaw in rows:
    p = math.hypot(ax - gx, ay - gy)
    if p > maxpos:
        maxpos, maxpos_t = p, t
    e = yaw_err(ayaw, gyaw)
    ymin, ymax = min(ymin, e), max(ymax, e)

t, gx, gy, gyaw, ax, ay, ayaw = rows[-1]
print('')
print('--- 末点 ---')
print('真值  x=%.3f y=%.3f yaw=%.1f deg' % (gx, gy, math.degrees(gyaw)))
print('AMCL  x=%.3f y=%.3f yaw=%.1f deg' % (ax, ay, math.degrees(ayaw)))
print('末点位置误差 = %.3f m   (dx=%+.3f dy=%+.3f)'
      % (math.hypot(ax - gx, ay - gy), ax - gx, ay - gy))
print('末点 yaw 误差 = %+.2f deg' % yaw_err(ayaw, gyaw))
print('')
print('--- 全程 ---')
print('最大位置误差 = %.3f m   (出现在 t=%.1f s)' % (maxpos, maxpos_t))
print('yaw 误差区间 = %+.2f ~ %+.2f deg' % (ymin, ymax))
print('')
print('--- 误差随进度抽样（每 10% 一行）---')
step = max(1, len(rows) // 10)
for i in range(0, len(rows), step):
    t, gx, gy, gyaw, ax, ay, ayaw = rows[i]
    print('t=%5.1f s  位置误差=%7.3f m  yaw误差=%+6.2f deg'
          % (t, math.hypot(ax - gx, ay - gy), yaw_err(ayaw, gyaw)))
PY
  echo ""
  echo "[SUMMARY] 已写入 $SUMMARY"
  cat "$SUMMARY"
  # 正常跑完的分支也必须抽行+还原共享 CSV。
  #   原实现只在上面「无 trace」的早退分支里调用 harvest_patrol_row，
  #   导致本轮巡逻记录既没复制到 RUN_DIR，共享 patrol_runs.csv 也没被还原，
  #   那行记录会一直留在批量实验的数据集里造成污染。
  harvest_patrol_row
}

# ---------- 收尾 ----------
cleanup() {
  echo ""
  echo "[CLEANUP] 开始收尾"
  if [ "$LAUNCHED" -eq 0 ]; then
    echo "[CLEANUP] 本轮未启动任何进程，跳过进程清理"
    exit 0
  fi
  # 先停本轮后台进程，再汇总：否则巡航节点可能在我们读 CSV 的同时写入
  for pid in "$WATCH_PID" "$BT_PID" "$PATROL_PID"; do
    [ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null
  done
  sleep 1
  finalize
  if [ -n "$GAZEBO_SH_PID" ] && kill -0 "$GAZEBO_SH_PID" 2>/dev/null; then
    echo "[CLEANUP] 通知 gazebo.sh 自行清理（其 trap 会关闭 RViz2/Nav2/Gazebo）"
    kill -TERM "$GAZEBO_SH_PID" 2>/dev/null
    sleep 3
    kill -9 "$GAZEBO_SH_PID" 2>/dev/null
  fi
  pkill -9 -f nav2_container 2>/dev/null
  pkill -9 -f gzserver 2>/dev/null
  pkill -9 -f gzclient 2>/dev/null
  rm -rf /dev/shm/gz* /dev/shm/rmw* 2>/dev/null
  echo "[CLEANUP] 完成"
  exit 0
}
trap cleanup INT TERM

wait_for_topic() {                      # $1 话题 $2 超时秒
  local topic=$1 timeout=${2:-60} elapsed=0
  while [ $elapsed -lt "$timeout" ]; do
    if ros2 topic list 2>/dev/null | grep -q -- "$topic"; then
      log "[READY] topic $topic (${elapsed}s)"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

# ---------- S1 启动仿真（不重定向输出，保证 Nav2/RViz 日志实时可见）----------
log "[S1] 启动 Gazebo + Nav2 + RViz2（复用 gazebo.sh）"
"$GAZEBO_SH" 9>&- &                  # 9>&- : 不把锁 fd 传给子进程，避免硬杀后锁悬挂
GAZEBO_SH_PID=$!
LAUNCHED=1
sleep 5

# ---------- S2 等待就绪 ----------
for t in /scan /odom /amcl_pose /gazebo/model_states; do
  if ! wait_for_topic "$t" "$READY_TIMEOUT"; then
    log "[FAIL] 话题 $t 在 ${READY_TIMEOUT}s 内未出现，终止"
    exit 4
  fi
done
elapsed=0
while [ $elapsed -lt "$READY_TIMEOUT" ]; do
  if ros2 action list 2>/dev/null | grep -q "navigate_to_pose"; then
    log "[READY] action navigate_to_pose (${elapsed}s)"
    break
  fi
  sleep 1
  elapsed=$((elapsed + 1))
done
[ $elapsed -lt "$READY_TIMEOUT" ] || { log "[FAIL] navigate_to_pose 未就绪"; exit 4; }

# ---------- S3 参数快照（本轮配置的凭证）----------
{
  echo "# 采集时间: $(date '+%F %T')"
  echo "# yaml: $NAV2_PARAMS"
  echo "# yaml md5: $(md5sum "$NAV2_PARAMS" 2>/dev/null | awk '{print $1}')"
  echo "# 说明: 以下为 AMCL 节点运行时真实生效值（ros2 param get），"
  echo "#       与 yaml 文件内容可能不同：顶层 key 与节点名不匹配时会静默不加载"
  echo ""
  for p in sigma_hit laser_max_range laser_min_range laser_likelihood_max_dist \
           max_beams z_hit z_rand z_max z_short lambda_short laser_model_type \
           do_beamskip alpha1 alpha2 alpha3 alpha4 alpha5 \
           update_min_d update_min_a min_particles max_particles \
           pf_err pf_z resample_interval recovery_alpha_fast recovery_alpha_slow \
           transform_tolerance tf_broadcast odom_frame_id global_frame_id base_frame_id; do
    v=$(ros2 param get /amcl "$p" 2>/dev/null | sed 's/.*value is //')
    printf '%-30s %s\n' "$p" "${v:-GET_FAILED}"
  done
} > "$SNAPSHOT" 2>&1
log "[S3] 参数快照已写入 $SNAPSHOT"
sed -n '1,16p' "$SNAPSHOT" | tee -a "$RUN_DIR/run.log"

# ---------- S4 启动连续采样 ----------
log "[S4] 启动连续采样（周期 ${SAMPLE_PERIOD}s）"
python3 "$CAPTURE" --watch --json "$RUN_DIR/pose_cache.json" --period "$SAMPLE_PERIOD" \
  9>&- > "$RUN_DIR/pose_watch.log" 2>&1 &
WATCH_PID=$!

# ---------- S5 行为树事件记录（恢复行为的机器可读证据）----------
python3 - "$BT_LOG" 9>&- > "$RUN_DIR/bt_node.log" 2>&1 <<'PY' &
import sys, rclpy
from nav2_msgs.msg import BehaviorTreeLog

path = sys.argv[1]
KEYS = ('Spin', 'BackUp', 'Clear', 'Recovery')
fh = open(path, 'w', encoding='utf-8')

rclpy.init()
node = rclpy.create_node('bt_event_logger')

def cb(msg):
    for e in msg.event_log:
        if e.current_status == 'RUNNING':
            continue                   # 只记终态，RUNNING 太吵
        hit = e.current_status == 'FAILURE' or any(k in e.node_name for k in KEYS)
        if hit:
            fh.write('%.3f %-40s %-8s -> %s\n'
                     % (msg.timestamp.sec + msg.timestamp.nanosec * 1e-9,
                        e.node_name, e.previous_status, e.current_status))
            fh.flush()

node.create_subscription(BehaviorTreeLog, '/behavior_tree_log', cb, 10)
try:
    rclpy.spin(node)
except BaseException:
    pass
finally:
    fh.close()
PY
BT_PID=$!

sleep 2

# ---------- S6 启动真实巡航（与批量实验同一条链路）----------
# partol_node 继承 BasicNavigator：自己 setInitialPose(0,0,0) + waitUntilNav2Active，
# 然后按 partol_config.yaml 的 10 个航点走一轮（max_rounds: 1），
# 每点导航超时 60 s、失败重试 nav_retry_count=2 次，
# 跑完把一行汇总写进 patrol_runs.csv 后自行退出。
# 注意：不要在这里再发 setInitialPose，两处同时设初始位姿会让 AMCL 粒子重新撒，
#       前半段的收敛过程被抹掉，轨迹数据就不可比了。
log "[S6] 启动巡航节点 ros2 launch autopartol_robot autopartol.launch.py"
ros2 launch autopartol_robot autopartol.launch.py 9>&- > "$RUN_DIR/patrol.log" 2>&1 &
PATROL_PID=$!
sleep 3

# 等待本轮记录落盘（巡航跑完才写，这是唯一可靠的完成信号）
deadline=$((SECONDS + PATROL_TIMEOUT))
rows_now=$ROWS_BEFORE
while [ $SECONDS -lt $deadline ]; do
  if [ -f "$PATROL_CSV" ]; then
    rows_now=$(wc -l < "$PATROL_CSV" | tr -d ' ')
    if [ "$rows_now" -gt "$ROWS_BEFORE" ]; then
      log "[S6] 本轮巡逻已落盘：行数 $ROWS_BEFORE -> $rows_now"
      break
    fi
  fi
  if ! kill -0 "$PATROL_PID" 2>/dev/null; then
    log "[WARN] 巡航节点提前退出，未写记录（见 $RUN_DIR/patrol.log）"
    break
  fi
  sleep 5
done
[ "$rows_now" -gt "$ROWS_BEFORE" ] || log "[WARN] 巡逻在 ${PATROL_TIMEOUT}s 内未产生记录"

log "[S6] 巡航流程结束，见 $RUN_DIR/patrol.log"

if [ "$HOLD" -eq 1 ]; then
  echo ""
  echo "=============================================================="
  echo " 巡航已结束，仿真保持运行（可在 RViz2 中观察）"
  echo " 按 Ctrl+C 结束 -> 自动汇总末点误差并关闭全部进程"
  echo "=============================================================="
  while :; do sleep 1; done
else
  log "[S7] HOLD=0，自动收尾"
  cleanup
fi