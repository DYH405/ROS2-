#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-P1-02B 基线汇总脚本。

三种用法（互斥，一次只跑一种）：
  1) python3 summarize_baseline.py --all
       扫描 experiment_logs/ 下全部 run_one_* 目录，产出
       baseline_summary.csv（24 列，与 patrol_runs.csv 完全分离）
       和 baseline_report.md（统计报告），stdout 只打印 3 行摘要。
  2) python3 summarize_baseline.py --judge <log_dir> --rc <exit_code>
       对单个 run 目录做轻量 valid 判定，固定输出 8 个 '|' 分隔字段，
       供 run_batch_experiments.sh 用 cut 按列取用（M3）。
  3) python3 summarize_baseline.py --all --no-md
       只刷新 CSV，不写 md。

设计约束（来自任务卡）：
  - 不修改 run CSV（patrol_runs.csv / truth_last_pose.csv 只读）
  - 不删除任何 invalid 轮原始数据
  - 统计只报 valid 轮，invalid 轮单列
  - 不引入第三方依赖（仅标准库）
"""

import argparse          # 命令行参数解析
import csv               # CSV 读写（标准库，无第三方依赖）
import itertools         # combinations：跳变落点两两配对（3.3 节）
import math              # hypot / degrees / atan2 / dist
import re                # 从日志文本提取 run_id / 位姿 / 目标点
import statistics        # fmean / median / stdev
from pathlib import Path # 路径操作

WS = Path('/home/robot/ros2_ws')                 # 工作空间根目录（硬编码，脚本随仓库走）
LOG_ROOT = WS / 'experiment_logs'                # 实验日志根目录
PATROL_CSV = LOG_ROOT / 'patrol_runs.csv'        # 主表 12 列，本脚本只读
TRUTH_CSV = LOG_ROOT / 'truth_last_pose.csv'     # 旁路真值表 7 列，本脚本只读
SUMMARY_CSV = LOG_ROOT / 'baseline_summary.csv'  # 汇总输出，本脚本唯一写入的 CSV
REPORT_MD = LOG_ROOT / 'baseline_report.md'      # 统计报告输出（Markdown，位于 gitignore 目录内）

JUMP_DEV_M = 1.0        # 规则a 偏差阈值：单采样 |gt-amcl| > 1.0 m 视为越阈
JUMP_DUR_S = 10.0       # 规则a 持续阈值：越阈状态连续超过 10 s 判 invalid
LAST_DEV_M = 0.5        # 规则b 末点阈值：末点 |gt-amcl| > 0.5 m 判 invalid
HIST_CUTOFF = '2026-11-06'   # 早于该日期的 run_id 视为历史轮，note 追加 hist（D-a 口径）

# 汇总 CSV 的 24 个字段，顺序固定（与放行清单逐字一致，不得增删改序）
SUMMARY_FIELDS = [
    'run_id', 'run_exec_ok', 'valid', 'invalid_reason',            # 1-4 身份与判定
    'total_goals', 'succeeded', 'failed', 'timeout',               # 5-8 导航结果
    'canceled', 'rejected', 'total_time_s',                        # 9-11 导航结果
    'gt_last_x', 'gt_last_y', 'gt_last_yaw',                       # 12-14 真值末点
    'amcl_last_x', 'amcl_last_y', 'amcl_last_yaw',                 # 15-17 AMCL 末点
    'pos_err_m', 'yaw_err_deg',                                    # 18-19 末点误差
    'max_dev_m', 'max_dev_dur_s', 'lethal_space_hit',              # 20-22 轨迹与日志证据
    'trace_path', 'note',                                          # 23-24 溯源与备注
]

# truth.log 单行形如：
# [INFO] run_id=20261105_153829_r1 gt={'x': -0.007, ...} amcl={'x': 0.037, ...}
TRUTH_RE = re.compile(
    r"run_id=(\S+)\s+"
    r"gt=\{'x':\s*([-\d.eE+]+|None),\s*'y':\s*([-\d.eE+]+|None),\s*'yaw':\s*([-\d.eE+]+|None)\}\s+"
    r"amcl=\{'x':\s*([-\d.eE+]+|None),\s*'y':\s*([-\d.eE+]+|None),\s*'yaw':\s*([-\d.eE+]+|None)\}"
)

# patrol.log 中每个巡逻点的下发记录形如：获取目标点0->2.0,1.0,0.0
GOAL_RE = re.compile(r'获取目标点(\d+)->([-\d.eE+]+),([-\d.eE+]+),([-\d.eE+]+)')

# fail.log 单行形如：[FAIL] step=S3 reason=topic_missing:/nonexistent_topic exit=4
FAIL_EXIT_RE = re.compile(r'exit=(\d+)')

# nav2.log 中规划器拒绝出解的标志串（规则c 的唯一证据）
LETHAL_PAT = 'Starting point in lethal space'


def wrap_pi(a):
    """把角度归一化到 [-π, π]。用于兼容历史 truth CSV 中未归一化的 yaw（如 -4.845）。"""
    return math.atan2(math.sin(a), math.cos(a))


def to_float(s):
    """把正则捕获串转 float；捕获到 'None' 或空串时返回 None，避免污染后续统计。"""
    if s is None:
        return None
    s = s.strip()
    if not s or s == 'None':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_truth_log(log_dir):
    """解析 <log_dir>/truth.log 的唯一一行，返回 dict；文件缺失或格式不符返回 None。

    返回键：run_id / gt_x / gt_y / gt_yaw / amcl_x / amcl_y / amcl_yaw
    注意：此处不做任何数值修改，yaw 归一化只在计算 yaw_err_deg 时做（不篡改原始值）。
    """
    p = log_dir / 'truth.log'
    if not p.exists():
        return None                       # 无 truth.log 的目录不算 completed run
    m = TRUTH_RE.search(p.read_text(encoding='utf-8', errors='ignore'))
    if not m:
        return None
    return {
        'run_id': m.group(1),
        'gt_x': to_float(m.group(2)), 'gt_y': to_float(m.group(3)), 'gt_yaw': to_float(m.group(4)),
        'amcl_x': to_float(m.group(5)), 'amcl_y': to_float(m.group(6)), 'amcl_yaw': to_float(m.group(7)),
    }


def parse_trace(log_dir):
    """读取 <log_dir>/pose_trace.csv，返回 [(t, gt_x, gt_y, gt_yaw, amcl_x, amcl_y, amcl_yaw), ...]。

    文件缺失（历史 run1/run2）时返回空列表，调用方据此走 no_trace 分支，不报错。
    单行解析失败直接跳过，不让一条脏数据拖垮整轮。
    """
    p = log_dir / 'pose_trace.csv'
    out = []
    if not p.exists():
        return out
    with p.open('r', encoding='utf-8', errors='ignore', newline='') as f:
        for row in csv.DictReader(f):
            try:
                out.append((
                    float(row['t_sec']),
                    to_float(row['gt_x']), to_float(row['gt_y']), to_float(row['gt_yaw']),
                    to_float(row['amcl_x']), to_float(row['amcl_y']), to_float(row['amcl_yaw']),
                ))
            except (KeyError, ValueError, TypeError):
                continue                  # 跳过表头错位/空值行
    return out


def trace_dev(trace):
    """计算轨迹偏差三量：最大偏差 / 最长“连续>1m”区段时长 / 跳变落点。

    返回 (max_dev, max_dur, jump)
      max_dev  : 全轮最大 |gt-amcl|，单位 m；无有效采样时为 None
      max_dur  : 越阈状态的最长持续时长，单位 s；从未越阈时为 0.0
      jump     : (t_sec, amcl_x, amcl_y, gt_x, gt_y) 跳变落点；无跳变时为 None

    跳变落点定义（P2-A 修正）：取相邻采样间 AMCL 单步位移最大的那个采样点，
    且该单步位移须 > JUMP_DEV_M(1m) 才认定为跳变，否则返回 None。
    不采用首个越阈点：220630 实测 t=238 已越阈 1.19m 属漂移起点，
    t=340 才是 9.66m 单步真跳变，用首越阈点会让落点聚集分析被漂移污染。
    max_dev / max_dur 计算口径未变，规则a 判定不受本修正影响。
    """
    devs = []
    for t, gx, gy, _gyaw, ax, ay, _ayaw in trace:
        if gx is None or ax is None:
            continue                  # 缺真值或缺 AMCL 的采样不参与偏差计算
        devs.append((t, math.hypot(ax - gx, ay - gy), ax, ay, gx, gy))
    if not devs:
        return None, None, None

    max_dev = max(d for _, d, *_ in devs)      # 全轮最大偏差
    best_dur = 0.0                             # 最长越阈区段时长
    cur_start = None                           # 当前越阈区段的起点时刻；None 表示未在越阈
    for t, d, *_rest in devs:
        if d > JUMP_DEV_M:                     # 进入越阈状态
            if cur_start is None:
                cur_start = t                   # 记录区段起点
            best_dur = max(best_dur, t - cur_start)   # 区段跨度实时更新
        else:
            cur_start = None                   # 回落到阈值内，区段结束

    jump = None                                # 跳变落点（单步位移最大的那个采样点）
    max_step = 0.0                             # 相邻采样间 AMCL 单步位移的最大值
    for i in range(1, len(devs)):
        _t0, _d0, ax0, ay0, _gx0, _gy0 = devs[i - 1]   # 前一采样
        t1, _d1, ax1, ay1, gx1, gy1 = devs[i]          # 当前采样
        step = math.hypot(ax1 - ax0, ay1 - ay0)        # 单步位移只算 AMCL，不看真值
        if step > max_step:
            max_step = step
            jump = (t1, ax1, ay1, gx1, gy1)            # 以跳变后的落点为跳变落点
    if max_step <= JUMP_DEV_M:
        jump = None                            # 单步位移不足 1m，视为无跳变（仅漂移）

    return max_dev, best_dur, jump


def lethal_hit(log_dir):
    """规则c：在 nav2.log 中查找 'Starting point in lethal space'。命中返回 1，否则 0。"""
    p = log_dir / 'nav2.log'
    if not p.exists():
        return 0
    return 1 if LETHAL_PAT in p.read_text(encoding='utf-8', errors='ignore') else 0


def fail_exit(log_dir):
    """从 <log_dir>/fail.log 解析 run_one_experiment.sh 的退出码；无 fail.log 时返回 0。

    --all 模式没有原始 exit code，只能用 fail.log 反推；--judge 模式以真实 rc 为准。
    """
    p = log_dir / 'fail.log'
    if not p.exists():
        return 0
    m = FAIL_EXIT_RE.search(p.read_text(encoding='utf-8', errors='ignore'))
    return int(m.group(1)) if m else 1      # 有 fail.log 但解析不出码时按非 0 处理


def parse_goals(log_dir):
    """解析 <log_dir>/patrol.log 中的巡逻点列表，返回 [(idx, x, y, yaw), ...]（去重保序）。

    用途：跳变落点“最近巡逻点”分析，坐标来自该轮实际下发记录，不硬编码巡逻点。
    """
    p = log_dir / 'patrol.log'
    seen = {}
    if not p.exists():
        return []
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        m = GOAL_RE.search(line)
        if not m:
            continue
        idx = int(m.group(1))
        if idx in seen:
            continue                  # 同一轮重复下发同一目标点时只保留首次
        seen[idx] = (idx, float(m.group(2)), float(m.group(3)), float(m.group(4)))
    return [seen[k] for k in sorted(seen)]


def nearest_wp(goals, x, y):
    """在巡逻点列表中找距 (x, y) 最近的一个，返回 (idx, x, y, yaw, dist)；无输入返回 None。"""
    if not goals or x is None or y is None:
        return None
    best = min(goals, key=lambda w: math.hypot(w[1] - x, w[2] - y))
    return (best[0], best[1], best[2], best[3], math.hypot(best[1] - x, best[2] - y))


def goals_all_done(run_id, patrol_idx):
    """判断该轮是否「全部巡逻目标都已成功到达」。

    D3 修正的依据来源：规则c 不再「lethal 出现即 invalid」，而是「出现 lethal 且该轮未跑完所有目标」。
    实证两例（20261106_145721_r1、20261107_164529_r1）：lethal 仅出现 1 次、规划目标是 home(0,0)，
    失败后清 global_costmap 即恢复并 10/10 全部到达，末点误差 0.08m / 0.13m，定位本身正常。
    这类轮次若被规则c 否决，会把「导航成功、定位可信」的样本误判为无效，压低 valid 率。

    返回 True=全部完成；False=未完成；None=无法判断（patrol_runs.csv 无该 run_id 或字段不可解析）。
    无法判断时由调用方按「未完成」处理，即保持保守口径，不让规则c 因缺数据而放行。
    """
    if not patrol_idx or not run_id:
        return None
    prow = patrol_idx.get(run_id)
    if not prow:
        return None
    tg = (prow.get('total_goals') or '').strip()
    sc = (prow.get('succeeded') or '').strip()
    if not tg.isdigit() or not sc.isdigit():
        return None
    return int(tg) > 0 and int(sc) >= int(tg)


def evaluate(log_dir, rc, patrol_idx=None):
    """单轮判定核心：四条 invalid 规则只在本函数实现一份（bash 侧不重复实现）。

    规则（满足任一即 invalid）：
      a. 任一 pose_trace 采样 |gt-amcl| > 1 m 且持续 > 10 s
      b. 末点 |gt-amcl| > 0.5 m
      c. 日志出现 'Starting point in lethal space' 且该轮未跑完所有目标（D3 修正）
      d. run_one_experiment.sh 退出码非 0
      e. 无 truth.log（末点偏差不可算，规则b 记不可判，同时保证该轮以 invalid 计入）
    返回 dict，字段供 judge() 与 build_row() 复用。
    """
    reasons = []

    if rc != 0:                                   # 规则d：单 run 脚本非正常退出
        reasons.append('exit_%d' % rc)

    # 先解析真值：规则c 需要 truth.log 里的 run_id 才能反查 patrol_runs 判定是否跑完所有目标
    truth = parse_truth_log(log_dir)              # 末点数据同样来自 truth.log

    hit = lethal_hit(log_dir)                     # 规则c：规划器报起点在致命格（先记录原始命中）
    all_done = goals_all_done(truth['run_id'] if truth else None, patrol_idx)
    if hit and all_done is not True:
        # D3 修正：只有「出现 lethal 且该轮未跑完所有目标」才判 invalid；
        # all_done 为 True 时 lethal 仅作观察（见返回值 lethal_nonfatal），不否决该轮；
        # all_done 为 None（patrol_runs 无记录）时按未完成处理，保持保守口径。
        reasons.append('lethal_space')

    trace = parse_trace(log_dir)                  # 历史轮无 trace 时为空列表
    max_dev, max_dur, jump = trace_dev(trace)
    if max_dur is not None and max_dur > JUMP_DUR_S:   # 规则a：越阈持续 > 10 s
        reasons.append('jump_gt_1m')

    pos_err = None
    yaw_err_deg = None
    if truth and truth['gt_x'] is not None and truth['amcl_x'] is not None:
        pos_err = math.hypot(truth['amcl_x'] - truth['gt_x'], truth['amcl_y'] - truth['gt_y'])
        if pos_err > LAST_DEV_M:                  # 规则b：末点偏差 > 0.5 m
            reasons.append('last_dev_gt_0.5m')
        if truth['gt_yaw'] is not None and truth['amcl_yaw'] is not None:
            # 先归一化两侧 yaw 再作差，兼容历史 CSV 中超出 [-π,π] 的原始值
            yaw_err_deg = math.degrees(wrap_pi(truth['amcl_yaw'] - truth['gt_yaw']))

    if not truth:
        reasons.append('no_truth')                # 无 truth.log：末点偏差不可算，规则b 记不可判而非静默跳过

    return {
        'truth': truth, 'trace': trace,
        'max_dev': max_dev, 'max_dur': max_dur, 'jump': jump,
        'lethal': hit, 'pos_err': pos_err, 'yaw_err_deg': yaw_err_deg,
        # lethal_nonfatal：日志确有 lethal，但该轮 10/10 跑完，仅作观察写入 note，不影响 valid
        'lethal_nonfatal': bool(hit and all_done is True),
        'valid': 1 if not reasons else 0,
        'reasons': reasons,
        'has_trace': bool(trace),
    }


def judge(log_dir, rc):
    """--judge 模式：固定输出 8 个 '|' 分隔字段（M3），空值一律用 '-' 占位。

    列序：valid|run_id|log_dir|exit_code|invalid_reason|pos_err_m|max_dev_m|jump
      valid          1 / 0
      run_id         该轮 run_id；无 truth.log 时用 <目录时间戳>_na 占位
      log_dir        目录名（非全路径，避免 bash 侧切分歧义）
      exit_code      run_one_experiment.sh 退出码原值
      invalid_reason 逗号连接的规则名；valid 时为 -
      pos_err_m      末点位置差；不可算时为 -
      max_dev_m      全轮最大偏差；无 trace 时为 -
      jump           形如 '339.0@(-3.817,2.860)'；无跳变时为 -
    """
    # 传入 patrol_runs 索引：规则c 需要用它判断该轮是否跑完所有目标（D3 修正）
    r = evaluate(log_dir, rc, load_patrol_index())
    # 无 truth.log 时用目录时间戳 + _na 占位，避免 batch_ledger 的 run_id 记成 '-' 无法回填
    run_id = r['truth']['run_id'] if r['truth'] else (log_dir.name.replace('run_one_', '') + '_na')
    reasons = ','.join(r['reasons']) if r['reasons'] else '-'
    pos_err = '%.3f' % r['pos_err'] if r['pos_err'] is not None else '-'
    max_dev = '%.3f' % r['max_dev'] if r['max_dev'] is not None else '-'
    jump = '-'
    if r['jump'] is not None:
        t, ax, ay, _gx, _gy = r['jump']
        jump = '%.1f@(%.3f,%.3f)' % (t, ax, ay)
    print('|'.join([str(r['valid']), run_id, log_dir.name, str(rc), reasons, pos_err, max_dev, jump]))


def load_patrol_index():
    """把 patrol_runs.csv 载入 dict，键为 run_id，值为 12 列原始字符串。

    run_id 列可能因历史脏数据带空格，统一 strip；重复 run_id 保留最后一次。
    """
    idx = {}
    if not PATROL_CSV.exists():
        return idx
    with PATROL_CSV.open('r', encoding='utf-8', errors='ignore', newline='') as f:
        for row in csv.DictReader(f):
            rid = (row.get('run_id') or '').strip()
            if rid:
                idx[rid] = row
    return idx


def build_row(log_dir, patrol_idx):
    """把一个 run 目录组装成 baseline_summary.csv 的一行（24 字段 dict）。

    数据来源分层：
      - 导航结果  <- patrol_runs.csv（只读）
      - 末点位姿  <- truth.log（权威，与 truth_last_pose.csv 同源）
      - 轨迹证据  <- pose_trace.csv（缺失则留空并标 no_trace）
      - 判定      <- evaluate() 的四条规则
    """
    rc = fail_exit(log_dir)                       # --all 模式由 fail.log 反推退出码
    r = evaluate(log_dir, rc, patrol_idx)         # 传入索引供规则c 判断是否跑完所有目标
    truth = r['truth']
    if not truth and not r['has_trace']:
        # 既无 truth.log 又无 pose_trace：该轮连轨迹都没产出（如开跑即崩），
        # 不产出行，只在 batch_ledger.csv 留痕。
        return None

    if truth:
        run_id = truth['run_id']                  # truth.log 是 run_id 的权威来源
    else:
        # 无 truth.log（典型为 S5 巡逻超时被外层杀掉，未执行 S6 真值采集）：
        # 用目录时间戳 + _na 后缀构造可排序的占位 id，明确标注不是 patrol_runs 权威 id。
        run_id = log_dir.name.replace('run_one_', '') + '_na'
    prow = patrol_idx.get(run_id, {})

    note = []
    if not r['has_trace']:
        note.append('no_trace')                   # 历史轮缺 trace：规则a 不可算，仅规则b 生效
    if not truth:
        note.append('no_truth')                   # 无 truth.log：末点偏差不可算，规则b 不可判
    if r.get('lethal_nonfatal'):
        # 出现过 lethal 但该轮全部目标都到达：按 D3 修正不否决，仅留痕便于回溯
        note.append('lethal_nonfatal')
    if run_id[:8] < HIST_CUTOFF.replace('-', ''):
        note.append('hist')                       # 放行 D-a：历史轮计入 N=10，需可溯源标注

    trace_path = '-'
    if r['has_trace']:
        trace_path = str((log_dir / 'pose_trace.csv').relative_to(WS))

    t = truth or {}                               # 无 truth.log 时用空 dict，保证末点列留空不报错

    def fmt(v, spec='%.4f'):
        """把可能为 None 的数值格式化；None 输出空串，保持 CSV 空列而非填 0。"""
        return '' if v is None else spec % v

    return {
        'run_id': run_id,
        'run_exec_ok': 0 if rc != 0 else 1,
        'valid': r['valid'],
        'invalid_reason': ';'.join(r['reasons']) if r['reasons'] else '',
        'total_goals': prow.get('total_goals', ''),
        'succeeded': prow.get('succeeded', ''),
        'failed': prow.get('failed', ''),
        'timeout': prow.get('timeout', ''),
        'canceled': prow.get('canceled', ''),
        'rejected': prow.get('rejected', ''),
        'total_time_s': prow.get('total_time_s', ''),
        'gt_last_x': fmt(t.get('gt_x')), 'gt_last_y': fmt(t.get('gt_y')),
        'gt_last_yaw': fmt(t.get('gt_yaw')),
        'amcl_last_x': fmt(t.get('amcl_x')), 'amcl_last_y': fmt(t.get('amcl_y')),
        'amcl_last_yaw': fmt(t.get('amcl_yaw')),
        'pos_err_m': fmt(r['pos_err']),
        'yaw_err_deg': fmt(r['yaw_err_deg'], '%.2f'),
        'max_dev_m': fmt(r['max_dev']),
        'max_dev_dur_s': fmt(r['max_dur'], '%.1f'),
        'lethal_space_hit': r['lethal'],
        'trace_path': trace_path,
        'note': ','.join(note),
    }


def count_trace_lines(row):
    """统计该行对应 pose_trace.csv 的数据行数（不含表头），供 D8 重复行取舍使用。

    无轨迹行（trace_path 为 '-'）返回 0；文件读不到也返回 0，不抛出异常，
    保证去重逻辑不会因为某个坏文件而中断整轮汇总。
    """
    p = row.get('trace_path') or ''
    if p in ('', '-'):
        return 0
    try:
        with open(WS / p, encoding='utf-8') as f:
            return max(0, sum(1 for _ in f) - 1)   # 去掉表头
    except OSError:
        return 0


def is_dup(row):
    """该行是否为并发重复行（note 含 dup_of=）。重复行只留痕，不参与任何统计。"""
    return 'dup_of=' in (row.get('note') or '')


def dedup_by_run_id(rows):
    """D8 修正：同一 run_id 出现多行时只保留一条计入统计，其余标 dup_of 仅留痕。

    背景（批 1c 事故）：批脚本被重复执行，两套 run_one 并发，而 capture_truth_pose.py
    的 run_id 取自 patrol_runs.csv 末行，并发时多个采集进程读到同一行，于是同一个 run_id
    写出了多份 truth.log / pose_trace.csv，导致 completed 被虚增、amcl 末点被交叉污染。

    取舍规则：保留 pose_trace.csv 采样行数最多的一条（采样最完整），并列时保留排序靠前者
    （rows 已按 run_id 排序，目录名次之）。其余行 note 追加 dup_of=<保留行所在目录名>，
    原始行仍写入 baseline_summary.csv、原始目录与数据一律保留，只从统计口径中剔除。
    """
    best = {}                                      # run_id -> (采样行数, 行)
    for r in rows:
        rid = r['run_id']
        n = count_trace_lines(r)
        cur = best.get(rid)
        if cur is None or n > cur[0]:
            best[rid] = (n, r)
    keep_dir = {}                                  # run_id -> 保留行的目录名，供 dup_of 标注
    for rid, (_n, r) in best.items():
        p = r.get('trace_path') or ''
        keep_dir[rid] = Path(p).parent.name if p not in ('', '-') else '-'
    for r in rows:
        p = r.get('trace_path') or ''
        dirname = Path(p).parent.name if p not in ('', '-') else '-'
        if dirname != keep_dir[r['run_id']]:
            tag = 'dup_of=' + keep_dir[r['run_id']]
            r['note'] = (r['note'] + ',' if r['note'] else '') + tag
    return rows


def scan_all():
    """扫描 LOG_ROOT 下全部 run_one_* 目录，返回按 run_id 排序的行列表。

    D8：排序后先按 run_id 去重标注（dup_of），再由调用方按 is_dup() 剔除统计。
    """
    patrol_idx = load_patrol_index()
    rows = []
    for d in sorted(LOG_ROOT.glob('run_one_*')):
        if not d.is_dir():
            continue
        row = build_row(d, patrol_idx)
        if row is not None:                       # 既无真值又无轨迹的目录（未产出数据）跳过
            rows.append(row)
    rows.sort(key=lambda x: x['run_id'])
    return dedup_by_run_id(rows)                  # D8：标注并发重复行（dup_of），统计侧再剔除


def write_summary(rows):
    """写 baseline_summary.csv（全量覆盖，24 列固定顺序）。返回写入行数。"""
    with SUMMARY_CSV.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return len(rows)


def stats(vals):
    """对数值列表求 n / mean / median / std / min / max；空列表返回 None。

    n=1 时 stdev 无定义，按 0.0 处理（单样本离散度为 0，而非报错中断）。
    """
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {
        'n': len(vals),
        'mean': statistics.fmean(vals),
        'median': statistics.median(vals),
        'std': statistics.stdev(vals) if len(vals) > 1 else 0.0,
        'min': min(vals),
        'max': max(vals),
    }


def fmt_stats(name, s, unit=''):
    """把一组统计量渲染成一行 Markdown 表格行；无数据时整行标注 n=0。"""
    if not s:
        return '| %s | 0 | - | - | - | - | - |' % name
    return '| %s | %d | %.3f%s | %.3f%s | %.3f%s | %.3f%s | %.3f%s |' % (
        name, s['n'],
        s['mean'], unit, s['median'], unit, s['std'], unit, s['min'], unit, s['max'], unit)


def build_report(rows):
    """生成统计报告 Markdown 文本。

    口径（M5，两栏分流，互不混淆）：
      栏一「定位可信度」= valid 轮数 / 已完成轮数
      栏二「导航成功率」= sum(succeeded) / sum(total_goals)，且只统计 valid 轮
    invalid 轮只进分布统计，绝不混入均值/中位数。
    D8：并发重复行（note 含 dup_of）整行剔除，不参与任何计数与统计，只在 CSV 中留痕。
    """
    dup = [r for r in rows if is_dup(r)]          # D8：并发重复行，只留痕不统计
    rows = [r for r in rows if not is_dup(r)]     # 后续所有统计只用去重后的行
    valid = [r for r in rows if str(r['valid']) == '1']
    invalid = [r for r in rows if str(r['valid']) != '1']

    lines = []
    lines.append('# T-P1-02B 基线统计报告')
    lines.append('')
    lines.append('> 自动生成，勿手改。数据源：`experiment_logs/run_one_*/`')
    lines.append('> N=10 指 **valid 轮数**达到 10，不是总轮数。')
    lines.append('')

    lines.append('## 一、总览（两栏分流）')
    lines.append('')
    lines.append('| 指标 | 值 | 口径 |')
    lines.append('|:---|:---:|:---|')
    lines.append('| 已完成轮数 completed_runs | %d | 有真值或轨迹的目录数（无真值轮标 no_truth） |' % len(rows))
    # D8：并发事故产生的同 run_id 重复行，只列数量以保持可追溯，不参与任何分母
    lines.append('| 并发重复行（已剔除） | %d | 同 run_id 多份采样，note 标 dup_of，仅留痕 |' % len(dup))
    # D7-B：采样额度只算「有 truth.log 的轮」，无真值的超时轮不占 MAX_RUNS，与 run_batch_experiments.sh 口径一致
    lines.append('| 采样额度已用（预算口径） | %d | 有 truth.log 的轮数，用于 MAX_RUNS 熔断 |' % len(
        [r for r in rows if 'no_truth' not in (r['note'] or '')]))
    lines.append('| 有效轮数 valid_runs | %d | 四条 invalid 规则全不命中的轮数 |' % len(valid))
    lines.append('| **定位可信率** | %s | valid_runs / completed_runs |' % (
        ('%.1f%%' % (100.0 * len(valid) / len(rows))) if rows else '-'))
    tot_goals = sum(int(r['total_goals']) for r in valid if str(r['total_goals']).isdigit())
    tot_succ = sum(int(r['succeeded']) for r in valid if str(r['succeeded']).isdigit())
    lines.append('| **导航成功率（仅 valid 轮）** | %s | %d / %d |' % (
        ('%.1f%%' % (100.0 * tot_succ / tot_goals)) if tot_goals else '-', tot_succ, tot_goals))
    lines.append('')

    lines.append('## 二、valid 轮统计（只含 valid，invalid 不参与）')
    lines.append('')
    lines.append('| 指标 | n | mean | median | std | min | max |')
    lines.append('|:---|:---:|:---:|:---:|:---:|:---:|:---:|')
    time_vals = [float(r['total_time_s']) for r in valid if r['total_time_s'] not in ('', None)]
    pos_vals = [float(r['pos_err_m']) for r in valid if r['pos_err_m'] not in ('', None)]
    yaw_vals = [float(r['yaw_err_deg']) for r in valid if r['yaw_err_deg'] not in ('', None)]
    lines.append(fmt_stats('total_time', stats(time_vals), 's'))
    lines.append(fmt_stats('pos_err', stats(pos_vals), 'm'))
    lines.append(fmt_stats('|yaw_err|', stats([abs(v) for v in yaw_vals]), 'deg'))
    lines.append('')

    # 2.1（2026-11-07 评审要求）：valid 轮 max_dev 全表。
    # 目的：规则a 只看「连续 >1m 且持续 >10s」，瞬时偏差不参与判定；
    # 把每轮 max_dev 摊开，便于观察 valid 轮的瞬时偏差离 1m 阈值还有多远。
    lines.append('### 2.1 valid 轮 max_dev 全表（规则a 阈值 1.0m，仅参考不参与判定）')
    lines.append('')
    lines.append('| run_id | max_dev m | 越阈持续 s | 末点误差 m | 判定 |')
    lines.append('|:---|:---:|:---:|:---:|:---:|')
    for r in sorted(valid, key=lambda x: -float(x['max_dev_m'] or 0)):
        lines.append('| %s | %s | %s | %s | valid |' % (
            r['run_id'], r['max_dev_m'] or '-', r['max_dev_dur_s'] or '-', r['pos_err_m'] or '-'))
    if valid:
        md_max = max(float(r['max_dev_m']) for r in valid if r['max_dev_m'] not in ('', None))
        lines.append('')
        lines.append('- 全表最大 max_dev = %.3f m（阈值 1.0m，余量 %.3f m）；越阈持续列全为 0 或空 ⇒ 无轮命中规则a' % (
            md_max, JUMP_DEV_M - md_max))
    lines.append('')

    lines.append('## 三、invalid 轮分布（单列，不参与上面的统计）')
    lines.append('')
    lines.append('| run_id | 原因 | 末点误差 m | 最大偏差 m | 越阈持续 s | 跳变落点 | 最近巡逻点 | 距离 m |')
    lines.append('|:---|:---|:---:|:---:|:---:|:---|:---:|:---:|')
    reason_dist = {}
    jump_wps = []
    for r in invalid:
        reasons = r['invalid_reason'] or '-'
        for one in reasons.split(';'):
            if one:
                reason_dist[one] = reason_dist.get(one, 0) + 1
        # 重新从目录计算跳变落点与最近巡逻点（CSV 只存聚合量，落点明细在报告里展开）
        log_dir = None
        rid = r['run_id']
        if rid.endswith('_na'):
            # 占位 id = 目录时间戳 + _na，可直接还原目录名（无 truth.log 无法按 run_id 反查）
            cand = LOG_ROOT / ('run_one_' + rid[:-3])
            if cand.is_dir():
                log_dir = cand
        if log_dir is None:
            for cand in LOG_ROOT.glob('run_one_*'):
                t = parse_truth_log(cand)
                if t and t['run_id'] == rid:
                    log_dir = cand
                    break
        jump_txt, wp_txt, dist_txt = '-', '-', '-'
        if log_dir:
            _md, _dur, jump = trace_dev(parse_trace(log_dir))
            if jump:
                t0, ax, ay, _gx, _gy = jump
                jump_txt = '%.1fs@(%.3f,%.3f)' % (t0, ax, ay)
                wp = nearest_wp(parse_goals(log_dir), ax, ay)
                if wp:
                    wp_txt = 'wp%d(%.1f,%.1f)' % (wp[0], wp[1], wp[2])
                    dist_txt = '%.2f' % wp[4]
                    # 保留落点坐标与恢复量，供 3.3 节做「同落点不同恢复」配对
                    jump_wps.append((r['run_id'], wp[0], wp[4], ax, ay,
                                     r['max_dev_dur_s'] or '', r['pos_err_m'] or ''))
        lines.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
            r['run_id'], reasons, r['pos_err_m'] or '-', r['max_dev_m'] or '-',
            r['max_dev_dur_s'] or '-', jump_txt, wp_txt, dist_txt))
    lines.append('')

    lines.append('### 3.1 原因分布')
    lines.append('')
    if reason_dist:
        for k in sorted(reason_dist, key=lambda x: -reason_dist[x]):
            lines.append('- `%s` × %d' % (k, reason_dist[k]))
    else:
        lines.append('- 无 invalid 轮')
    lines.append('')

    lines.append('### 3.2 跳变落点聚集分析')
    lines.append('')
    if jump_wps:
        for rid, widx, dist, _ax, _ay, _dur, _pe in jump_wps:
            lines.append('- `%s` 跳变落点最近巡逻点 = wp%d，距离 %.2f m' % (rid, widx, dist))
        agg = {}
        for _rid, widx, _d, _ax, _ay, _dur, _pe in jump_wps:
            agg[widx] = agg.get(widx, 0) + 1
        top = sorted(agg.items(), key=lambda x: -x[1])
        lines.append('- 聚集：%s（仅观察，不构成结论；样本数 n=%d）' % (
            '、'.join('wp%d×%d' % (k, v) for k, v in top), len(jump_wps)))
    else:
        lines.append('- 无可用跳变落点（历史轮缺 pose_trace 或无单步>1m 跳变）')
    lines.append('')

    # 3.3（2026-11-07 评审要求）：同一落点、不同恢复行为，只记一行，n=2 不下结论。
    # 判据：两次跳变落点世界坐标相距 ≤0.2m 视为「同一落点」，仅陈述各自越阈持续与末点误差。
    lines.append('### 3.3 同落点不同恢复行为（仅记录，n<3 不下结论）')
    lines.append('')
    pairs = []
    for a, b in itertools.combinations(jump_wps, 2):
        if a[3] is None or b[3] is None:
            continue
        gap = math.dist((a[3], a[4]), (b[3], b[4]))
        if gap <= 0.2:
            pairs.append((a, b, gap))
    if pairs:
        for a, b, gap in pairs:
            lines.append('- `%s` 与 `%s` 跳变落点相距 %.2f m（同一落点）；越阈持续 %ss / %ss，'
                         '末点误差 %sm / %sm ⇒ 恢复行为不同（样本 n=2，不下结论）' % (
                             a[0], b[0], gap,
                             a[5] or '-', b[5] or '-', a[6] or '-', b[6] or '-'))
    else:
        lines.append('- 暂无落点相距 ≤0.2 m 的跳变对')
    lines.append('')

    lines.append('## 四、字段口径说明')
    lines.append('')
    lines.append('- `pos_err_m` = 末点 |gt-amcl|；`yaw_err_deg` = 归一化后 (amcl_yaw - gt_yaw) 的度数')
    lines.append('- `max_dev_dur_s` = 轨迹中最长“连续 |gt-amcl|>1m”区段跨度，非累计时长')
    lines.append('- `跳变落点` = 相邻采样间 AMCL 单步位移最大且 >1m 的那个采样点，不是首次越阈点')
    lines.append('- `note=no_trace` 表示该轮无 pose_trace.csv，规则a 不可算，判定退化为规则b')
    lines.append('- `note=no_truth` 表示该轮无 truth.log（典型为 S5 超时未进 S6），末点四列为空，规则b 不可判')
    lines.append('- `note=lethal_nonfatal` 表示日志出现过 lethal，但该轮全部目标都到达，按 D3 修正不判 invalid')
    lines.append('- 规则c 口径（D3 修正）：`lethal 出现 且 该轮未跑完所有目标` 才判 invalid，否则只留痕')
    lines.append('- `note=dup_of=<目录>` 表示该行与另一行同 run_id，属并发重复采样（批 1c 事故产物），已从统计剔除')
    lines.append('- `note=hist` 表示该轮早于 %s，属历史轮（放行 D-a 计入 N=10）' % HIST_CUTOFF)
    lines.append('')

    # 五、六（2026-11-07 评审要求）：口径说明 + 假设清单，均随报告自动生成。
    lines.append('## 五、基线口径说明')
    lines.append('')
    lines.append('- **N=10 指 valid 轮数达到 10**，不是总轮数。完成标志以 `baseline_summary.csv` 的 valid 计数为准。')
    lines.append('- **invalid 轮是「发现」，不是「副产品」**：每条 invalid 都对应一条可复核的规则命中（原因列 + 落点明细），'
                 '不因未达 N=10 而丢弃，也不参与均值/中位数。')
    lines.append('- **采样额度**只计有 `truth.log` 的轮（D7-B），`no_truth` 轮不占 `MAX_RUNS` 槽位；'
                 '当前额度 = truth 计数，见第一节。')
    lines.append('- **并发重复行**（`note=dup_of`）只留痕不统计（D8），剔除数量见第一节。')
    lines.append('- **导航成功率只统计 valid 轮**：invalid 轮的到点情况受定位错误污染，不计入成功率分母。')
    lines.append('')

    lines.append('## 六、假设清单（待验证，不是结论）')
    lines.append('')
    lines.append('| 编号 | 假设 | 来源 | 状态 |')
    lines.append('|:---|:---|:---|:---:|')
    lines.append('| H1 | 跳变点相对真值近似点对称，指向地图对称性/激光特征退化引发的**全局重定位错解** | BUGLOG 2026-11-05 | 待验证 |')
    lines.append('| H2 | **AMCL 存在伪吸引子**；EKF 融合 IMU 航向先验能否抑制这种误收敛 | 2026-11-07 评审（M3 假设清单新增） | 待验证 |')
    lines.append('| H3 | 跳变落点聚集于 wp3 附近与巡逻点几何/环境特征相关 | 本报告 3.2（仅观察） | 待验证 |')
    lines.append('')
    lines.append('> H2 的验证前提：需先接入 `robot_localization`（当前 IMU 未进 EKF 链路，见 HANDOFF 2.3），'
                 '属研究内容 3 范围，不在 P1 基线内展开。')
    lines.append('')
    return '\n'.join(lines) + '\n'


def resolve_judge_dir(arg):
    """把 --judge 入参解析成真实存在的目录（P1 修正，避免相对路径被二次拼接）。

    按优先级依次尝试三种写法：
      1. 原样：绝对路径直接用；相对路径按当前工作目录解析
      2. 相对工作空间根：WS / arg
      3. 只给目录名：LOG_ROOT / 目录名
    返回第一个真实存在的目录；三者都不存在时返回原样 Path，由调用方输出 no_dir。
    """
    d = Path(arg)
    candidates = [d]                          # 绝对路径或相对 cwd
    if not d.is_absolute():
        candidates.append(WS / d)             # 相对工作空间根
        candidates.append(LOG_ROOT / d.name)  # 只给目录名
    for cand in candidates:
        if cand.is_dir():
            return cand                       # 命中即返回，不再尝试后续写法
    return d                                  # 全不存在，交由调用方输出 no_dir


def main():
    """入口：解析参数并按模式分派。"""
    ap = argparse.ArgumentParser(description='T-P1-02B 基线汇总')
    ap.add_argument('--all', action='store_true', help='全量扫描并刷新 baseline_summary.csv')
    ap.add_argument('--judge', metavar='LOG_DIR', help='只判定单个 run 目录，输出 8 个 | 字段')
    ap.add_argument('--rc', type=int, default=0, help='配合 --judge，传入 run_one 退出码')
    ap.add_argument('--no-md', action='store_true', help='配合 --all，不生成 baseline_report.md')
    args = ap.parse_args()

    if args.judge:
        d = resolve_judge_dir(args.judge)   # P1 修正：相对路径按 cwd / 工作空间根 / 目录名依次解析
        if not d.is_dir():
            print('-|-|%s|%d|no_dir|-|-|-' % (d.name, args.rc))   # M2：目录不存在也固定 8 列
            return
        judge(d, args.rc)
        return

    if args.all:
        rows = scan_all()
        n = write_summary(rows)                   # 全部行都写盘（含 dup_of 行，保证可追溯）
        # D8：统计口径只用去重后的行，避免并发重复行把 completed / valid 虚增
        kept = [r for r in rows if not is_dup(r)]
        valid = [r for r in kept if str(r['valid']) == '1']
        invalid = [r for r in kept if str(r['valid']) != '1']
        # P3（2026-11-07 评审放行）：原打印 completed= 与批脚本 [PRE] completed_runs= 同词两义
        # （前者=全部非 dup 目录行含 no_truth，后者=有 truth.log 的轮），同屏易被误读。
        # 改为四个互不重名的计数：dirs / truth / valid / invalid，另单列 dup_excluded。
        truth = [r for r in kept if 'no_truth' not in (r['note'] or '')]
        print('[SUMMARY] dirs=%d truth=%d valid=%d invalid=%d dup_excluded=%d -> %s' % (
            len(kept), len(truth), len(valid), len(invalid), n - len(kept), SUMMARY_CSV.name))
        tv = [float(r['total_time_s']) for r in valid if r['total_time_s'] not in ('', None)]
        pe = [float(r['pos_err_m']) for r in valid if r['pos_err_m'] not in ('', None)]
        ye = [abs(float(r['yaw_err_deg'])) for r in valid if r['yaw_err_deg'] not in ('', None)]
        st = stats(tv); sp = stats(pe); sy = stats(ye)
        print('[SUMMARY] valid: time=%s pos_err=%s yaw_err=%s' % (
            ('%.1fs' % st['mean']) if st else '-',
            ('%.3fm' % sp['mean']) if sp else '-',
            ('%.2fdeg' % sy['mean']) if sy else '-'))
        rd = {}
        for r in invalid:
            for one in (r['invalid_reason'] or '').split(';'):
                if one:
                    rd[one] = rd.get(one, 0) + 1
        print('[SUMMARY] invalid: %s' % (
            '、'.join('%s×%d' % (k, rd[k]) for k in sorted(rd, key=lambda x: -rd[x])) or '-'))
        if not args.no_md:
            REPORT_MD.write_text(build_report(rows), encoding='utf-8')
        return

    ap.print_help()


if __name__ == '__main__':
    main()