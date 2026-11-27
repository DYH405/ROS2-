# src/

| 分类           | 目录                         | 一句话                                       | 入口                                                  |
|:------------ |:-------------------------- |:----------------------------------------- |:--------------------------------------------------- |
| 主线           | `pkg03_gazebo_20260814`    | Gazebo 世界 + URDF + Nav2 参数 + 启动脚本，整套仿真的入口 | `scripts/gazebo.sh`                                 |
| 主线           | `autopartol_robot`         | 巡逻节点：航点列表逐点 `goToPose`、拍照、语音、CSV 记录                    | `ros2 launch autopartol_robot autopartol.launch.py` |
| 主线           | `autopartol_interfaces`    | 拍照/语音两个自定义 srv                            | `srv/*.srv`                                         |
| 主线           | `robot_speech`             | 语音播报节点                                    | `speech_node`                                       |
| 主线           | `robot_vision`             | 图像抓取/拍照节点                                 | `image_capture_node`                                |
| 旁路           | `motion_control_system`    | pluginlib 运动控制插件示例（原地旋转），基类为自定义 `MotionController`，非 `nav2_core::Controller` | `spin_motion_controller.cpp`                        |
| 旁路           | `odom_to_tf_pkg`           | 把 `/odom` 转成 TF 的旁路节点                     | `odom_to_tf`                                        |
| 旁路           | `ros2_node_monitor`        | 节点生命周期监控 GUI                              | `node_monitor`                                      |
| 练习           | `graduation_ws`            | 仅有学习笔记（day1~day9、语音链路），无 package.xml      | `notes/`                                            |
| 学习备份（**待定**） | `pkg01_backup_20260808_py` | Python 基础示例备份（话题/TF/导航）                   | —                                                   |
| 学习备份（**待定**） | `pkg02_backup_20260811`    | C++ 基础示例备份（节点/服务/Action）                  | —                                                   |
| 第三方          | `rplidar_ros`              | Slamtec 雷达驱动，BSD                          | `launch/`                                           |
| 第三方          | `wpr_simulation2`          | 6-robot 仿真包，GPLv3                         | `launch/`                                           |

非包目录：`bag_analyzer`（脚本/数据），不参与构建。

主线 5 个：`pkg03_gazebo_20260814` / `autopartol_robot` / `autopartol_interfaces` / `robot_speech` / `robot_vision`。

`pkg01_backup_20260808_py`、`pkg02_backup_20260811` 是学习备份，位置待定，不要当主线读。