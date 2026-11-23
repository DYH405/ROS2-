#!/usr/bin/env python3
"""原地转向探针：验证 wheel_separation 是否配错。

做法：发布固定角速度的 /cmd_vel 持续固定时长，同时采样
  - /odom 的 yaw（编码器积分航向）
  - /gazebo/model_states 的 yaw（真值）
结束时打印两者比值。

判据（wheel_separation 与真实轮距一致时，比值应约为 1.0）：
  odom_yaw / gt_yaw ≈ 0.36/0.24 = 1.5  ⇒ sep 配小了，/odom 航向被放大
  odom_yaw / gt_yaw ≈ 1.0              ⇒ 配置正确
另外看 gt_yaw 是否接近 cmd_yaw：物理转向速率 = 指令 * sep_cfg/sep_real。

用法（需先启动 Gazebo）：
  python3 scripts/odom_spin_probe.py                # 默认 0.5 rad/s 转 2 秒
  python3 scripts/odom_spin_probe.py 0.5 2.0        # 角速度 时长
注意：运行前应保证车处于静止、且位于空旷处，避免撞墙改变真值。
"""
import math
import sys
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from gazebo_msgs.msg import ModelStates

MODEL_NAME = 'basic_diff_drive_robot'


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def norm(a):
    return math.atan2(math.sin(a), math.cos(a))


class Probe(Node):
    def __init__(self):
        super().__init__('odom_spin_probe')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.create_subscription(ModelStates, '/gazebo/model_states', self.on_states, 10)
        self.odom_yaw = None
        self.gt_yaw = None

    def on_odom(self, msg):
        self.odom_yaw = yaw_of(msg.pose.pose.orientation)

    def on_states(self, msg):
        if MODEL_NAME in msg.name:
            self.gt_yaw = yaw_of(msg.pose[msg.name.index(MODEL_NAME)].orientation)

    def spin_for(self, wz, sec):
        t0 = time.time()
        while time.time() - t0 < sec:
            tw = Twist()
            tw.angular.z = wz
            self.pub.publish(tw)
            rclpy.spin_once(self, timeout_sec=0.02)
        self.pub.publish(Twist())
        t1 = time.time()
        while time.time() - t1 < 1.0:
            rclpy.spin_once(self, timeout_sec=0.02)


def main():
    wz = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    sec = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

    rclpy.init()
    node = Probe()
    t = time.time()
    while time.time() - t < 3.0 and (node.odom_yaw is None or node.gt_yaw is None):
        rclpy.spin_once(node, timeout_sec=0.05)
    o0, g0 = node.odom_yaw, node.gt_yaw
    if o0 is None or g0 is None:
        print('未收到 /odom 或 /gazebo/model_states，确认 Gazebo 已启动')
        node.destroy_node()
        rclpy.shutdown()
        return

    node.spin_for(wz, sec)
    o1, g1 = node.odom_yaw, node.gt_yaw
    d_odom = abs(norm(o1 - o0))
    d_gt = abs(norm(g1 - g0))
    d_cmd = abs(wz) * sec

    print('指令角速度 %.2f rad/s，时长 %.2f s ⇒ 指令转角 %.1f deg' % (wz, sec, math.degrees(d_cmd)))
    print('真值转角 %.1f deg   等效速率 %.2f rad/s' % (math.degrees(d_gt), d_gt / sec))
    print('odom 转角 %.1f deg   等效速率 %.2f rad/s' % (math.degrees(d_odom), d_odom / sec))
    if d_gt > 1e-3:
        print('odom / 真值 = %.3f   （1.5 说明 sep 配小；1.0 说明正确）' % (d_odom / d_gt))
        print('真值 / 指令 = %.3f   （0.667 说明物理转向被 sep 拖慢；1.0 说明正确）'
              % (d_gt / d_cmd if d_cmd > 1e-3 else float('nan')))
    else:
        print('真值几乎未转动，检查车是否被卡住或 /cmd_vel 未被接收')

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()