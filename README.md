# ros2_ws

## 是什么

ROS2 Humble + Nav2 + Gazebo Classic 的室内巡逻仿真。

个人项目，**未经从零安装验证**，仓库用于阅读/复盘。

## 主线包与职责

| 分类           | 目录                         | 一句话                                       | 入口                                                  |
|:------------ |:-------------------------- |:----------------------------------------- |:--------------------------------------------------- |
| 主线           | `pkg03_gazebo_20260814`    | Gazebo 世界 + URDF + Nav2 参数 + 启动脚本，整套仿真的入口 | `scripts/gazebo.sh`                                 |
| 主线           | `autopartol_robot`         | 巡逻节点：航点循环、拍照、语音、CSV 记录                    | `ros2 launch autopartol_robot autopartol.launch.py` |
| 主线           | `autopartol_interfaces`    | 拍照/语音两个自定义 srv                            | `srv/*.srv`                                         |
| 主线           | `robot_speech`             | 语音播报节点                                    | `speech_node`                                       |
| 主线           | `robot_vision`             | 图像抓取/拍照节点                                 | `image_capture_node`                                |
| 旁路           | `motion_control_system`    | Nav2 控制器插件示例（原地旋转）                        | `spin_motion_controller.cpp`                        |
| 旁路           | `odom_to_tf_pkg`           | 把 `/odom` 转成 TF 的旁路节点                     | `odom_to_tf`                                        |
| 旁路           | `ros2_node_monitor`        | 节点生命周期监控 GUI                              | `node_monitor`                                      |
| 练习           | `graduation_ws`            | 仅有学习笔记（day1~day9、语音链路），无 package.xml      | `notes/`                                            |
| 学习备份（**待定**） | `pkg01_backup_20260808_py` | Python 基础示例备份（话题/TF/导航）                   | —                                                   |
| 学习备份（**待定**） | `pkg02_backup_20260811`    | C++ 基础示例备份（节点/服务/Action）                  | —                                                   |
| 第三方          | `rplidar_ros`              | Slamtec 雷达驱动，BSD                          | `launch/`                                           |
| 第三方          | `wpr_simulation2`          | 6-robot 仿真包，GPLv3                         | `launch/`                                           |

## 怎么启动

```bash
# 假设工作空间在 ~/ros2_ws
bash ~/ros2_ws/src/pkg03_gazebo_20260814/scripts/gazebo.sh            # 起 Gazebo+Nav2+RViz
bash ~/ros2_ws/src/pkg03_gazebo_20260814/scripts/gazebo.sh --no-rviz  # 只想跑数据
ros2 launch autopartol_robot autopartol.launch.py                     # 开始巡逻
```

两个已知细节：

- `gazebo.sh` 里 `headless:=true` 是未声明参数、会被忽略。
- `autopartol.launch.py` 的图片目录写死 `/home/robot/ros2_ws/patrol_images/`，路径不同要自己改。

## 依赖

依赖以各 `package.xml` 为准（Nav2、gazebo_ros_pkgs、slam_toolbox 等），未提供 rosdep 验证过的安装步骤。

## 文档索引

| 文件 | 内容 |
|---|---|
| [HANDOFF.md](HANDOFF.md) | 现状 |
| [BUGLOG.md](BUGLOG.md) | 踩坑 |
| [docs/](docs/) | 实验记录 |

## 许可

第三方包：

| 包 | 许可 | LICENSE |
|---|---|---|
| `rplidar_ros` | BSD | [src/rplidar_ros/LICENSE](src/rplidar_ros/LICENSE) |
| `wpr_simulation2` | GPLv3 | 该包未附带 LICENSE 文件，许可仅声明于 [package.xml](src/wpr_simulation2/package.xml) |