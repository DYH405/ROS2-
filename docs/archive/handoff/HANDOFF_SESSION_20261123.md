# 本次对话交接文档（一次性，仅服务 2026-11-22 ~ 11-23 这一段工作）

> 写于 2026-11-23，用途：把这一整段对话的来龙去脉、结论、数据、坑、剩余待办一次性交接出去。
> **本文档只用于交接，不承担长期维护职责**；长期结论已分别沉淀在
> [BUGLOG.md](file:///home/robot/ros2_ws/BUGLOG.md)、[HANDOFF.md](file:///home/robot/ros2_ws/HANDOFF.md)、
> [docs/AMCL_PARAM_SWEEP_ARCHIVE.md](file:///home/robot/ros2_ws/docs/AMCL_PARAM_SWEEP_ARCHIVE.md)、
> [docs/VERIFY_ODOM_SOURCE.md](file:///home/robot/ros2_ws/docs/VERIFY_ODOM_SOURCE.md)。
> 读完本文若只想记一件事：**`wheel_separation` 已从 0.24 修成 0.36，A~D 四组的 yaw 指标因此全部作废，下一步是重建基线 E 组。**

---

## 一、这段对话的起点：M3 EKF 前置验证

项目主线是 **M3 —— 用 EKF 融合 `/odom` 与 `/imu`，证明融合后定位精度优于纯轮式里程计**。要让这个论点站得住，必须先满足两个前提：

1. `/odom` **必须真的会漂**。如果仿真里的 `/odom` 就是世界真值，那"融合改善"无从谈起（拿满分去比满分）。
2. AMCL 参数必须**与仿真实际状态匹配**。否则 AMCL 误差大到盖住 EKF 的效果，或者参数本身就是错的，实验结论不成立。

这段对话做的全部工作，都是围绕这两个前提。**注意：EKF 本身一次都没有实跑过**，本段只做前置清理。

### 1.1 当时拆的三层（后续沿用这个框架）

| 层 | 内容 | 本段状态 |
|:---:|:---|:---|
| ① 功能验证 | EKF 节点活着、TF 无冲突、`/odometry/filtered` 有输出 | ❌ 未做 |
| ② 数据录制 | 一次运行同时录 A 组（纯 odom）/ B 组（EKF）/ 真值 | ❌ 未做 |
| ③ 指标分析 | 算误差、出曲线 | 🟡 分析脚本已在主机侧完成，不在本工作区 |

---

## 二、时间线：这段对话实际做了什么

### 阶段 0：确认 bag 与既有资产

- 确认工作区里有历史 bag（如 `20261026_151507`），曾复制到共享文件夹。
- 确认既有 16 个 bag 与批量实验数据**建立在"`/odom` = 真值"之上**，属乐观上界，后续新数据与之**不可直接比较**。

### 阶段 1：`/odom` 数据源性质定案（WORLD → ENCODER）

**问题**：差速插件 `libgazebo_ros_diff_drive.so` 的 `odometry_source` 有两个取值：

| 值 | 含义 | 后果 |
|:---:|:---|:---|
| `1`（WORLD，默认） | 直接读 Gazebo 世界位姿 | `/odom` = 真值，**不会漂** |
| `0`（ENCODER） | 用左右轮编码器行程积分 | 有系统性比例误差，**会漂** |

原配置是默认的 WORLD，所以"里程计很准"是假象。改为 `odometry_source: 0` 后实测（`VERIFY_ODOM_SOURCE.md` 第七节）：

| 真值行进距离 | 位置误差 |
|:---:|:---:|
| 3.07 m | 0.343 m |
| 5.10 m | 1.252 m |

误差**超线性增长**（距离 1.66 倍、误差 3.65 倍、yaw 误差 11.1 倍），当时归因为"转弯打滑"，**后来证明这个归因是错的**（见阶段 5）。

**这一步的意义**：A 组（纯 `/odom`）从此具备可对比的累积误差，EKF 对比实验有了意义。

### 阶段 2：AMCL 参数与仿真实际状态对齐

逐条比对"AMCL 假设"与"仿真实际"，修了三项（均带注释，改的是
[nav2_params_hybrid.yaml](file:///home/robot/ros2_ws/src/pkg03_gazebo_20260814/config/nav2_params_hybrid.yaml)）：

| 参数 | 原值 | 改为 | 理由 |
|:---|:---:|:---:|:---|
| `sigma_hit` | 0.2 m | **0.05 m** | 仿真雷达**零噪声**，0.2 m 的"雷达噪声"在仿真里根本不存在；0.05 正好是 1 个地图栅格（0.05 m/px），代表"端点与最近障碍的距离偏差" |
| `max_beams` | 60（Nav2 默认） | **180** | 雷达 720 线/圈 ≈ 0.5°，60 束 ≈ 6°，丢掉 12 倍角向信息；先试 120 再试 180，180 时角间隔 2.0°，3 m 处弧长 0.105 m ≈ 2 倍 `sigma_hit`，够用 |
| `laser_max_range` | 100 | **8.0** | 必须与 `lidar.urdf.xacro` 的 `<range><max>8.0</max>` 逐字一致；写成 100 会把 `z_rand` 的均匀项按量程归一化，等于把 `z_hit:z_rand = 0.5:0.5` 悄悄改成近乎纯 `z_hit` |

**三个概念必须分清**（当时反复强调过）：

- `sigma_hit` 是**端点与地图障碍的距离偏差**，不是雷达测距噪声；
- `laser_max_range` 是**无回波判定线**（超过即视为打空），不是"最大可用距离"；
- `max_beams` 是**每帧参与打分的激光束上限**，只有取"能整除 `range_count-1`"的值才不浪费。

**yaml 静默失效的坑**：顶层 key 必须与节点名逐字一致，否则参数不加载、不报错，节点用出厂默认值跑。

### 阶段 3：写一键测试脚本 `run_amcl_test.sh`

用户要求：一条命令拉起仿真 + 导航 + RViz2，后台采真值与 AMCL 轨迹，人工在 RViz 看效果，脚本自动记量化指标。

**第一版犯的错（用户当场指出）**：脚本自己写了 `BasicNavigator` 发 3 个自定义目标点，**没有启动项目原有的巡航节点**。已改为 `ros2 launch autopartol_robot autopartol.launch.py`，与批量实验**完全同一条链路**（10 个固定航点、单轮、失败重试 2 次、60 s/点超时）。

脚本现在做的事（详见文件头注释）：

1. 互斥 + 残留检查（有仿真在跑就拒绝启动，**绝不 `pkill` 别人的进程**）
2. 复用 `gazebo.sh` 拉起 Gazebo + Nav2 + RViz2
3. 记录本轮**实际生效**的 AMCL 参数 → `params_snapshot.txt`（含 yaml md5）
4. `capture_truth_pose.py --watch` 连续采样 → `pose_trace.csv`
5. 订阅 `/behavior_tree_log` → `bt_log.txt`（把 Spin / BackUp 变成可 grep 的记录）
6. 启动真实巡航节点
7. 巡逻结束后把新增的 `patrol_runs.csv` 行抽到本轮目录，并**还原共享 CSV**（避免污染批量实验数据集）
8. `Ctrl+C` 时按 `pose_trace.csv` 算末点误差 → `summary.txt`

用法：

```bash
TAG=xxx HOLD=1 bash ~/ros2_ws/scripts/run_amcl_test.sh   # 跑完保持仿真，人工观察后 Ctrl+C
TAG=xxx HOLD=0 bash ~/ros2_ws/scripts/run_amcl_test.sh   # 跑完自动退出并出汇总
```

### 阶段 4：四组单变量实验（A / B / C / D）

| 组 | 参数 | 结果 | 判定 |
|:---:|:---|:---|:---|
| A | `z_hit/z_rand` 0.5/0.5，`alpha` 0.2 | 10/10，207.7 s，末点 0.033 m | 有效基线 |
| B | `z_hit/z_rand` **0.9/0.1**，`alpha` 0.2 | 10/10，198.1 s，末点 0.033 m | **有效** |
| C | `z .9/.1`，`alpha` **0.05** | **8/10，462.0 s，末点 6.892 m** | **失败，已回滚** |
| D | `z .9/.1`，`alpha` 0.2（回滚后复现） | 10/10，199.5 s，末点 **0.009 m** | **B 复现，n=2 定稿** |

数据目录：`experiment_logs/amcl_test/<时间戳>_<TAG>/`

- `20261122_220622_baseline`（A）
- `20261122_224554_zhit09_zrand01`（B）
- `20261123_221425_alpha005`（C，失败组，**原样保留不删**）
- `20261123_224358_zhit09_alpha02_rerun`（D）
- `20261122_215934_baseline`（**作废**，是自写三点驱动版本，与批量链路不可比）

**C 组失败的机理（重要负结果）**：

`alpha` 建模的是**每步独立随机噪声**（随步数开方增长、可互相抵消）。`update_min_a = 0.2 rad` 时 `alpha = 0.05` 给出的航向散开只有 `sqrt(0.05 × 0.04) ≈ 0.045 rad ≈ 2.6°`，而当时观测到的旋转期航向偏差约 40°。**粒子云比真实误差窄十几倍，真值不在粒子覆盖范围内**，激光再准也看不见正确解。叠加 `resample_interval: 1` 每轮砍掉多样性，几十次更新后 2000 个粒子全挤在同一错误假设上 → 118.6 s 在 0.5 s 内位姿瞬移 3.6 m、yaw 跳 258°，**滤波器整体切到另一个错误全局假设**。

当时被推翻的推理（原文记录在案）："实测每 0.4 m 行进偏差 0.098 m，`alpha=0.05` 给出 0.089 m，同量级所以合理" —— 错在拿**瞬时白噪声**去对标**系统性比例偏差**。

### 阶段 5：发现几何错误 `wheel_separation`（本段最重要的一条）

**现象**：旋转段 yaw 误差怎么调都压不下去（超调 +17~20°，旋转期滞后 40°），`alpha`、`z_hit`、`sigma_hit` 全试过无效。

**根因**：差速插件 `wheel_separation` 写 `0.24`，实际轮距是 `0.36`，**差 1.5 倍**。

几何推导：

| 依据 | 值 |
|:---|:---|
| [model.xacro](file:///home/robot/ros2_ws/src/pkg03_gazebo_20260814/urdf/model.xacro#L10-L11) 左右轮组挂载 | `y = ±0.12` |
| [wheel.urdf.xacro](file:///home/robot/ros2_ws/src/pkg03_gazebo_20260814/urdf/parts/wheel.urdf.xacro#L60) 轮心相对轮组再外移 | `motor_l/2 + shaft_length + wheel_length/2 = 0.03+0.02+0.01 = ±0.06` |
| 轮心实际位置 | `±(0.12+0.06) = ±0.18` |
| **接触点实际间距** | **0.36** |
| 插件配置（修正前） | **0.24** |
| 轮径 | 插件 `0.10` vs `wheel_radius 0.05` → **自洽，直线不受影响** |

`sep` 同时用于两处，一个错误同时污染两个方向：

```
反解轮速：v_L = v - w*sep/2 ,  v_R = v + w*sep/2   ⇒ sep 小 ⇒ 物理转向速率 = 指令的 2/3
积分航向：th = (d_R - d_L)/sep                      ⇒ sep 小 ⇒ /odom 航向 = 真值的 1.5 倍
```

**两者叠加后 `/odom` 恰好与指令一致**，于是"里程计看起来挺准"，但真值只有指令的 2/3 —— 这就是此前所有旋转段 yaw 误差的系统性来源，也是阶段 1 "超线性增长" 的真正解释（**不是打滑**）。

**取证工具**：[scripts/odom_spin_probe.py](file:///home/robot/ros2_ws/scripts/odom_spin_probe.py)，发固定角速度转固定时长，同时采 `/odom` 与 `/gazebo/model_states`，打印三个比值。

实测（0.5 rad/s × 2 s，指令 57.3°）：

| 比值 | 修正前（预期） | 修正后（实测） |
|:---|:---:|:---:|
| `odom / 真值` | 1.500 | **1.055** |
| `真值 / 指令` | 0.667 | **0.955** |
| `odom / 指令` | 1.000 | 1.008 |
| 真值转角 | ~38° | **54.7°** |
| odom 转角 | ~57° | **57.8°** |

修正后残余 5.5% 为 Gazebo **真实轮胎滑移**（轮子转够了、地面没跟上），正常量级。

**修复内容**：`urdf/parts/plugins.urdf.xacro` 的 `wheel_separation` `0.24 → 0.36`，带完整注释（两处使用位置、几何推导、双面后果、与 C 组失败的关联、build 提醒）。

**踩到的坑**：注释里写了 ASCII `--`（`colcon build --packages-select ...`），**XML 注释不允许连续两个连字符**，导致 `xacro` 解析失败（`line 52, column 27`）。已改写该句。自查命令：

```bash
cd ~/ros2_ws/src/pkg03_gazebo_20260814 && grep -rn -- '--' urdf/ | grep -v '<!--' | grep -v '-->'
```

**未动**：`worlds/one.world` 里也有一个 0.24，但该 world **无任何引用**（实际启动用 `robocup_home.world` + `spawn_entity` 注入 xacro），是死副本。

### 阶段 6：文档归档 + git 提交

- 四组实验（含失败组）完整归档进 `docs/AMCL_PARAM_SWEEP_ARCHIVE.md`（7 章：目的判据 / 方法 / 参数结果 / 逐组分析 / 缺陷清单 / 结论 / 待办）
- `BUGLOG.md` 新增 `wheel_separation` 条目，并给 C 组条目追加"事后更正"
- `HANDOFF.md` 14.6 补 D 组 + 几何警示，新增 14.7 重建基线待办
- `docs/VERIFY_ODOM_SOURCE.md` 新增第九节（几何错误专章），**D-03 / D-04 待办作废**
- 对比逻辑固化为 `scripts/amcl_compare.py`（避免反复粘贴长 heredoc 被终端破坏）
- git 提交命令已给出（拆两个提交：代码修复 / 文档归档），**是否已执行请以 `git log --oneline -n 3` 为准**

---

## 三、当前实际状态（截至本文档写作时）

### 3.1 已生效的配置

| 文件 | 当前值 | 说明 |
|:---|:---|:---|
| `urdf/parts/plugins.urdf.xacro` | `wheel_separation 0.36`、`wheel_diameter 0.10`、`odometry_source 0` | ✅ 已 build、已重启验证 |
| `config/nav2_params_hybrid.yaml` | `alpha1~4 = 0.2`、`alpha5 = 0.2`、`z_hit 0.9`、`z_rand 0.1`、`sigma_hit 0.05`、`max_beams 180`、`laser_max_range 8.0`、`laser_likelihood_max_dist 2.0`、`update_min_d 0.25`、`update_min_a 0.2`、`DifferentialMotionModel` | 均为 B/D 组定稿值 |
| 控制器参数 | `max_vel_x 0.26`、`max_vel_theta 1.0`、`xy/yaw_goal_tolerance 0.15` | 未动 |
| 差速插件动力学 | `max_wheel_torque 20`、`max_wheel_acceleration 2.0` | 未动 |
| `config/ekf.yaml` | 已存在，`publish_tf: true`、`imu0_differential: false`、`two_d_mode: true`、`world_frame: odom`、`frequency 50` | **从未实跑** |

**两条成对约束（改的时候必须一起改）**：

1. `ekf.yaml` 的 `publish_tf: true` ↔ xacro 的 `publish_odom_tf:=false`。只改一边 = 差速插件和 EKF 抢同一条 TF 边，RViz 里车身来回抽。
2. `imu0_differential` 必须 `false`。写 `true` 不报错，但 IMU 退化成第二个会漂的陀螺仪，M3 核心论点直接作废。

### 3.2 已确认的遗留问题

| 问题 | 状态 |
|:---|:---|
| IMU **零噪声**（`imu.urdf.xacro` 只有 `update_rate 50`，无任何 `<noise>` 参数） | 🔴 未修。协方差全零会让 EKF 把 IMU 当成完美传感器，权重拉满，滤波器退化 |
| `laser_likelihood_max_dist: 2.0` 与 `sigma_hit: 0.05` 不匹配 | 🟡 未处理 |
| 末点航向超调 +17~20°（`yaw_goal_tolerance` 仅 8.6°） | 🟡 机理已明，未做参数验证 |
| `recovery_alpha_fast/slow` 从未实跑验证 | 🟢 未做 |

### 3.3 数据可信度对照（**用数据前必看**）

| 指标类别 | A~D 四组是否可用 | 原因 |
|:---|:---:|:---|
| 位置误差（0.033 / 0.009 m 等） | ✅ **可用** | 轮径自洽，直线运动与 `sep` 无关 |
| 航点成功率 / 巡航耗时 | 🟡 弱受影响 | 转向变慢会拖长耗时，修完后应略快 |
| yaw 误差（全部区间与末点值） | ❌ **失效** | 输入自带 50% 比例误差 |
| 末点航向超调数值 | ❌ 数值失效 | 受物理转速影响，需在新基线重测（机理仍成立） |
| C 组"alpha 不能压低" | ✅ **成立且更充分** | 粒子云 2.6° vs 50% 比例误差，必然跟丢 |

**所以：A~D 四组的 yaw 结论不能进论文，位置结论可以保留。**

---

## 四、方法论（后续所有实验必须沿用）

### 4.1 评估口径：必须用"更新时刻统计"

`/amcl_pose` 受 `update_min_d: 0.25` / `update_min_a: 0.2 rad` 门限约束，**呈阶梯状**。与 0.5 s 连续真值对比时必然存在"车在走、估计不动"的空档，差值就是门限量。

**`summary.txt` 里的"最大位置误差"是阶梯假象，不能作为精度上报**（A 组 0.433 m、B 组 0.474 m 均属此类）。

正确口径：**只在 `/amcl_pose` 数值变化的时刻统计**（`scripts/amcl_compare.py` 默认输出这个口径），或改采 TF `map->base_footprint`。

A 组该口径下：位置误差 mean 0.102 / max 0.336，yaw mean −2.63° / 区间 −17.19° ~ +11.23°。

### 4.2 单变量原则

一轮只改一个参数。C 组之所以把"alpha 回滚"和"z_hit 保持"合并成一组，是因为 D 组目的是**复现**而非探索，已在注释里写明理由。

### 4.3 安全禁区（批量实验环境）

| 禁区 | 原因 |
|:---|:---|
| `pkill -f` 全局匹配 | 会误杀同机其他实验进程 |
| 运行期 `colcon build` | 读 `install/` 副本，会与运行中的节点打架 |
| 动 `/dev/shm` 整机清理 | 影响同机其他进程 |
| 直接写共享 `patrol_runs.csv` | 污染批量实验数据集（脚本已用备份/抽取/还原机制规避） |

### 4.4 参数生效路径（**容易搞错**）

| 文件 | 生效方式 |
|:---|:---|
| `config/nav2_params_hybrid.yaml` | `gazebo.sh` 传的是 `src/` 下**绝对路径**，改即生效，**无需 build** |
| `urdf/parts/*.xacro` | launch 用 `get_package_share_directory()` 读 `install/` **副本**，**必须 `colcon build`** |
| `autopartol_robot/config/partol_config.yaml` | 同上，**必须 build**（除非用了 `--symlink-install`） |

### 4.5 一个反直觉的坑：修正后超调可能变大

修完 `sep` 后物理转速回到 1.0 rad/s，`max_wheel_acceleration: 2.0` 下从 1.0 rad/s 刹停需 0.5 s，期间多转约 14.3°，加容差 8.6° ≈ **23°**（修正前对应约 15°，实测 17~20°）。

**所以修完几何后，末点航向超调很可能从 18° 涨到 22~25°。这不是新 bug，是同一套运动剖面对更快转速的自然结果。** 若确认，可把 `max_vel_theta` 降到 **0.67**（让物理转速回到修正前水平，等效于"只改几何不改运动剖面"），或把 `max_wheel_acceleration` 提到 5。**但这必须作为单独一组，不能和几何修正混在一起。**

---

## 五、剩余待办（按优先级）

| 编号 | 待办 | 优先级 | 命令 / 判据 |
|:---:|:---|:---:|:---|
| E1 | **重建基线 E 组**：`sep 0.36` + `z .9/.1` + `alpha 0.2` | 🔴 下一步 | `TAG=sep036_baseline HOLD=1 bash scripts/run_amcl_test.sh`；跑前重启 Gazebo |
| E2 | 单独测 `update_min_a: 0.2 → 0.05` | 🟡 | 必须在 E1 之后，避免双变量；看超调是否消失 |
| E3 | `max_vel_theta: 1.0` 是否降到 0.67 | 🟡 | 视 E1 超调是否涨到 22~25° 再定 |
| E4 | **IMU 噪声配置**（零协方差 → 加 `<noise>`） | 🔴 阻塞 EKF | 不加则 EKF 权重失真，M3 结论不可信 |
| E5 | `laser_likelihood_max_dist: 2.0` 与 `sigma_hit: 0.05` 匹配性核查 | 🟢 | 现有不匹配项 |
| E6 | EKF 三层验证（节点存活 / TF 单一发布者 / 融合真生效） | 🔴 主线 | 见 `config/ekf.yaml` 与 `launch/ekf_test.launch.py` |
| E7 | `recovery_alpha_fast/slow` 实跑验证 | 🟢 | 从未跑过 |
| E8 | 可选：同步 `worlds/one.world` 的 `wheel_separation` | 🟢 | 该 world 无引用，死副本 |
| E9 | 不同 `wz` 下多测几组探针，量化 4.5% 滑移随角速度的变化 | 🟢 | 若要更精细的 odom 误差模型 |

**E1 之后必须做的事**：E 组是新基线，A~D 与它不再同源。后续所有对照（E2、E3、E5、E7）**都以 E 组为参照**。

---

## 六、如何恢复工作（照着做即可）

### 6.1 跑一组新实验

```bash
# 0) 确认无残留（空输出 + 退出码 1 才继续）
pgrep -af 'gzserver|gzclient|nav2|amcl|partol' || echo "干净"

# 1) 改参数（yaml 改即生效，无需 build）
#    改完记得在 yaml 里写清"本组改了什么、为什么、对照哪一组"

# 2) 重启 Gazebo 保证初始位姿一致，然后跑一轮
cd ~/ros2_ws && TAG=xxx HOLD=1 bash scripts/run_amcl_test.sh

# 3) 人工在 RViz 观察，结束后 Ctrl+C 出 summary.txt
```

### 6.2 看数据

```bash
# 跨组并排对比（更新时刻口径，跨组可比）
python3 ~/ros2_ws/scripts/amcl_compare.py \
  experiment_logs/amcl_test/20261122_220622_baseline \
  experiment_logs/amcl_test/20261122_224554_zhit09_zrand01 \
  experiment_logs/amcl_test/20261123_221425_alpha005 \
  experiment_logs/amcl_test/20261123_224358_zhit09_alpha02_rerun

# 几何/里程计比值探针（Gazebo 已启动时）
python3 ~/ros2_ws/scripts/odom_spin_probe.py 0.5 2.0
```

### 6.3 判断一组实验是否"可用"

看四件事：

1. 航点成功率是否 10/10
2. `bt_log.txt` 里有无 `Spin` / `Backing Up`（有则说明发生过恢复行为）
3. 末点位置误差量级（正常 < 0.05 m）
4. `params_snapshot.txt` 的 md5 是否与预期参数一致（**证明这一轮跑的是哪套配置**）

---

## 七、术语与代号速查（给忘了上下文的人）

| 代号 / 术语 | 含义 |
|:---|:---|
| **M3** | 项目阶段名：EKF 融合 `/odom` + `/imu`，验证融合优于纯轮式 |
| **A 组** | 纯 `/odom` 导航（无 EKF），本段用作 AMCL 基线 |
| **B 组** | 本段指 `z_hit 0.9 / z_rand 0.1` 那一组（与 M3 的 B 组含义不同，注意区分） |
| **真值 / ground truth** | `/gazebo/model_states` 里的机器人位姿，唯一可信参照 |
| **更新时刻口径** | 只在 `/amcl_pose` 数值变化的时刻统计误差，排除门限阶梯假象 |
| **粒子耗尽（particle depletion）** | 粒子云覆盖范围小于真实误差，叠加逐轮重采样导致多样性丧失，滤波器无法自救 |
| **系统性比例偏差** | 误差随距离/转角**线性累积、不可抵消**（如轮距配错）；区别于可抵消的白噪声 |
| **`sep`** | `wheel_separation` 的简写 |
| **死副本** | 存在但无任何引用的配置文件（如 `worlds/one.world`） |

---

## 八、一句话结论

这段对话把 M3 的两个前置条件**都清掉了**：`/odom` 已从"真值"改为"会漂的编码器积分"，AMCL 参数已与仿真实际状态对齐，且**在最后关头揪出了一个 1.5 倍的几何错误**——这个错误此前一直被误认为"轮胎打滑"，导致三组实验的 yaw 结论全部建立在错误前提上。

代价是 A~D 四组的 yaw 指标作废，必须重建基线。**但这不是浪费**：C 组失败反而成了最有力的证据——"用调参去掩盖几何错误，只会让滤波器彻底跟丢"。

下一步只有一件事：**E1 重建基线**。