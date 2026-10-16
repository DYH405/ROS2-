#!/usr/bin/env python3

import argparse # 导入argparse模块，用于解析命令行参数-可以理解linux命令行
import sys
from pathlib import Path
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message # serialization 序列化
from rosidl_runtime_py.utilities import get_message # 获取消息类型
import matplotlib.pyplot as plt # MATLAB风格绘制(plot)库(lib)，python绘制，简化名称plt

def parse_args():
    # 创建参数解释器对象
    parser = argparse.ArgumentParser(description="ROS2 Bag 数据分析工具")
    parser.add_argument('bag_path', type=str, help='Bag文件目录路径')
    return parser.parse_args()

def open_bag(bag_path):
    storage_options =StorageOptions(# 存储配置
        uri=str(bag_path),
        storage_id="sqlite3"
    )
    converter_options = ConverterOptions()# 格式转换参数包
    reader = SequentialReader()# sequential 顺序，顺序读取器
    reader.open(storage_options, converter_options)

    topic_types = reader.get_all_topics_and_types()
    print(f'[INFO] 话题数量：{len(topic_types)}')
    for tt in topic_types:
        print(f'  - {tt.name} ({tt.type})')

    return reader

def read_odom_messages(reader):
    t0 = None # 第一个时间戳
    odom_data = []
    msg_type = get_message('nav_msgs/msg/Odometry')

    while reader.has_next():# 当还有下一个数据
        topic, data, timestamp = reader.read_next()
        if topic == '/odom':
            msg = deserialize_message(data, msg_type)
            x = msg.pose.pose.position.x
            y = msg.pose.pose.position.y
            if t0 is None:
                t0 = timestamp / 1e9 # 第一个时间戳
            t = timestamp / 1e9 - t0 # 相对时间-便于画图
            odom_data.append((t, x, y)) # append 添加到列表末尾

    print(f'[INFO] 读取到{len(odom_data)}条/odom数据')
    return odom_data

def plot_trajectory(odom_data, bag_path):
    times = [t for t, x, y in odom_data] # 列表推导式，提取t单独成一个列表
    xs = [x for t, x, y in odom_data] # 列表推导式，提取x单独成一个列表
    ys = [y for t, x, y in odom_data] # 列表推导式，提取y单独成一个列表

    plt.figure(figsize=(10, 8)) # 10英寸宽，8英寸高
    plt.plot(xs, ys ,'b-', linewidth=1, label='Trajectory')# 'b-' 蓝色实线，线宽1，标签：轨迹
    plt.plot(xs[0], ys[0], 'go',markersize=10, label='Start')# 'go':绿色圆点，标记大小10，标签：起点
    plt.plot(xs[-1], ys[-1], 'ro',markersize=10, label='End')# 'ro':红色圆点，标记大小10，标签：终点

    plt.title('Robot Trajectory') # 标题
    plt.xlabel('X(m)') # X轴标签
    plt.ylabel('Y(m)') # Y轴标签
    plt.legend() # legend: 图例
    plt.grid(True) # grid: 网格线
    plt.axis('equal') # axis: 等比例缩放,X轴与Y轴比例相同，避免拉伸

    output_path = bag_path / 'trajectory.png' # 输出路径
    plt.savefig(output_path, dpi=150) # dpi: 分辨率，150 dpi 为 150 像素/英寸
    plt.close() # 关闭图窗，释放内存
    print(f'[INFO] 轨迹图已保存: {output_path}')


def main():
    args = parse_args()
    bag_path = Path(args.bag_path)

    if not bag_path.exists():
        print(f'[ERROR] Bag路径不存在: {bag_path}')
        # exit：退出程序，返回非0表示错误
        sys.exit(1)

    print(f'[INFO] 分析Bag: {bag_path}') # 分析Bag
    reader = open_bag(bag_path) # 打开Bag
    odom_data = read_odom_messages(reader) # 读取/odom数据
    plot_trajectory(odom_data, bag_path) # 画轨迹图

    for t, x, y in odom_data[:5]:
        print(f' t={t:.2f}, x={x:.3f}, y={y:.3f}') # 2f 保留2位小数，3f 保留3位小数
if __name__ == '__main__':
    main()
