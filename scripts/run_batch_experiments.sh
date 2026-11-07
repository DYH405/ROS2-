#!/bin/bash
# =============================================================================
# T-P1-02B 批量串行实验脚本
#
# 职责：外部循环调用 scripts/run_one_experiment.sh（每轮内部已自带重启 Gazebo），
#       每轮结束后立刻做轻量 valid 判定，按四条规则记 invalid，并按熔断条件停机。
#
# 硬约束（来自任务卡）：
#   - 不修改 run_one_experiment.sh 任何内部逻辑，只做外部调用
#   - valid 计数权威来源 = baseline_summary.csv（--all 全量扫描），ledger 只记执行流水
#   - 每轮新建目录用「批前快照 → 批后 diff」识别，禁用 ls -dt | head -1
#   - invalid 轮原始数据一律保留，绝不删除
#   - 分批执行：BATCH_N 指定本次最多跑几轮，跑完即停
#
# 参数（全部用环境变量覆盖，均有默认值）：
#   TARGET_VALID        目标 valid 轮数，默认 10（N=10 指 valid 轮数，不是总轮数）
#   MAX_RUNS            总轮数上限（含历史），默认 15
#   RUN_TIMEOUT         单轮外层硬超时，默认 900 s（=15 min），到点强制终止记 invalid
#   PATROL_TIMEOUT      透传给 run_one_experiment.sh 的巡逻超时，默认 840 s（早于外层，让内层先干净退出）
#   MAX_CONSEC_INVALID  连续 invalid 熔断阈值，默认 3
#   BATCH_N             本批最多跑几轮，默认 0 表示不限（跑满额度或触发熔断）
#   BATCH_ID            本批标识，默认取当前时间戳
# =============================================================================
set -u                                  # 未定义变量即报错，避免静默用空值；不用 -e，因为要捕获非 0 退出码

WS=/home/robot/ros2_ws                   # 工作空间根目录
LOG_ROOT=$WS/experiment_logs             # 实验日志根目录
ONE=$WS/scripts/run_one_experiment.sh    # 单轮脚本（本脚本唯一调用对象，只读）
SUM=$WS/scripts/summarize_baseline.py    # 汇总/判定脚本（规则只在那里实现一份）
SUMMARY_CSV=$LOG_ROOT/baseline_summary.csv   # valid 计数权威来源（M1）
LEDGER=$LOG_ROOT/batch_ledger.csv        # 本批执行流水（只记 batch_id/seq/run_id/log_dir/exit_code/elapsed）

TARGET_VALID=${TARGET_VALID:-10}         # 目标 valid 轮数
MAX_RUNS=${MAX_RUNS:-15}                 # 采样额度上限（D7-B：只计有 truth.log 的轮）
RUN_TIMEOUT=${RUN_TIMEOUT:-900}          # 单轮外层硬超时（秒）
PATROL_TIMEOUT=${PATROL_TIMEOUT:-840}    # 内层巡逻超时（秒），透传给 run_one
MAX_CONSEC_INVALID=${MAX_CONSEC_INVALID:-3}   # 连续 invalid 熔断阈值
BATCH_N=${BATCH_N:-0}                    # 本批轮数上限，0 = 不限
BATCH_ID=${BATCH_ID:-$(date +%Y%m%d_%H%M%S)}  # 本批唯一标识
BATCH_RUN_TS=$(date +%Y%m%d_%H%M%S)      # 本批启动时刻，用于单轮输出文件名去重
                                          # （P2：原文件名 batch_${BATCH_ID}_${SEQ}.out 在
                                          #   同 BATCH_ID 重复执行时会被后一次覆盖，批 1c 事故后
                                          #   只剩 3 个 out 文件而 ledger 有 6 条，故加入启动时刻）

STOP_REASON=''                           # 停机原因，供结尾汇总打印
CONSEC_INVALID=0                         # 本批连续 invalid 计数（跨轮累计，valid 即清零）
SEQ=0                                    # 本批已跑轮数

log() { printf '%s\n' "$*"; }            # 统一输出入口，便于后续改写到文件


# ---------- D9：单实例互斥锁 ----------
# 背景（批 1c 事故）：同一批命令被重复执行，两套批脚本并发抢占同一个 Gazebo，
#   互相 pkill 对方的节点，capture_truth_pose 读到同一个 patrol_runs 末行，
#   于是同一 run_id 写出多份 truth.log，completed 虚增、末点被交叉污染。
# 做法：对固定锁文件加非阻塞排他锁；第二个实例立即退出，不进入主循环。
#   锁随脚本进程退出自动释放，无需手工删锁文件（fd 9 一直持有到进程结束）。
LOCK_FILE=$LOG_ROOT/.batch_run.lock
exec 9>"$LOCK_FILE" || { printf '%s\n' "[ABORT] 无法创建锁文件：$LOCK_FILE"; exit 1; }
if ! flock -n 9; then
  printf '%s\n' "[ABORT] 已有批脚本在运行（锁文件 $LOCK_FILE），本次退出，避免并发污染"
  printf '%s\n' "        确认无残留后可等待其结束；锁会自动释放，不要手工删除锁文件"
  exit 1
fi
printf '%s\n' "$$" > "$LOCK_FILE"       # 写入持有者 PID，便于事后排查是谁占着锁


# 从 baseline_summary.csv 统计 valid=1 的行数（M1：唯一权威来源，不读 ledger）
# D8 修正：note 含 dup_of 的行是并发重复采样，不计入 valid（与 summarize 的统计口径一致）
count_valid() {
  python3 - "$SUMMARY_CSV" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8')))
print(sum(1 for r in rows
          if r.get('valid') == '1' and 'dup_of=' not in (r.get('note') or '')))
PY
}

# 统计「有 truth.log 的轮数」= 采样额度已用轮数
# D7-B 修正：无真值的超时轮（note 含 no_truth）不占 MAX_RUNS 额度，
# 否则 S5 超时轮会白吃槽位，导致 valid 目标在算术上不可达
# D8 修正：并发重复行（note 含 dup_of）同样不占额度
count_completed() {
  python3 - "$SUMMARY_CSV" <<'PY'
import csv, sys
n = 0
for r in csv.DictReader(open(sys.argv[1], encoding='utf-8')):
    note = r.get('note') or ''
    if 'no_truth' in note or 'dup_of=' in note:
        continue
    n += 1
print(n)
PY
}

# 批前/批后目录快照：只列目录名并排序（M2，替代 ls -dt | head -1）
snapshot_dirs() {
  find "$LOG_ROOT" -maxdepth 1 -type d -name 'run_one_*' -printf '%f\n' 2>/dev/null | sort
}

# git 工作区快照：用于熔断条件 d（计划外文件改动检测）
git_snapshot() {
  ( cd "$WS" && git status --short 2>/dev/null | sort )
}

# 写 ledger 表头（仅在文件不存在时写，避免覆盖历史批次记录）
init_ledger() {
  [ -f "$LEDGER" ] || echo 'batch_id,seq,run_id,log_dir,exit_code,elapsed' > "$LEDGER"
}

# 追加一条执行流水：只记 6 个执行事实字段，不含判定结论（判定结论以 summary 为准）
append_ledger() {
  printf '%s,%s,%s,%s,%s,%s\n' "$BATCH_ID" "$1" "$2" "$3" "$4" "$5" >> "$LEDGER"
}

# 刷新 summary（--no-md 快刷，不写报告），stdout 丢弃以免每轮刷屏
refresh_summary_fast() {
  python3 "$SUM" --all --no-md > /dev/null 2>&1
}


log "=================================================================="
log "[BATCH $BATCH_ID] TARGET_VALID=$TARGET_VALID MAX_RUNS=$MAX_RUNS BATCH_N=$BATCH_N"
log "[BATCH $BATCH_ID] RUN_TIMEOUT=${RUN_TIMEOUT}s PATROL_TIMEOUT=${PATROL_TIMEOUT}s MAX_CONSEC_INVALID=$MAX_CONSEC_INVALID"
log "=================================================================="

# ---------- 前置检查 ----------
if [ ! -x "$ONE" ] && [ ! -f "$ONE" ]; then
  log "[ABORT] 缺少单轮脚本：$ONE"
  exit 1
fi
if [ ! -f "$SUM" ]; then
  log "[ABORT] 缺少汇总脚本：$SUM"
  exit 1
fi

init_ledger                                    # 首次运行写表头

# M1：启动时先做一次全量 --all，把 valid 计数建立起来，再读
refresh_summary_fast
VALID_NOW=$(count_valid)
COMPLETED_NOW=$(count_completed)
log "[PRE] completed_runs=$COMPLETED_NOW valid_runs=$VALID_NOW (源：baseline_summary.csv，completed 只计有 truth.log 的轮)"

# 前置熔断：已经达成目标或额度已满，直接退出，不浪费一次 Gazebo 启动
if [ "$VALID_NOW" -ge "$TARGET_VALID" ]; then
  log "[STOP] target_valid_reached（前置）：valid=$VALID_NOW >= $TARGET_VALID"
  exit 0
fi
if [ "$COMPLETED_NOW" -ge "$MAX_RUNS" ]; then
  log "[STOP] max_runs_reached（前置）：completed=$COMPLETED_NOW >= $MAX_RUNS"
  exit 0
fi

GIT_BEFORE=$(git_snapshot)                     # 熔断 d 基线：批前工作区状态
if [ -n "$GIT_BEFORE" ]; then
  log "[PRE] git 工作区非空（$(printf '%s\n' "$GIT_BEFORE" | wc -l) 项），将逐轮比对是否新增改动"
fi

DIRS_BEFORE=$(snapshot_dirs)                   # M2 基线：批前已有 run 目录清单

# ---------- 主循环 ----------
while :; do
  # 每轮开头刷新一次计数，保证熔断判断用的是最新权威数据
  refresh_summary_fast
  VALID_NOW=$(count_valid)
  COMPLETED_NOW=$(count_completed)

  if [ "$VALID_NOW" -ge "$TARGET_VALID" ]; then
    STOP_REASON="target_valid_reached（valid=$VALID_NOW >= $TARGET_VALID）"
    break
  fi
  if [ "$COMPLETED_NOW" -ge "$MAX_RUNS" ]; then
    STOP_REASON="max_runs_reached（completed=$COMPLETED_NOW >= $MAX_RUNS）"
    break
  fi
  if [ "$CONSEC_INVALID" -ge "$MAX_CONSEC_INVALID" ]; then
    STOP_REASON="consec_invalid（连续 $CONSEC_INVALID 轮 invalid >= $MAX_CONSEC_INVALID）"
    break
  fi
  if [ "$BATCH_N" -gt 0 ] && [ "$SEQ" -ge "$BATCH_N" ]; then
    STOP_REASON="batch_done（本批已跑 $SEQ 轮，BATCH_N=$BATCH_N）"
    break
  fi

  SEQ=$((SEQ + 1))
  log "[RUN $SEQ] start | completed=$COMPLETED_NOW valid=$VALID_NOW consec_invalid=$CONSEC_INVALID"

  DIRS_PRE=$(snapshot_dirs)                    # 单轮前快照
  T0=$SECONDS                                  # 单轮计时起点

  # 外层硬超时：-k 30 表示 TERM 后 30 s 仍未退出则 KILL，防残留 gzserver
  PATROL_TIMEOUT=$PATROL_TIMEOUT timeout -k 30 "$RUN_TIMEOUT" bash "$ONE" \
      > "$LOG_ROOT/batch_${BATCH_ID}_${BATCH_RUN_TS}_${SEQ}.out" 2>&1
  RC=$?                                        # run_one 退出码（124 = 被外层 timeout 杀掉）
  ELAPSED=$((SECONDS - T0))                    # 单轮实际耗时

  # M2：批后 diff 找本轮新建目录，不再依赖时间戳猜测
  DIRS_POST=$(snapshot_dirs)
  NEW_DIRS=$(comm -13 <(printf '%s\n' "$DIRS_PRE") <(printf '%s\n' "$DIRS_POST"))
  NEW_DIR=$(printf '%s\n' "$NEW_DIRS" | grep -v '^$' | sort | tail -n 1)   # 理论上只会有一个

  if [ -z "$NEW_DIR" ]; then
    # 目录没建出来 = 本轮彻底失败，无数据可判，直接记 invalid 并计数
    log "[RUN $SEQ] result=INVALID(no_dir) rc=$RC elapsed=${ELAPSED}s"
    append_ledger "$SEQ" "-" "-" "$RC" "$ELAPSED"
    CONSEC_INVALID=$((CONSEC_INVALID + 1))
  else
    # 判定交给 summarize_baseline.py --judge（M3：固定 8 个 | 字段）
    JUDGE_LINE=$(python3 "$SUM" --judge "$LOG_ROOT/$NEW_DIR" --rc "$RC" 2>/dev/null)
    IFS='|' read -r J_VALID J_RUNID J_DIR J_RC J_REASON J_POS J_MAXDEV J_JUMP <<< "$JUDGE_LINE"

    if [ "$J_VALID" = "1" ]; then
      CONSEC_INVALID=0                         # 出现 valid 即清零连续计数
      RESULT=VALID
    else
      CONSEC_INVALID=$((CONSEC_INVALID + 1))
      RESULT=INVALID
    fi

    # 单行摘要：run_id / 退出码 / 判定 / 原因 / 耗时 / 关键偏差，不刷屏
    log "[RUN $SEQ] run_id=$J_RUNID rc=$RC $RESULT reason=${J_REASON:--} pos_err=${J_POS:--} max_dev=${J_MAXDEV:--} jump=${J_JUMP:--} ${ELAPSED}s"
    append_ledger "$SEQ" "$J_RUNID" "$NEW_DIR" "$RC" "$ELAPSED"

    # 熔断 c：单轮超过外层超时被强杀，单独告警（该轮已因 rc=124 被规则 d 判 invalid）
    [ "$RC" -eq 124 ] && log "[WARN] run_timeout: 本轮超过 ${RUN_TIMEOUT}s 被强制终止，已记 invalid，原始数据保留于 $NEW_DIR"
  fi

  # 熔断 d：每轮结束比对 git 工作区，出现新增改动立即停机并报告
  GIT_AFTER=$(git_snapshot)
  if [ "$GIT_AFTER" != "$GIT_BEFORE" ]; then
    log "[FATAL] unexpected_file_change：检测到计划外文件改动，立即停机"
    printf '%s\n' "$GIT_AFTER" | grep -vxF "$GIT_BEFORE" | sed 's/^/    + /'
    STOP_REASON="unexpected_file_change"
    break
  fi
done

# ---------- 收尾 ----------
refresh_summary_fast                            # 确保 summary 是最新（含刚跑完的轮）
log ""
log "[STOP] ${STOP_REASON:-unknown}"
python3 "$SUM" --all                            # 批末写 md 报告，stdout 固定 3 行

# 熔断自检提示：不真实触发也能人工验证
log ""
log "[HINT] 熔断验证方法（不真实触发）:"
log "  MAX_RUNS=$COMPLETED_NOW BATCH_N=1  -> 首轮即停 max_runs_reached"
log "  TARGET_VALID=$VALID_NOW BATCH_N=1  -> 首轮即停 target_valid_reached"
log "  MAX_CONSEC_INVALID=1 BATCH_N=1     -> 首轮 invalid 即停 consec_invalid"
log "[DONE] batch=$BATCH_ID seq=$SEQ ledger=$LEDGER"
exit 0