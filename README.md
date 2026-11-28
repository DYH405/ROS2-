# patrol-sim

室内巡检小车：Gazebo 里跑 Nav2 + AMCL 的差速底盘，按 10 个航点自主巡逻、到点拍照，每轮结束自动收摊并给出与真值的误差。

<!-- 数据来源：experiment_logs/patrol_runs.csv、experiment_logs/truth_last_pose.csv、docs/experiments/UNATTENDED_CLOSURE_20261128.md 7.5（2026-11-28 10:29~10:42 三次实跑）。标注「待验证」的条目尚无实测数据支撑。 -->

定位是「实验台」而不是「成品系统」，理由是仓库的价值在可复算的前后差异：参数改动是否成立，只能看 `patrol_runs.csv` 的逐轮实测行和 `docs/experiments/` 的单变量对照归档；只看代码无法判断某个阈值是否有效，也无法排除「跑通一次」的偶然性。

个人项目，**未经从零安装验证**，仓库用于阅读/复盘。

## 它能做什么

1. 按 `patrol_config.yaml` 的 `target_point` 逐点导航，一轮 10 个点；到达后调用拍照服务并写入记录。
2. 连续跑三次都不需要人工干预：跑满配置轮数（`max_rounds`）即停，收摊后下一轮可以直接起。
3. 每轮产出可复核的数字：末点定位误差、航向误差、仿真耗时、墙钟耗时、图片数、RTF，以及是否干净退出（exit code）。
4. 失败处理：单点导航失败重试 `nav_retry_count` 次（当前 2），仍失败按 `nav_fail_action: skip` 跳过该点，不阻塞整轮。
5. 仿真真值来自 Gazebo 的 `/gazebo/model_states`，不依赖 AMCL 自报位置。

<!-- 待补：一张总览图（Gazebo 场景 / RViz 中的地图+轨迹截图） -->

## 实测结果

2026-11-28 10:29–10:42，同一配置连跑 3 次，未改任何文件与参数，RViz 保持开启：

| `run_id`             |  航点 |  图片 | `pos_err_m` | `yaw_err_deg` | `total_time_s` | 墙钟 s |  RTF  | 收摊                 | exit |
| :------------------- | :---: | :---: | :---------: | :-----------: | :------------: | :----: | :---: | :------------------- | :--: |
| `20261128_102949_r1` | 10/10 | 10/10 |    0.0375   |      4.47     |      207.6     |  211   | 0.984 | clean（TERM 快路径） |   0  |
| `20261128_103411_r1` | 10/10 | 10/10 |    0.0149   |      1.89     |      206.0     |  208   | 0.990 | clean（KILL 慢路径） |   0  |
| `20261128_103842_r1` | 10/10 | 10/10 |    0.0171   |      0.06     |      197.1     |  199   | 0.990 | clean（KILL 慢路径） |   0  |

三次极差：`pos_err` 0.0226 m、`yaw_err` 4.41°、`total_time_s` 10.5 s、墙钟 12 s。

**口径**

1. `pos_err_m` = 末点 `hypot(amcl_x - gt_x, amcl_y - gt_y)`；真值取 `/gazebo/model_states`，AMCL 取 `/amcl_pose`，两列原始坐标落在 `experiment_logs/truth_last_pose.csv`，误差由 `scripts/summarize_baseline.py` 计算。
2. `yaw_err_deg` = `degrees(wrap_pi(amcl_yaw - gt_yaw))`，先归一化到 ±180° 再换算，避免 ±π 跳变被记成 360° 级误差。
3. `total_time_s` 是仿真钟（`use_sim_time=true`）；与墙钟的差额即仿真滞后，RTF 已单列。
4. 这 3 次是**同一时段**的重复性复测，只证明「当前配置在同一天内可重复」；跨时段比较不能用这组小极差，需用合并样本的保守阈值，见 [UNATTENDED_CLOSURE_20261128.md](docs/experiments/UNATTENDED_CLOSURE_20261128.md) 7.5。
5. 样本量 n=3，不足以支撑「任意环境都稳定」的说法。

## 快速开始

两条路径**互斥**，不要混用。

### 路径 A：无人值守跑一轮（推荐）

```bash
cd ~/ros2_ws
colcon build
source install/setup.bash
bash scripts/run_one_experiment.sh
```

`run_one_experiment.sh` 自己依次拉起 Gazebo → Nav2 → RViz → patrol，跑完自动收摊，并打印 `run_id`。

**为什么不能先 `gazebo.sh` 再跑它**：该脚本会自行启动 Gazebo（见脚本内 `launching gazebo` 段），其前置检查若发现 `/scan` 或 `/amcl_pose` 已有发布者，会判定为残留并以 `S2 stale_ros_graph` 直接退出非零码 —— 不是 bug，是防两套仿真并发的保护。

常用变体：

```bash
PATROL_TIMEOUT=1800 bash scripts/run_one_experiment.sh   # 放宽单轮超时（默认 900 s）
ROUNDS=3 bash scripts/run_one_experiment.sh              # 一个进程内连跑 3 轮
RECOVER=1 bash scripts/run_one_experiment.sh             # 检测到残留时自动清理再跑
bash scripts/run_one_experiment.sh --clean-only          # 只清理残留，不启动任何节点
```

### 路径 B：手动观察（要在 RViz 里看过程）

```bash
bash src/patrol_simulation/scripts/gazebo.sh            # 起 Gazebo+Nav2+RViz，前台，Ctrl+C 收
bash src/patrol_simulation/scripts/gazebo.sh --no-rviz  # 只想跑数据

# 另开终端
ros2 launch patrol_mission patrol.launch.py                    # 开始巡逻，用 yaml 里的 max_rounds
ros2 launch patrol_mission patrol.launch.py max_rounds:=3      # 显式覆盖轮数
```

### 结果落在哪

| 路径 | 内容 |
|:---|:---|
| `experiment_logs/patrol_runs.csv` | 每轮一行：`total_goals`/`succeeded`/`failed`/`timeout`/`total_time_s`/`note` |
| `experiment_logs/truth_last_pose.csv` | 每轮末点真值与 AMCL 位姿（`gt_x`/`gt_y`/`gt_yaw`/`amcl_x`/`amcl_y`/`amcl_yaw`） |
| `patrol_images/` | 每个航点一张 PNG |
| `experiment_logs/run_one_<时间戳>/` | 本轮 `gazebo.log`/`nav2.log`/`patrol.log`/`rviz.log`/`pose_trace.csv` |

## 系统结构

| 包 | 职责 | 入口 |
|:---|:---|:---|
| `patrol_simulation` | Gazebo 世界 + URDF + Nav2 参数 + 启动脚本，整套仿真的入口 | `scripts/gazebo.sh` |
| `patrol_mission` | 巡逻节点：航点循环、拍照、语音、CSV 记录 | `ros2 launch patrol_mission patrol.launch.py` |
| `patrol_interfaces` | 拍照/语音两个自定义 srv（`CaptureImage`、`SpeechText`） | `srv/*.srv` |
| `patrol_speech` | 语音播报节点，`espeakng` 合成，服务名 `speech_text` | `speech_node` |
| `patrol_vision` | 订阅 `/camera/image_raw`，服务 `capture_image` 落盘 | `image_capture_node` |

旁路与其余包（`patrol_odom_tf`、`motion_control_system`、`ros2_node_monitor`、`graduation_ws`、`pkg01_backup_20260808_py`、`pkg02_backup_20260811`、第三方 `rplidar_ros`/`wpr_simulation2`）见 [src/README.md](src/README.md)。

**数据流**（文字版，替代拓扑图）：

1. `patrol_node` → `/navigate_to_pose`(action) → Nav2 `bt_navigator` → `planner_server` / `controller_server`。
2. `/scan` + `/odom` + `/imu` → AMCL → `map→odom` TF。
3. `patrol_node` → `capture_image`(srv) → `image_capture_node` → `/camera/image_raw` → `patrol_images/`。
4. `patrol_node` → `speech_text`(srv) → `speech_node` → 扬声器。
5. Gazebo `/gazebo/model_states` → `scripts/capture_truth_pose.py` → `truth_last_pose.csv`（真值，不参与导航）。

**地图与航点**（`src/patrol_simulation/maps/my_map.yaml`）：

| 项 | 值 |
|:---|:---|
| 图像 | `my_map.pgm`，202×161，P5 灰度 |
| `resolution` | 0.05 m/px |
| `origin` | `[-5.03, -3.99, 0]`（左下角） |
| 覆盖范围 | x −5.03 → 5.07 m，y −3.99 → 4.06 m |
| 航点数 | 10（`patrol_config.yaml` 的 `target_point`，每点 3 值 x/y/yaw） |
| 起点 | `initial_point: [0.0, 0.0, 0.0]` |

## 工程方法

1. **真值对照**：用 Gazebo 的 `/gazebo/model_states` 作为位置真值，与 `/amcl_pose` 逐点比对，避免「用定位评价定位」。
2. **固定协议**：每轮跑满配置航点数；跑前不改参数，跑后只记录，不在同一轮里换变量。
3. **无效轮判定**：单步跳变 > 1 m、末点误差 > 0.5 m、出现 lethal 且未跑完全部目标等，判 invalid，不混进均值。
4. **收摊验证**：进程组、话题发布者、共享内存三项都要清；清完才允许下一轮启动。
5. **图片对齐**：跑前取一次文件快照、跑后取一次，用差集算本轮新图数；因此 10 个航点对应 10 张，历史图片不干扰计数。
6. **时间口径**：耗时同时记仿真钟与墙钟，跨运行比较先换算 RTF。

## 已知限制

1. **仿真 IMU 没有噪声**：`src/patrol_simulation/urdf/parts/sensors/imu.urdf.xacro` 内无 `<noise>` 块、无协方差设置。因此「融合前后对比」只能说明运动模型约束的作用，不能当作真实 IMU 的降噪效果。
2. **EKF 未进主链路**：`ekf.yaml` / `ekf_test.launch.py` / `gazebo_ekf.sh` 已存在，但主启动走 `gazebo_test.launch.py`，未启用 EKF。
3. **样本量小**：目前可引用的重复性数据是 n=3（同日同时段），不能外推到其他时段或环境。
4. **收摊快慢路径不稳定**：同一配置下出现过 TERM 快路径与 KILL 慢路径（相差约 10 s），不影响正确性，但会放大耗时波动。
5. **未在实物平台验证**：<!-- 待补：实车迁移进度与差异数据 -->
6. **Nav2 容器偶发启动失败**：曾出现只加载 3 个组件即停摆、patrol 卡在等 `amcl/get_state`，重启即恢复；未定位到根因，记录见 [BUGLOG.md](BUGLOG.md) 2026-11-28 条。

## 依赖

依赖以各 `package.xml` 为准（Nav2、`gazebo_ros_pkgs`、`slam_toolbox` 等），未提供 rosdep 验证过的安装步骤。

ROS 之外的额外依赖：`patrol_speech` 直接 `import espeakng`（Python 包，不在 ROS 依赖体系内，包名与安装方式请自行确认）。

两个已知细节：

1. `gazebo.sh` 里 `headless:=true` 是未声明参数、会被忽略。
2. `patrol.launch.py` 的图片目录写死 `/home/robot/ros2_ws/patrol_images/`，路径不同要自己改。

仓库名 `patrol-sim` 与本地工作空间目录名 `~/ros2_ws` 不一致，是有意保留的：脚本、launch、`.bashrc` 中共有 33 处硬编码 `/home/robot/ros2_ws`，改目录名会让这些绝对路径全部失效；而 ament 解析包只按 `package.xml` 里的包名查索引，与所在目录名无关，改目录名不会带来任何收益。克隆到新机器时目录可任意命名，但需同步替换这 33 处路径。

## 文档索引

| 文件 | 内容 |
|---|---|
| [HANDOFF.md](HANDOFF.md) | 现状 |
| [BUGLOG.md](BUGLOG.md) | 踩坑与负结果 |
| [docs/](docs/) | 实验记录 |
| [docs/experiments/UNATTENDED_CLOSURE_20261128.md](docs/experiments/UNATTENDED_CLOSURE_20261128.md) | 无人值守闭环加固归档与噪声底判据 |

## 许可

自研部分：Apache License 2.0，全文见 [LICENSE](LICENSE)，第三方组件声明见 [NOTICE](NOTICE)。
各包 `package.xml` 另有 `<license>` 声明的，以包内声明为准。

第三方包：

| 包 | 许可 | LICENSE |
|---|---|---|
| `rplidar_ros` | BSD | [src/rplidar_ros/LICENSE](src/rplidar_ros/LICENSE) |
| `wpr_simulation2` | GPLv3 | 该包未附带 LICENSE 文件，许可仅声明于 [package.xml](src/wpr_simulation2/package.xml) |