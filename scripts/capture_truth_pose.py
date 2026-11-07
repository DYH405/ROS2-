#!/usr/bin/env python3
import argparse
import csv
import json
import math
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from gazebo_msgs.msg import ModelStates
from geometry_msgs.msg import PoseWithCovarianceStamped

ROBOT_NAME = 'basic_diff_drive_robot'
MODEL_TOPICS = ('/gazebo/model_states', '/model_states')
HEADER = ['run_id', 'gt_x', 'gt_y', 'gt_yaw', 'amcl_x', 'amcl_y', 'amcl_yaw']


def yaw_from_quat(q): # 平面运动，四元数转yaw
    yaw = 2.0 * math.atan2(q.z, q.w) # 四元数双覆盖(q与-q等价)，结果可能落在(-2π,2π]
    return math.atan2(math.sin(yaw), math.cos(yaw)) # 归一化到[-π,π]，使与AMCL可直接比较


def append_row(csv_path, row): # 追加一行，末行缺换行则先补，避免粘连
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    has_content = path.exists() and path.stat().st_size > 0
    need_nl = False
    if has_content:
        with open(path, 'rb') as fb:
            fb.seek(-1, 2)
            need_nl = fb.read(1) != b'\n'
    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if need_nl:
            f.write('\r\n')
        if not has_content:
            writer.writerow(HEADER)
        writer.writerow([row.get(key, '') for key in HEADER])


def last_run_id(csv_path): # 取主表最后一个可解析run_id，保证同轮对齐
    path = Path(csv_path)
    if not path.exists():
        return ''
    with open(path, 'r', encoding='utf-8', newline='') as f:
        rows = [r for r in csv.reader(f) if r and r[0] != 'run_id']
    return rows[-1][0] if rows else ''


class PoseWatcher(Node):
    def __init__(self, json_path, robot_name, period):
        super().__init__('capture_truth_pose_watch')
        self.json_path = Path(json_path)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.robot_name = robot_name
        self.cache = {'gt': None, 'amcl': None}
        self.trace_path = self.json_path.with_name('pose_trace.csv') # 采样轨迹旁路文件，供偏差曲线分析
        self.t0 = time.time() # 采样起点，作为曲线横轴
        for topic in MODEL_TOPICS: # 两种命名都订阅，哪条先到用哪条
            self.create_subscription(ModelStates, topic, self.on_model_states, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.on_amcl, 10)
        self.create_timer(period, self.dump)

    def on_model_states(self, msg): # 真值来自Gazebo世界系
        if self.robot_name not in msg.name:
            return
        idx = msg.name.index(self.robot_name)
        pose = msg.pose[idx]
        self.cache['gt'] = {
            'x': round(pose.position.x, 3),
            'y': round(pose.position.y, 3),
            'yaw': round(yaw_from_quat(pose.orientation), 3),
        }

    def on_amcl(self, msg): # AMCL末点，map系
        pose = msg.pose.pose
        self.cache['amcl'] = {
            'x': round(pose.position.x, 3),
            'y': round(pose.position.y, 3),
            'yaw': round(yaw_from_quat(pose.orientation), 3),
        }

    def dump(self): # 原子写缓存，供finalize读取；同时追加一行轨迹
        tmp = self.json_path.with_name(self.json_path.name + '.tmp')
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False), encoding='utf-8')
        tmp.replace(self.json_path)
        self.trace() # 每次采样落一行，形成随时间变化的偏差曲线

    def trace(self): # 追加一行gt/amcl采样，末行缺换行先补，避免粘连
        path = self.trace_path
        has_content = path.exists() and path.stat().st_size > 0
        need_nl = False
        if has_content:
            with open(path, 'rb') as fb:
                fb.seek(-1, 2)
                need_nl = fb.read(1) != b'\n'
        gt = self.cache.get('gt') or {}
        amcl = self.cache.get('amcl') or {}
        with open(path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if need_nl:
                f.write('\r\n')
            if not has_content:
                writer.writerow(['t_sec', 'gt_x', 'gt_y', 'gt_yaw',
                                 'amcl_x', 'amcl_y', 'amcl_yaw'])
            writer.writerow([round(time.time() - self.t0, 1),
                             gt.get('x', ''), gt.get('y', ''), gt.get('yaw', ''),
                             amcl.get('x', ''), amcl.get('y', ''), amcl.get('yaw', '')])


def run_watch(args):
    rclpy.init()
    watcher = PoseWatcher(args.json, args.robot, args.period)
    try:
        rclpy.spin(watcher)
    except KeyboardInterrupt:
        pass
    finally:
        watcher.dump()
        watcher.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


def run_finalize(args):
    cache = {'gt': None, 'amcl': None}
    cache_path = Path(args.json)
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding='utf-8'))
        except Exception as exc:
            print(f'[WARN] 缓存解析失败：{exc}')

    rclpy.init() # 现场再取一次真值，避免缓存滞后
    node = Node('capture_truth_pose_finalize')
    box = {}
    for topic in MODEL_TOPICS: # 两种命名都订阅
        node.create_subscription(
            ModelStates, topic, lambda m: box.setdefault('m', m), 10)
    deadline = time.time() + args.timeout
    while time.time() < deadline and 'm' not in box:
        rclpy.spin_once(node, timeout_sec=0.1)
    if 'm' in box:
        states = box['m']
        if ROBOT_NAME in states.name:
            idx = states.name.index(ROBOT_NAME)
            pose = states.pose[idx]
            cache['gt'] = {
                'x': round(pose.position.x, 3),
                'y': round(pose.position.y, 3),
                'yaw': round(yaw_from_quat(pose.orientation), 3),
            }
    node.destroy_node()
    rclpy.shutdown()

    run_id = last_run_id(args.patrol_csv)
    gt = cache.get('gt')
    amcl = cache.get('amcl')
    row = {'run_id': run_id}
    if gt:
        row.update({'gt_x': gt['x'], 'gt_y': gt['y'], 'gt_yaw': gt['yaw']})
    if amcl:
        row.update({'amcl_x': amcl['x'], 'amcl_y': amcl['y'], 'amcl_yaw': amcl['yaw']})
    append_row(args.csv, row)

    missing = []
    if not gt:
        missing.append('gt_missing')
    if not amcl:
        missing.append('amcl_missing')
    print(f'[INFO] run_id={run_id} gt={gt} amcl={amcl}')
    if missing:
        print(f'[FAIL] {" ".join(missing)}')
        return 7
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--finalize', action='store_true')
    parser.add_argument('--json', default='~/ros2_ws/experiment_logs/pose_cache.json')
    parser.add_argument('--csv', default='~/ros2_ws/experiment_logs/truth_last_pose.csv')
    parser.add_argument('--patrol-csv', default='~/ros2_ws/experiment_logs/patrol_runs.csv')
    parser.add_argument('--robot', default=ROBOT_NAME)
    parser.add_argument('--period', type=float, default=1.0)
    parser.add_argument('--timeout', type=float, default=15.0)
    args = parser.parse_args()
    args.json = str(Path(args.json).expanduser())
    args.csv = str(Path(args.csv).expanduser())
    args.patrol_csv = str(Path(args.patrol_csv).expanduser())
    if args.finalize:
        return run_finalize(args)
    return run_watch(args)


if __name__ == '__main__':
    raise SystemExit(main())