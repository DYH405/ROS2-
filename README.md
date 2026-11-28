# patrol-sim

## 是什么

ROS 2 Humble + Nav2 + Gazebo Classic 的室内巡逻仿真实验台：差速底盘在 `robocup_home` 世界里按 10 个固定航点循环巡检，每个航点拍照、语音播报、写 CSV，同时采集 AMCL 位姿与 Gazebo 真值用于定位误差对照。

定位是「实验台」而不是「系统」，理由是仓库的价值在可复算的前后差异：参数改动是否成立，只能看 `experiment_logs/patrol_runs.csv` 的逐轮实测行（每行含 `succeeded`/`timeout`/`total_time_s`）和 `docs/experiments/` 的单变量对照归档；只看代码无法判断某个阈值是否有效，也无法排除「跑通一次」的偶然性。

个人项目，**未经从零安装验证**，仓库用于阅读/复盘。

## 主线包与职责

| 分类           | 目录                         | 一句话                                       | 入口                                                  |
|:------------ |:-------------------------- |:----------------------------------------- |:--------------------------------------------------- |
| 主线           | `patrol_simulation`    | Gazebo 世界 + URDF + Nav2 参数 + 启动脚本，整套仿真的入口 | `scripts/gazebo.sh`                                 |
| 主线           | `patrol_mission`         | 巡逻节点：航点循环、拍照、语音、CSV 记录                    | `ros2 launch patrol_mission patrol.launch.py` |
| 主线           | `patrol_interfaces`    | 拍照/语音两个自定义 srv                            | `srv/*.srv`                                         |
| 主线           | `patrol_speech`             | 语音播报节点                                    | `speech_node`                                       |
| 主线           | `patrol_vision`             | 图像抓取/拍照节点                                 | `image_capture_node`                                |
| 旁路           | `motion_control_system`    | pluginlib 运动控制插件示例（原地旋转），基类为自定义 `MotionController`，非 `nav2_core::Controller` | `spin_motion_controller.cpp`                        |
| 旁路           | `patrol_odom_tf`           | 把 `/odom` 转成 TF 的旁路节点                     | `odom_to_tf`                                        |
| 旁路           | `ros2_node_monitor`        | 节点生命周期监控 GUI                              | `node_monitor`                                      |
| 练习           | `graduation_ws`            | 仅有学习笔记（day1~day9、语音链路），无 package.xml      | `notes/`                                            |
| 学习备份（**待定**） | `pkg01_backup_20260808_py` | Python 基础示例备份（话题/TF/导航）                   | —                                                   |
| 学习备份（**待定**） | `pkg02_backup_20260811`    | C++ 基础示例备份（节点/服务/Action）                  | —                                                   |
| 第三方          | `rplidar_ros`              | Slamtec 雷达驱动，BSD                          | `launch/`                                           |
| 第三方          | `wpr_simulation2`          | 6-robot 仿真包，GPLv3                         | `launch/`                                           |

## 怎么启动

```bash
# 假设工作空间在 ~/ros2_ws
bash ~/ros2_ws/src/patrol_simulation/scripts/gazebo.sh            # 起 Gazebo+Nav2+RViz
bash ~/ros2_ws/src/patrol_simulation/scripts/gazebo.sh --no-rviz  # 只想跑数据
ros2 launch patrol_mission patrol.launch.py                     # 开始巡逻
```

仓库名 `patrol-sim` 与本地工作空间目录名 `~/ros2_ws` 不一致，是有意保留的：脚本、launch、`.bashrc` 中共有 33 处硬编码 `/home/robot/ros2_ws`（其中 `scripts/` 17 处、`src/` 12 处、`.bashrc` 4 处），改目录名会让这些绝对路径全部失效；而 ament 解析包只按 `package.xml` 里的包名查索引，与所在目录名无关，改目录名不会带来任何收益。克隆到新机器时目录可任意命名，但需同步替换这 33 处路径。

两个已知细节：

- `gazebo.sh` 里 `headless:=true` 是未声明参数、会被忽略。
- `patrol.launch.py` 的图片目录写死 `/home/robot/ros2_ws/patrol_images/`，路径不同要自己改。

## 依赖

依赖以各 `package.xml` 为准（Nav2、gazebo_ros_pkgs、slam_toolbox 等），未提供 rosdep 验证过的安装步骤。

## 文档索引

| 文件 | 内容 |
|---|---|
| [HANDOFF.md](HANDOFF.md) | 现状 |
| [BUGLOG.md](BUGLOG.md) | 踩坑 |
| [docs/](docs/) | 实验记录 |

## 许可

自研部分：Apache License 2.0，全文见 [LICENSE](LICENSE)，第三方组件声明见 [NOTICE](NOTICE)。
各包 `package.xml` 另有 `<license>` 声明的，以包内声明为准。

第三方包：

| 包 | 许可 | LICENSE |
|---|---|---|
| `rplidar_ros` | BSD | [src/rplidar_ros/LICENSE](src/rplidar_ros/LICENSE) |
| `wpr_simulation2` | GPLv3 | 该包未附带 LICENSE 文件，许可仅声明于 [package.xml](src/wpr_simulation2/package.xml) |