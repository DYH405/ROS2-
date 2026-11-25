#!/usr/bin/env python3
# 用法: python3 scripts/amcl_compare.py <目录名1> <目录名2> ...
#   目录名指 experiment_logs/amcl_test/ 下的子目录，按给定顺序并排输出。
#   输出两种口径：全样本口径（含 update_min_d/a 阶梯滞后）与
#   更新时刻口径（只在 /amcl_pose 数值变化时统计，用于跨组比较）。
import csv
import math
import statistics as st
import sys
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                    'experiment_logs', 'amcl_test')


def yaw_err(a, b):
    d = math.degrees(a - b)
    return (d + 180) % 360 - 180


def load(path):
    rows = []
    with open(path, encoding='utf-8') as fp:
        for r in csv.DictReader(fp):
            try:
                rows.append(tuple(float(r[k]) for k in (
                    't_sec', 'gt_x', 'gt_y', 'gt_yaw', 'amcl_x', 'amcl_y', 'amcl_yaw')))
            except (KeyError, ValueError):
                pass
    return rows


def metrics(path):
    rows = load(path)
    if not rows:
        return None
    upd = [r for i, r in enumerate(rows)
           if i == 0 or (r[4], r[5], r[6]) != (rows[i - 1][4], rows[i - 1][5], rows[i - 1][6])]
    e = [math.hypot(r[4] - r[1], r[5] - r[2]) for r in upd]
    y = [abs(yaw_err(r[6], r[3])) for r in upd]
    ea = [math.hypot(r[4] - r[1], r[5] - r[2]) for r in rows]

    def q(v, f):
        return sorted(v)[min(len(v) - 1, int(len(v) * f))]

    f = rows[-1]
    return dict(n=len(rows), upd=len(upd), dur=f[0] - rows[0][0],
                emean=st.mean(e), e50=q(e, .5), e90=q(e, .9), emax=max(e),
                ymean=st.mean(y), y90=q(y, .9), ymax=max(y),
                aemean=st.mean(ea), aemax=max(ea),
                fin_p=math.hypot(f[4] - f[1], f[5] - f[2]),
                fin_y=yaw_err(f[6], f[3]), rows=rows)


def main():
    names = sys.argv[1:]
    if not names:
        names = sorted(d for d in os.listdir(ROOT)
                       if os.path.isdir(os.path.join(ROOT, d)) and not d.startswith('.'))
    hdr = ('%-34s %4s %3s %5s | %6s %6s %6s %6s | %5s %5s %5s | %6s %6s'
           % ('run', 'rows', 'upd', 'dur', 'e_mean', 'e_50%', 'e_90%', 'e_max',
              'y_mean', 'y_90%', 'y_max', 'all_max', 'fin_p'))
    print('--- 更新时刻口径（跨组可比）---')
    print(hdr)
    for n in names:
        v = metrics(os.path.join(ROOT, n, 'pose_trace.csv'))
        if not v:
            print('%-34s (pose_trace.csv 缺失)' % n)
            continue
        print('%-34s %4d %3d %5.1f | %6.3f %6.3f %6.3f %6.3f | %5.2f %5.2f %5.2f | %6.3f %+6.2f'
              % (n, v['n'], v['upd'], v['dur'], v['emean'], v['e50'], v['e90'], v['emax'],
                 v['ymean'], v['y90'], v['ymax'], v['aemax'], v['fin_p']))
    print('\n说明: e_*/y_* 为更新时刻口径；all_max 为全样本口径最大值（含阶梯滞后，仅供对照）。')

    if len(names) >= 1:
        v = metrics(os.path.join(ROOT, names[-1], 'pose_trace.csv'))
        if v:
            print('\n=== %s 位置误差最大 5 个采样（全样本口径）===' % names[-1])
            for r in sorted(v['rows'], key=lambda r: -math.hypot(r[4] - r[1], r[5] - r[2]))[:5]:
                print(' t=%6.1f err=%.3f gt=(%.3f,%.3f) amcl=(%.3f,%.3f)'
                      % (r[0], math.hypot(r[4] - r[1], r[5] - r[2]), r[1], r[2], r[4], r[5]))
            print('\n=== %s |yaw误差| 最大 5 个采样（全样本口径）===' % names[-1])
            for r in sorted(v['rows'], key=lambda r: -abs(yaw_err(r[6], r[3])))[:5]:
                print(' t=%6.1f err=%+7.2f gt_yaw=%7.1f amcl_yaw=%7.1f'
                      % (r[0], yaw_err(r[6], r[3]), math.degrees(r[3]), math.degrees(r[6])))


if __name__ == '__main__':
    main()