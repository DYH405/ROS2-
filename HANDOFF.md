# ROS2 仿真导航项目 — 交接文档

> 更新时间：2026-11-28
> 2026-11-25 按当前 `master` 校正：Nav2 参数入口、IMU/EKF 链路状态、rosbag 话题数
> 2026-11-27 补第十五节（许可统一、实验脚本实跑修复、单轮冒烟通过）；14.7 待办表按 E~G 组实测结论更正；第八节 Git 状态刷新
> 2026-11-28 补第十六节（无人值守闭环加固、收摊假阳性修复、当前配置噪声底）；15.7 待验证项已转「已实跑验证」
> 当前阶段：M3 EKF 前置 — **E 组基线已于 11-24 完成**，下一步看 `transform_tolerance`（归档 S11）与视觉现象形态确认（S14）

---

## 一、项目概况

| 项目 | 内容 |
|:---|:---|
| 工作空间 | `~/ros2_ws` |
| ROS2 版本 | Humble |
| 仿真环境 | Gazebo |
| 导航框架 | Nav2 |
| 建图工具 | SLAM Toolbox (online_async) |
| Git 远端 | `https://github.com/DYH405/ROS2-.git` |
| 核心功能包 | `pkg03_gazebo_20260814`, `autopartol_robot`, `robot_speech`, `robot_vision` |

---

## 二、已完成内容

### 2.1 一键启动 — `gazebo.sh`

- 路径：`src/pkg03_gazebo_20260814/scripts/gazebo.sh`
- 流程：Gazebo 仿真 → Nav2(AMCL定位+导航) → RViz2
- 特性：cleanup 优雅退出、共享内存清理、headless 模式

### 2.2 SLAM 建图 — `slam.sh`（新建）

- 路径：`src/pkg03_gazebo_20260814/scripts/slam.sh`
- 流程：
  1. 启动 Gazebo 仿真
  2. 检查核心话题（/scan、/odom）+ 验证数据频率
  3. 启动 SLAM Toolbox (online_async)
  4. 检查 /map 话题
  5. 启动 RViz2 + rqt_robot_steering
  6. 防御性创建地图目录
  7. 提示保存地图命令
- 特性：话题检查、数据验证、遥控工具、cleanup 含 steering

### 2.3 正常定位 + 正常导航

- 地图：`src/pkg03_gazebo_20260814/maps/my_map.yaml` + `my_map.pgm`
- Nav2 参数：`src/pkg03_gazebo_20260814/config/nav2_params_hybrid.yaml`（当前入口；`nav2_params.yaml` 为基线备用）
- 巡逻节点：`autopartol_robot` — 10个巡逻点 + 超时机制（`total_goals` 语义 = 巡逻点数量 = 10）
- 联合启动：`autopartol.launch.py`（巡逻+语音+图像）
- 健壮性修复（2026-10-25）：
  - `goToPose()` 返回值检查，目标被拒时返回 `'rejected'`，不重试
  - `elapsed` 防御性初始化，避免 UnboundLocalError
  - `getFeedback()` 空判断 + 日志节流（1秒间隔）
  - `rejected`/`canceled` 确定性失败不重试，`rejected` 独立计数
  - `spin_once` timeout_sec 从 0.0 改为 0.05，避免 CPU 忙等
  - `max_rounds` 参数支持多轮巡逻 + 全程统计
  - `gazebo.sh` 新增 `--no-rviz` 参数

> ⚠️ **IMU 状态说明**：IMU（`/imu`）已接入 `robot_localization` EKF 融合链路 —— `config/ekf.yaml` + `launch/ekf_test.launch.py` + `scripts/gazebo_ekf.sh` + `scripts/run_ekf_line.sh`。`ekf_test.launch.py` 传 `publish_odom_tf:=false`，差速插件不再发 `odom -> base_footprint`，由 `ekf_filter_node` 接管该 TF 并输出 `/odometry/filtered`。默认入口 `gazebo.sh` 仍走 AMCL（基于 `/scan` + `/odom`）。

### 2.4 rosbag 录制 — `record_30s.sh`（已优化）

- 路径：`src/pkg03_gazebo_20260814/scripts/record_30s.sh`
- 录制话题：`/scan /tf /tf_static /cmd_vel /odom /plan /amcl_pose /imu /clock /odometry/filtered /gazebo/model_states /navigate_to_pose/_action/status`（12个）
- 特性：
  - 话题就绪检测：录制前等待 /odom /scan /cmd_vel 出现
  - 双模式停止：默认 Ctrl+C / `-w` 模式监听话题消失自动停止
  - 话题消失确认机制：连续10次（20秒）检测不到才判定
  - cleanup 优雅退出，保证 bag 完整写入
  - 参数：`./record_30s.sh`（默认）/ `./record_30s.sh -w`（自动停止）
- 历史数据：`bag_data/` 下有 17 组旧录制

### 2.5 Python 分析 — `bag_analyzer.py`（新建）

- 路径：`scripts/bag_analyzer.py`
- 当前功能：读取 bag → 解析 /odom → 绘制轨迹图 (trajectory.png)
- 用法：`python3 scripts/bag_analyzer.py ~/ros2_ws/bag_data/bag_01`
- 依赖：`rosbag2_py`, `matplotlib`

### 2.6 Git 版本管理（修复重建）

- 旧仓库对象损坏（9个空文件），无远端可修复 → 重建
- `.gitignore`：排除 build/install/log/bag_data/__pycache__/.git_broken_backup 等
- 提交记录：
  1. `feat: 初始提交 - ROS2仿真导航项目基线`
  2. `feat: 新增SLAM建图脚本和bag数据分析脚本`
  3. `docs: 添加第一阶段交接文档`
  4. `feat: 优化bag录制脚本-双模式停止+话题确认机制+amcl_pose`
  5. `chore: .gitignore排除巡逻截图文件`
- 远端：已推送至 GitHub
- `.gitignore` 新增：`img_*.png`（巡逻截图）

---

## 三、踩过的坑

### 坑1：Git 对象损坏

- 现象：`fatal: 松散对象 ... 已损坏`，9个对象文件为 0 字节
- 原因：写入时异常中断（断电/强杀），导致对象文件被创建但内容为空
- 解决：备份旧 .git → `git init` 重建 → `.gitignore` → 首次提交
- 教训：**有远端仓库才能 `git fetch` 修复，否则只能重建**

### 坑2：.git_broken_backup 被提交

- 现象：`git add -A` 把备份目录的几百个对象文件全加进去了
- 原因：`.gitignore` 里没排除 `.git_broken_backup`
- 解决：追加到 `.gitignore` → `git rm -r --cached` 移除 → amend 合并提交
- 教训：**备份目录也要加入 .gitignore**

### 坑3：Shell heredoc 未闭合

- 现象：终端出现 `>` 提示符，等待输入
- 原因：`echo "..."` 的引号未闭合
- 解决：Ctrl+C 退出，重新执行
- 教训：**多行写入用 `cat > file << 'EOF'` 更可靠**

### 坑4：cleanup 函数名与 trap 不匹配

- 现象：Ctrl+C 无法触发清理函数，进程残留
- 原因：函数名写成 `up()`，但 `trap cleanup` 调用的是 `cleanup`
- 解决：统一函数名为 `cleanup`
- 教训：**trap 引用的函数名必须与定义一致**

### 坑5：Python Path vs str

- 现象：`AttributeError: 'str' object has no attribute 'exists'`
- 原因：`argparse` 返回 str，没包裹 `Path()`
- 解决：`bag_path = Path(args.bag_path)`
- 教训：**argparse 返回值永远是 str，需要 Path() 转换才能用路径方法**

### 坑6：时间戳缩进错误

- 现象：所有时间戳都显示 t=0.00
- 原因：`t = timestamp/1e9 - t0` 缩进在 `if t0 is None:` 内部，只在第一次计算
- 解决：把 `t = ...` 移到 `if` 外面
- 教训：**Python 缩进决定逻辑，if 内外的代码要分清**

### 坑7：matplotlib 中文乱码

- 现象：`UserWarning: Glyph ... missing from font(s) DejaVu Sans`
- 原因：默认字体 DejaVu Sans 不支持中文
- 解决：图表标签改用英文
- 教训：**技术图表用英文是行业惯例，跨机器兼容**

### 坑8：map_saver_cli 参数后缀

- 现象：`-f .../my_map.yaml` 导致生成 `my_map.yaml.yaml`
- 原因：`-f` 参数是路径前缀，程序自动追加 .yaml 和 .pgm
- 解决：`-f .../my_map`（不带后缀）
- 教训：**-f 是前缀不是文件名，不要加后缀**

### 坑9：话题消失误判

- 现象：小车还在跑，录制就自动停止了
- 原因：`ros2 topic list` 偶尔返回不完整，一次检测不到就误判为话题消失
- 解决：连续确认机制（confirm_threshold=10，共20秒窗口）
- 教训：**一次性检测不可靠，需要连续多次确认**

### 坑10：DDS 缓存延迟

- 现象：关闭 Gazebo 后，话题仍然存在于 `ros2 topic list` 中
- 原因：ROS2 DDS 中间件会缓存话题信息，发布者关闭后不会立即消失
- 解决：等待一段时间（十几秒），话题最终会消失
- 教训：**话题消失有延迟，确认阈值要覆盖 DDS 缓存时间**

### 坑11：Git 远端 URL 反引号

- 现象：`git push` 报 GnuTLS 错误
- 原因：添加远端时 URL 被反引号包裹，bash 把反引号当命令替换
- 解决：`git remote set-url origin "https://..."`（用双引号）
- 教训：**shell 中设置 URL 要用双引号包裹，防止特殊字符解析**

### 坑12：巡逻截图被提交

- 现象：`git add -A` 把 `img_*.png` 截图文件加进暂存区
- 原因：`.gitignore` 没排除运行时生成的截图
- 解决：追加 `img_*.png` 到 `.gitignore`
- 教训：**运行时生成的数据文件要排除，和 build/install 同理**

---

## 四、待打磨任务

### 4.1 第一阶段基线（✅ 已完成，bag_analyzer 扩展见 4.5 暂缓区）

第一阶段基线任务均已完成，bag_analyzer 相关扩展功能统一延后（见 4.5）。

### 4.2 建立可复现基线（中优先级）

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 🟡 | 固定测试场景 | 同一地图 + 同一起点 + 同一目标点 + 同一导航参数 |
| 🟡 | 自动化重复测试脚本 | 重复N次导航 + 录制 + 分析 |
| 🟡 | 统计基线指标 | 成功率、位置误差、航向误差、路径长度、耗时 |
| 🟡 | 定义完成标准 | 每项任务有量化达标条件 |

### 4.3 slam.sh 优化（低优先级）

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 🟡 | 封装话题检查函数 | `check_topic()` + `check_topic_hz()` |
| 🟢 | 增加重试+超时机制 | 话题检查失败时重试N次，设超时 |

### 4.4 其他

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 🟡 | gazebo.sh 也封装话题检查 | 和 slam.sh 保持一致的代码风格 |

### 4.5 🔕 暂缓：bag_analyzer 扩展

> **状态：全部暂缓，不作为当前工作的前置任务。** 第一阶段基线已建立（bag_analyzer 已支持 /odom + /plan 基本轨迹绘制），以下扩展功能留待后续第二阶段/第三阶段需要时再开启。

| 任务 | 说明 | 原始出处 |
|:---|:---|:---|
| bag_analyzer 支持 /scan | 读取 LaserScan，绘制雷达扫描图 | 4.1 |
| 规划路线 vs 实际轨迹对比图 | 同一画布叠加 /plan 和 /odom，需先完成 plan 分组拼接 | 4.1 |
| bag_analyzer 统计报告 | 路径长度、平均速度、耗时、位置误差 | 4.1 + 9.3 |
| `group_plans_by_goal` | 按终点坐标分组，`threshold=0.5` | 9.3 |
| `build_reference_path` | 每组取最后一条 plan 拼接为完整 reference path | 9.3 |
| `plot_comparison` | reference path vs 实际轨迹叠加 | 9.3 |
| bag_analyzer 支持 /cmd_vel | 读取 Twist，绘制速度曲线 | 4.4 |
| bag_analyzer 自动检测话题 | 根据 bag 中实际话题自动选择分析 | 4.4 |
| bag_analyzer 命令行参数 | `--odom` `--scan` `--plan` 参数控制 | 4.4 |

---

## 五、项目五阶段规划（Codex 建议）

> 课题核心：**面向室内巡检任务的ROS2移动机器人故障检测与分级恢复，并通过不确定性仿真和回归实验进行验证。**

> ⚠️ 原五阶段规划已降级，归档见 `docs/archive/ROADMAP_FAULT_DETECTION_ARCHIVE.md`，当前主线见路线图 v2.0。

### 第一阶段：建立可复现的仿真基线

- 固定：同一地图、起点、目标点、导航参数
- 每个场景重复≥10次
- 记录：/cmd_vel /odom /scan /tf /plan /amcl_pose
- 统计：成功率、位置误差、航向误差、路径长度、耗时

### 第二阶段：分层注入不确定性

| 类别 | 注入内容 | 观察指标 |
|:---|:---|:---|
| 控制/底盘 | 轮速比例误差、响应延迟 | 轨迹误差、到点误差 |
| 里程计 | 噪声、比例误差、短时跳变 | odom漂移、定位偏差 |
| 雷达 | 延迟、丢帧、数据停更 | AMCL协方差、导航状态 |
| 负载 | 质量和重心变化 | 运动误差、成功率 |

### 第三阶段：故障检测与分类

- Topic超时：多久无新消息才报警
- TF超时：查哪对坐标系，等多久
- 有命令无运动：比较 /cmd_vel 与轮速/里程计变化
- 雷达异常：消息超时、有效点比例过低
- 里程计跳变：速度/加速度是否超出合理范围
- 定位异常：协方差阈值 + 连续N次超限

### 第四阶段：分级恢复与安全边界

- 雷达短时中断 → 停车等待恢复
- 代价地图异常 → 清理局部代价地图 + 重新规划
- 有命令无运动 → 停车 + 限制重试次数
- TF/里程计丢失 → 保持停止，不盲目后退
- 定位协方差异常 → 停止任务 + 等待重新定位

### 第五阶段：自动化回归与结果对比

| 编号 | 注入条件 | 预期行为 | 指标 |
|:---|:---|:---|:---|
| T01 | 正常导航 | 到达目标 | 成功率、误差、耗时 |
| T02 | 雷达停止发布 | 报警并停车 | 检测时间、误报 |
| T03 | 里程计停止发布 | 取消导航并停车 | 停车时间 |
| T04 | 轮速偏差10% | 误差上升 | 误差变化 |
| T05 | 有命令无运动 | 判定卡滞并停车 | 检测率、误报 |
| T06 | 故障短暂恢复 | 有条件恢复 | 恢复成功率 |

---

## 六、关键文件索引

| 文件 | 路径 | 说明 |
|:---|:---|:---|
| gazebo.sh | `src/pkg03_gazebo_20260814/scripts/gazebo.sh` | 一键启动（导航模式） |
| slam.sh | `src/pkg03_gazebo_20260814/scripts/slam.sh` | 一键启动（建图模式） |
| record_30s.sh | `src/pkg03_gazebo_20260814/scripts/record_30s.sh` | 30秒 bag 录制 |
| bag_analyzer.py | `scripts/bag_analyzer.py` | bag 数据分析工具 |
| delete_old_images.py | `scripts/delete_old_images.py` | 清理旧图片 |
| nav2_params.yaml | `src/pkg03_gazebo_20260814/config/nav2_params.yaml` | Nav2 参数配置 |
| my_map.yaml | `src/pkg03_gazebo_20260814/maps/my_map.yaml` | 导航地图 |
| partol_node.py | `src/autopartol_robot/autopartol_robot/partol_node.py` | 巡逻导航节点 |
| partol_config.yaml | `src/autopartol_robot/config/partol_config.yaml` | 10个巡逻点配置 |
| autopartol.launch.py | `src/autopartol_robot/launch/autopartol.launch.py` | 巡逻联合启动 |
| patrol_runs.csv | `experiment_logs/patrol_runs.csv` | 巡逻实验指标落盘（12 列，T-P1-01 产出） |
| patrol_runs_v1_11cols_backup.csv | `experiment_logs/patrol_runs_v1_11cols_backup.csv` | 11 列表头历史备份（T-P1-01-FIX 处置留存） |
| run_one_experiment.sh | `scripts/run_one_experiment.sh` | 单次端到端实验脚本（重启→就绪→巡逻→落盘→真值→关闭，T-P1-02A 产出） |
| capture_truth_pose.py | `scripts/capture_truth_pose.py` | 末点真值 + AMCL 末点采集（`--watch` / `--finalize`，T-P1-02A 产出） |
| truth_last_pose.csv | `experiment_logs/truth_last_pose.csv` | 末点真值旁路文件（7 列，运行时生成） |
| archive/baseline_results_20261023 | `archive/baseline_results_20261023/` | 旧基线目录归档（未纳入 Git，见 12.8 遗留风险） |
| BUGLOG.md | `BUGLOG.md` | 问题记录（现象/根因/处置/教训） |
| .gitignore | `.gitignore` | Git 忽略规则 |

---

## 七、环境依赖

| 依赖 | 版本/状态 | 安装方式 |
|:---|:---|:---|
| ROS2 Humble | 已安装 | 系统安装 |
| Gazebo + ros2_control | 已安装 | 系统安装 |
| slam_toolbox | 已安装 | 系统安装 |
| nav2_bringup | 已安装 | 系统安装 |
| rqt_robot_steering | 已安装 | `apt install ros-humble-rqt-robot-steering` |
| matplotlib | 3.10.9 | 系统 Python 可用 |
| rosbag2_py | 可用 | ROS2 自带 |

---

## 八、Git 状态

- 分支：master
- 远端：`https://github.com/DYH405/ROS2-.git`（`git remote -v` 回读显示 URL 字面含反引号，见 BUGLOG 2026-11-04 条目）
- 当前 HEAD：`6a51916`（docs: 修正 AMCL 归档内两处 VERIFY_ODOM_SOURCE 旧路径）
- VM 内 origin/master：`6a51916`（**2026-11-27 已与本地一致**；`git ls-remote origin refs/heads/master` 回读成功）
- 提交数：以 `git rev-list --count HEAD` 实测为准（11-04 记录「21」已过旧，勿引用）
- 旧 .git 备份：`.git_broken_backup/`（已在 .gitignore 中排除）
- `.trae/`（IDE 配置目录）已加入 `.gitignore`，不入库
- ⚠️ 2026-11-27 工作区未提交改动（无人值守闭环加固，见第十六节）：`scripts/run_one_experiment.sh`、`src/autopartol_robot/launch/autopartol.launch.py`、`src/autopartol_robot/config/partol_config.yaml`、`src/autopartol_robot/autopartol_robot/partol_node.py`

---

## 九、2026-10-19 更新：bag_analyzer 扩展 /plan 支持

### 9.1 本次完成内容

| 功能 | 说明 |
|:---|:---|
| `read_all_messages()` | 合并遍历，一次读取 `/odom` + `/plan`，解决 SequentialReader 只能遍历一次的问题 |
| `plot_plan()` | 读取 `/plan`（nav_msgs/msg/Path），绘制最后一条规划路径，保存为 `planned_path.png` |
| `main()` 更新 | 调用 `read_all_messages` + `plot_plan`，打印 plan 数据预览 |
| 新 bag 录制 | `bag_20261017_234254`：217s、7话题完整数据、136条/plan |
| 验证通过 | `python3 scripts/bag_analyzer.py bag_data/bag_20261017_234254` 成功生成 trajectory.png + planned_path.png |

### 9.2 关键设计决策

- **SequentialReader 单次遍历**：`read_odom_messages` 和 `read_plan_messages` 合并为 `read_all_messages`，用 `if/elif` 在同一 while 循环中处理多话题
- **`/plan` 数据结构**：`plan_data = [(t, [(x,y),...]), ...]`，每条 Path 消息存为一组点（与 `/odom` 每条消息一个点不同）
- **`plot_plan` 默认画最后一条**：当前仅绘制最后一条规划路径，完整 reference path 需要拼接

### 9.3 🔕 暂缓：plan 分组拼接 → reference path

> **状态：暂缓，已迁入 4.5 统一管理。** 详细设计需求见 4.5 节 `group_plans_by_goal` / `build_reference_path` / `plot_comparison` 条目。

> 虚拟机 `bag_analyzer.py` 中 `group_plans_by_goal` 已留注释占位，主机上已完成。

### 9.4 本次踩坑

| 坑 | 现象 | 原因 | 解决 |
|:---|:---|:---|:---|
| SequentialReader 二次遍历为空 | `plan_data` 始终为空列表 | 第一次遍历后指针到末尾，`has_next()` 返回 False | 合并为 `read_all_messages`，一次遍历 |
| plan 数据缩进错误 | 同一条路径被重复添加 N 次 | `if t0`/`t`/`append` 缩进在 `for` 循环内部 | 移到 `for` 循环外面（坑6同类问题） |
| 函数名拼写 | `read_plan_maessages` | 多打了一个 `a` | 改为 `read_plan_messages` |

### 9.5 新 bag 数据概况

| Bag | 时长 | /odom | /plan | /scan | /cmd_vel | /amcl_pose | /tf | /tf_static |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `bag_20261017_231931` | ~28s | 1374 | 13 | 275 | 257 | 10 | 2157 | 1 |
| `bag_20261017_233550` | ~30s | 1431 | 18 | 287 | 344 | 11 | 1215 | 1 |
| `bag_20261017_234254` | ~217s | 10583 | 136 | 2117 | 2817 | 126 | 3306 | 1 |

### 9.6 待打磨任务更新

原 4.1 节高优先级任务进度（**bag_analyzer 扩展全部暂缓，见 4.5**）：

| 任务 | 状态 |
|:---|:---:|
| bag_analyzer 支持 /plan | ✅ 已完成 |
| bag_analyzer 支持 /scan | 🔕 暂缓（见 4.5） |
| 规划路线 vs 实际轨迹对比图 | 🔕 暂缓（见 4.5） |
| bag_analyzer 统计报告 | 🔕 暂缓（见 4.5） |
| 录制新 bag（7话题完整数据） | ✅ 已完成（bag_20261017_234254） |

---

## 十、2026-10-20 更新：Hybrid 规划器切换 + 巡逻点修正 + 图片路径修复

### 10.1 全局规划器切换：NavfnPlanner(Dijkstra) → SmacPlannerHybrid(DUBIN)

| 项目 | 旧值 | 新值 |
|:---|:---|:---|
| 配置文件 | `nav2_params.yaml` | `nav2_params_hybrid.yaml`（新建） |
| planner plugin | `nav2_navfn_planner/NavfnPlanner` | `nav2_smac_planner/SmacPlannerHybrid` |
| motion_model | 无 | `DUBIN`（只前进不后退） |
| minimum_turning_radius | 无 | `0.26`（从速度参数推算） |
| expected_planner_frequency | 20.0 | 5.0（Hybrid 在 SE2 三维空间搜索，计算量更大） |
| max_iterations | 无 | 1000000 |
| smoother | 无 | 开启 SimpleSmoother（holonomic: False） |
| use_astar | false | 删除（Hybrid 内部就是 A*） |
| tolerance | 0.5 | 删除（Hybrid 通过代价地图膨胀处理容差） |

**关键设计决策**：
- **DUBIN 而非 REEDS_SHEPP**：当前场景不需要倒车，DUBIN 运动模型更简单、搜索空间更小、规划更快
- **minimum_turning_radius = 0.26**：由 `max_vel_x / max_vel_theta` 推算，如不合适可调整
- **expected_planner_frequency 降至 5Hz**：Hybrid 在 (x, y, θ) 三维空间搜索，20Hz 可能跑不到

**效果**：全局规划路径从带尖角的折线变为平滑曲线（圆弧转弯），导航更流畅

### 10.2 巡逻点修正

#### 10.2.1 删除原点目标 (0,0,0)

- **问题**：巡逻点第一个为 `(0.0, 0.0, 0.0)`，小车在初始位置就往原点跑，导致 AMCL 粒子收敛到地图原点附近，原点附近特征不明显，引发定位跳变
- **解决**：删除第一个巡逻点，从 `(2.0, 1.0, 0.0)` 开始

#### 10.2.2 yaw 角度归一化到 [-π, π]

- **问题**：最后两个巡逻点 yaw 值超出 [-π, π] 范围（3.927 和 5.498），AMCL 运动模型更新时角度差过大，导致粒子发散、定位失效
- **修正**：

| 点 | 旧 yaw | 新 yaw | 角度 |
|:---:|:---|:---|:---|
| 3 | 2.358 | 2.356 | 135°（微调精确值） |
| 6 | 3.927 | -2.356 | 225° → -135° |
| 7 | 5.498 | -0.785 | 315° → -45° |

**原理**：AMCL 粒子角度更新是加法 `θ_new = θ_old + Δθ + noise`，yaw 在 [-π, π] 范围内可以避免跨越 ±π 边界的角度跳变问题

### 10.3 图片保存路径修复

- **问题**：`img_save_path` 默认值为空字符串，`cv2.imwrite()` 用相对路径保存到 CWD（当前工作目录），从不同目录启动脚本导致图片散落在 `~/ros2_ws/` 和 `~/ros2_ws/scripts/` 等多处
- **解决**：
  - `autopartol.launch.py` 中传入 `img_save_path: '/home/robot/ros2_ws/patrol_images/'`（绝对路径，末尾带 `/`）
  - 创建专用目录 `~/ros2_ws/patrol_images/`
- **根因**：launch 文件未传参数 → 节点用空字符串默认值 → 相对路径 → CWD 依赖

### 10.4 AMCL 跳变问题诊断记录

| 现象 | 原因 | 解决 |
|:---|:---|:---|
| 小车在初始位置往 (0,0,0) 跑 | 巡逻点第一个就是原点 | 删除原点巡逻点 |
| 倒数第二个点定位失效 | yaw 超出 [-π, π]，粒子角度发散 | yaw 归一化 |
| 雷达显示突然跳变 | 目标点附近特征不明显 + 角度异常 | 综合上述修正 |

**后续调参方向**（如跳变仍未完全消除）：
- 增大粒子数：`min_particles: 500→800, max_particles: 2000→4000`
- 降低重采样频率：`resample_interval: 1→2`
- 降低运动噪声：`alpha1~alpha4: 0.2→0.1`（仿真里程计较准）
- 开启恢复机制：`recovery_alpha_fast: 0.0→0.1, recovery_alpha_slow: 0.0→0.001`

### 10.5 关键文件索引更新

| 文件 | 路径 | 说明 |
|:---|:---|:---|
| nav2_params_hybrid.yaml | `src/pkg03_gazebo_20260814/config/nav2_params_hybrid.yaml` | Nav2 Hybrid 规划器配置（当前使用） |
| nav2_params.yaml | `src/pkg03_gazebo_20260814/config/nav2_params.yaml` | Nav2 原始配置（Dijkstra，备用） |
| patrol_images/ | `patrol_images/` | 巡逻截图统一保存目录 |

---

## 十一、2026-10-22 更新：巡逻节点稳健性打磨

### 11.1 本次完成内容

| 编号 | 修复项 | 改动文件 | 说明 |
|:---:|:---|:---|:---|
| E | `spin_once` 超时一致性 | `partol_node.py` | 主循环与内层循环统一使用 `timeout_sec=0.0`（非阻塞轮转） |
| F | 巡逻统计日志 | `partol_node.py` | 每轮结束打印成功/失败/超时/取消计数和耗时 |
| A | 导航重试机制 | `partol_node.py` + `partol_config.yaml` | 单点失败后可重试 N 次，重试耗尽后可跳过或停止 |
| C | `get_current_pose` 死循环消除 | `partol_node.py` | 去掉 `while rclpy.ok()` 误导性外层循环，调用方检查返回值 |

### 11.2 use_sim_time 统一

| 文件 | 改前 | 改后 |
|:---|:---|:---|
| `partol_config.yaml` | `use_sim_time: false` | `use_sim_time: true` |
| `autopartol.launch.py` | 未传递 `use_sim_time` | 三个节点均传入 `use_sim_time=True` |

**原因**：Nav2/Gazebo 全链路使用仿真时钟，巡逻节点用系统时钟会导致 TF 查找、超时判断等行为异常。

### 11.3 导航重试机制设计

**新增参数**（`partol_config.yaml` 可覆盖）：

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `nav_retry_count` | 2 | 单点最大重试次数（总共尝试 3 次：1 次原始 + 2 次重试） |
| `nav_fail_action` | `skip` | 重试耗尽后行为：`skip` 跳过该点继续 / `stop` 停止整轮巡逻 |

**重试逻辑**：

```
对每个目标点：
  ├─ for attempt in range(retry+1):
  │   ├─ succeeded → break 跳出重试
  │   └─ 失败 → warn 日志 + 继续重试 / error 日志 + 重试耗尽
  ├─ 成功 → 保存图片、记录位姿
  └─ 失败 → 计数 + 根据 fail_action 决定跳过或停止
```

**设计决策**：
- `timeout`/`failed`/`canceled`/`unknown` 四种失败状态均触发重试（简化实现，覆盖绝大多数场景）
- 默认 `skip` 而非 `stop`：巡检任务更看重"尽量多覆盖"，且故障检测方向需要观察失败后的行为

### 11.4 get_current_pose 修复

| 改动 | 改前 | 改后 |
|:---|:---|:---|
| 去掉 `while rclpy.ok()` | 外层套了 `while` 死循环（实际只跑一次就 return） | 直接 `for` 循环重试，结构诚实 |
| 调用方检查返回值 | `partol.get_current_pose()` 返回值被丢弃 | 赋值给 `pose_result`，None 时打 warn 日志 |
| 重试日志 | 无序号 | 加 `({i+1}/{max_retries})` 序号 |
| 错别字 | `坐标换` | `坐标变换` |

### 11.5 待办记录

| 项 | 优先级 | 说明 |
|:---|:---:|:---|
| B | 📌待办 | 导航超时时间改为可配置参数（当前硬编码 60s） |
| D | 📌待办 | 图片保存加等待确认（当前异步无等待） |

### 11.6 关键文件索引更新

| 文件 | 路径 | 说明 |
|:---|:---|:---|
| partol_config.yaml | `src/autopartol_robot/config/partol_config.yaml` | 巡逻点配置 + 重试参数 + use_sim_time + CSV 路径 |
| autopartol.launch.py | `src/autopartol_robot/launch/autopartol.launch.py` | 巡逻联合启动 + use_sim_time 传递 |

---

## 十二、2026-11-01 更新：实验指标落盘 + 初始状态一致性约定

### 12.1 巡逻结果落盘（T-P1-01）

每轮巡逻结束向 `experiment_logs/patrol_runs.csv` 追加一行，**只追加不覆盖**历史；表头仅首次写入；目录不存在时自动创建；写失败只打 warn，不中断巡逻。

CSV 正式表头（**12 列，顺序不可改，后续卡沿用**）：

```
run_id,start_time,end_time,total_goals,succeeded,failed,timeout,canceled,rejected,total_time_s,max_rounds,note
```

| 字段 | 语义 |
|:---|:---|
| `run_id` | 开始时间戳 + 轮次，如 `20261101_173210_r1` |
| `start_time` / `end_time` | 墙上时钟 ISO（便于与日志目录对应） |
| `total_goals` | 本轮目标点总数 = 巡逻点数量 = **10** |
| `succeeded` | 本轮成功到达的点数 |
| `failed` | **仅**统计 timeout/canceled/rejected 之外的失败（`failed`/`unknown`） |
| `timeout` | 重试耗尽后仍超时的点数（独立计数，不并入 failed） |
| `canceled` | 重试耗尽后仍被取消的点数（独立计数，不并入 failed） |
| `rejected` | 目标被 Nav2 拒绝的点数（独立计数，不并入 failed；不重试） |
| `total_time_s` | 本轮耗时（**仿真时钟**，与 console「耗时」同源，实测差 0.0s） |
| `max_rounds` | 本轮生效的 `max_rounds` 参数值 |
| `note` | 本轮结束状态，如 `completed` |

### 12.2 验收等式（5 项，含 rejected）

```
succeeded + failed + timeout + canceled + rejected == total_goals
```

> ⚠️ 早期文档写的是 4 项（不含 `rejected`）。`rejected` 独立计数后，等式**必须加 `rejected` 项**，否则只要出现目标被拒就不成立。
>
> 配合 `nav_fail_action: skip`，每个点必落入上述五个分支之一，等式恒成立。

### 12.3 每次 run 前必须重启 Gazebo（初始状态一致性约定）

**约定**：每次实验 run 前**必须重启 Gazebo**，保证机器人初始位姿一致；不允许"只关巡逻节点、Gazebo 不动"接着跑下一轮。

**原因**：

- `init_robot_pose()` 无条件调用 `setInitialPose(initial_point)`，其中 `initial_point = [0.0, 0.0, 0.0]` → yaw = 0（朝东）
- 巡逻点表末点为 `[0.0, 0.0, 1.571]` → yaw = 1.571（朝北）
- 不重启 Gazebo 时，机器人物理位姿保留上一轮终态（yaw ≈ 1.571），而 AMCL 被告知 yaw = 0 → **偏差约 90°**

**现象**：AMCL 粒子云按错误的初始假设撒开，与地图匹配失败 → 粒子发散 → RViz 中定位四处漂移 → 随机器人移动、观测累积逐步收敛，雷达边界才与地图边缘重合。漂移期间导航不可信。

**处置（方案 A）**：每次 run 前重启 Gazebo，机器人回到 yaw = 0，与 `initial_point` 一致，不触发漂移。

**落地方向**：T-P1-02 批量脚本中，每次 run 前重启 Gazebo 作为固定步骤，不依赖人工。

### 12.4 AMCL 漂移实测证据（2026-11-01 采集）

采集方式：`ros2 topic echo /amcl_pose` 整轮记录，取首/末帧；yaw 由四元数 `2*atan2(z,w)` 换算。

| 场景 | init 位姿（AMCL 实测） | 末点位姿 / yaw（AMCL 实测） | 与 `initial_point (0,0,0)` 偏差 |
|:---|:---|:---|:---|
| 重启 Gazebo 后第一轮 | `(0.00001, -0.000002)`, yaw ≈ **-0.004°** | `(0.0337, -0.1402)`, yaw ≈ **108.43°** | 起点 ≈ 0，与 initial_point 一致 ✅ |
| 不重启，紧接着第二轮 | 首帧 = 上轮末帧 `(0.0337, -0.1402)`, yaw **108.43°**；随后新发布帧 yaw **98.57°** → **85.18°** | `(0.0757, -0.1241)`, yaw ≈ **106.34°** | 位置偏差 **0.144 m**，yaw 偏差 **约 85°~108°**（预期约 90°，吻合）❌ |
| 重启后第二轮（方案 A 验证） | `(0.00001, -0.000003)`, yaw ≈ **-0.004°** | `(0.0103, -0.1601)`, yaw ≈ **106.79°** | 与第一轮 init 差 **< 1e-6 m / < 0.001°**（远优于 0.05m / 2°）✅ |

**结论**：

1. 不重启 Gazebo 时，第二轮 init 位姿与上一轮末帧**完全相同**（逐位一致），且随后新发布的 AMCL 帧 yaw 从 108.43° 起算（98.57° → 85.18°），**并未回到 0°** → 证明 `setInitialPose(0,0,0)` 未能重置 AMCL，其粒子滤波状态跨 run 延续。**漂移根因确认。**
2. 重启 Gazebo 后，init 位姿回到 `(0,0,0)`、yaw≈0°，与第一轮差异 < 1e-6 m / < 0.001° → **方案 A 有效。**
3. 补充观测（记录不修）：三次 run 的**末点** yaw 均为 106°~108°，而末点指令为 `1.571 rad = 90°`，存在 **约 17°~18° 的系统性末点朝向偏差**。可能来源：`yaw_goal_tolerance`（Nav2 默认 0.25 rad ≈ 14°）+ AMCL 末次发布滞后（AMCL 仅在运动时发布，末次消息可能早于最终位姿稳定）。本卡未采集 TF 真值（`tf2_echo` 未执行），故不下定论，列入后续核查项。

**采集局限**：本次未采集 `tf2_echo map base_footprint` 物理真值，末点位姿均来自 `/amcl_pose`（AMCL 估计值）。另外 `/amcl_pose` 的 QoS 为 transient_local，新订阅者会先收到上一轮最后一条消息，故「第二轮首帧」不一定是新发布——本结论依据的是**随后新发布帧的 yaw 走向**，而非首帧。

### 12.5 巡逻点数量唯一结论

**当前实际巡逻点数量 = 10**，`total_goals` 语义 = 10。

三处历史数字差异来源：

| 出处 | 数字 | 来源说明 |
|:---|:---:|:---|
| 交接文档 2.3 节（旧） | 8个 | 2026-10-20「删除原点巡逻点」**之前**的旧值 |
| 交接文档 六、索引（旧） | 7个 | 删除原点巡逻点**之后**的旧值 |
| T-P1-01 回传 | 9点 | 2026-11-01 新增「回到原点朝北」「-4,-2 朝南」两点后的值 |

**当前 10 点的来源**：在 9 点基础上，于「第8点 `4.0,-3.0,-2.356`」与「第9点 `0.0,0.0,1.571`」之间新增过渡点 `2.0,-3.0,3.1416`（yaw = 初始角 0° + 180°）。

**核对依据**：`partol_config.yaml` 实有 10 组 `[x,y,yaw]`；`autopartol.launch.py` **不覆盖、不追加** `target_point`（仅传参文件路径）；全仓仅此一个 `partol_config.yaml`。

### 12.6 遗留目录处置

`baseline_results/`（2026-10-23 生成，9 个空 bag + 1 行全 0 CSV + 半成品脚本）已归档至 `archive/baseline_results_20261023/`，**不删除**，保留作 T-P1-02 批量脚本的目录结构参考。

### 12.7 T-P1-01 巡逻结果落盘：产出与 12 列表头来源（2026-11-04 补更）

| 项 | 结论 |
|:---|:---|
| 卡号 | T-P1-01（2026-11-01 完成） |
| 代码落点 | `partol_node.py` 的 `append_run_record()` |
| 参数名 | `csv_log_path`，默认 `~/ros2_ws/experiment_logs/patrol_runs.csv` |
| 产出文件 | `experiment_logs/patrol_runs.csv` |
| 写入时机 | 每轮巡逻结束（`while` 循环内、失败 `break` 之前） |
| 写失败行为 | 仅 `warn`，不中断巡逻主流程 |
| 表头 | 12 列，字段语义以 **12.1 节为准**，本节不重复表头 |

**12 列表头来源**：原 11 列 + `rejected` 插入第 9 位（`canceled` 之后）→ 12 列。字段顺序在代码 `header` 列表与 12.1 节文本中同源，**后续增删字段必须两处同步**。

**实际数据（2026-11-04 只读核对）**：表头 12 列正确；数据 6 个物理行，其中第 4 行粘连 2 条 run（见 12.8 遗留风险 2），实为 **7 条 run 记录**；`total_goals=9` 4 条（9 点旧口径）、`=10` 3 条（10 点现行口径）。

### 12.8 T-P1-01-FIX 收口结论索引（2026-11-04 补更）

| 项 | 结论 |
|:---|:---|
| 卡号 | T-P1-01-FIX |
| 问题 | 表头 11→12 列未同步，新数据行整体右移一列，`total_time_s` 读成 0、`max_rounds` 读成 252.5 |
| 处置 | 原文件备份 → 主文件重写为 12 列 → 历史 2 行补 `rejected=0` → 第 3 行（本就 12 列）原样保留 |
| 备份文件 | `experiment_logs/patrol_runs_v1_11cols_backup.csv` |
| 遗留风险 1 | 写表头条件仅判「文件不存在或大小为 0」，**不校验列数** → 再次增删字段会静默重演错列且无告警 |
| 遗留风险 2 | 数据文件第 4 行行尾缺换行，`completed` 与下一条 `run_id` 粘连成一行（2026-11-04 只读核对发现）；**已在 T-P1-02A 修复**（备份 `patrol_runs_pre_tp102a_backup.csv`，拆行后 7→8 行，`all12=True`） |
| 详情 | `BUGLOG.md`「2026-11-01 CSV 表头 11→12 列未同步导致列错位」 |

### 12.9 T-P1-01-PUSH 提交与推送方式（2026-11-04 补更）

| 项 | 值 |
|:---|:---|
| 卡号 | T-P1-01-PUSH |
| 提交 hash | `4cf679e` |
| 提交信息 | `feat: 巡逻实验指标落盘与AMCL漂移收口` |
| 分支 | `master` |
| 远端 | `origin` |
| 推送执行位置 | **主机共享文件夹**（虚拟机内 `git push` 异常，未在 VM 内完成） |
| VM 内 `origin/master` | `f44c7ac`（本地缓存的远端跟踪引用，**不代表 GitHub 实际状态**） |
| 待确认 | GitHub 上是否已存在 `4cf679e`；需在 VM 执行 `git fetch origin` 后核对 `origin/master` |

**推送异常的根因与处置**详见 `BUGLOG.md`「2026-11-04 虚拟机内 git push 异常 → 主机共享文件夹推送」。

### 12.10 文档同步约定（2026-11-04 新增，长期有效）

**硬要求**：

1. **同卡更新**：每张任务卡完成后，在**同一张卡内**更新文档，不分卡补、不攒批补、不留到下一卡。
2. **回传必须列位置**：回传需写明文档更新位置（文件 + 章节号）；**无文档影响时必须写明理由**，不得省略。

**配套要求**：

3. **文档更新是卡内必做项**：与代码改动同等对待，不是"有空再写"。
4. **缺口只列不扩**：发现历史缺口先列清单交评审决策，不自行扩写范围（本卡 P0 缺口即按此处理）。
5. **禁止伪造**：只写已发生事实与证据位置；未采集数据留「待确认」，不估算填充、不写"测试全过"式自述。
6. **只写结论**：文档写结论、决策、证据位置，不贴完整代码、完整日志、整篇文件。

### 12.11 T-P1-02A 单次端到端实验脚本与真值末点（2026-11-05）

**脚本**：`scripts/run_one_experiment.sh`，一条命令完成 重启 Gazebo → 等就绪 → 跑一轮 → 落 CSV → 采真值末点 → 关仿真。

```bash
cd ~/ros2_ws && ./scripts/run_one_experiment.sh
# 可选环境变量覆盖：READY_TIMEOUT(默认60) / ACTION_TIMEOUT(120) / PATROL_TIMEOUT(900) / READY_TOPICS
```

| 步骤 | 动作 | 失败退出码 |
|:---|:---|:---:|
| S1 | 清理残留（`nav2_bringup`/`nav2_container`/`gzserver`/`gzclient` + `/dev/shm/gz*`、`/dev/shm/rmw*`） | — |
| S2 | 起 `gazebo_test.launch.py` + `nav2_bringup`（`my_map.yaml` + `nav2_params_hybrid.yaml`） | 2 |
| S3 | 等 `/scan` `/odom` `/cmd_vel` + action `navigate_to_pose` | 4 |
| S4 | 起 `capture_truth_pose.py --watch`（先于巡逻，缓存 `/amcl_pose`）→ 起 `autopartol.launch.py` | 5 |
| S5 | 轮询 CSV 行数 +1 判定本轮完成 | 6 |
| S6 | `capture_truth_pose.py --finalize` 采真值 + AMCL 末点 | 7 |
| S7 | `trap` 清理并退出 | 0 |

失败日志：`experiment_logs/run_one_<时间戳>/fail.log`，格式 `[FAIL] step=S3 reason=topic_missing:/xxx exit=4`。

**真值来源**：`/gazebo/model_states`（`gazebo_msgs/ModelStates`），按 `name[]` 查 `basic_diff_drive_robot` 下标取同下标 `pose[]`，`yaw = 2*atan2(q.z, q.w)`。

- **前置条件**：`robocup_home.world` 的 `<world>` 内声明 `<plugin name="gazebo_ros_state" filename="libgazebo_ros_state.so">`，并设 `<namespace>/gazebo</namespace>` + `<update_rate>30.0</update_rate>`（本卡 +6 行）。
- **该插件是 `WorldPlugin`，只能写在 world SDF 内，不能用 `gzserver -s` 加载**（`-s` 会报 `incorrect plugin type`，见 BUGLOG 2026-11-05 条目）。
- **`namespace` 决定话题名**：插件源码内是相对名 `model_states`；设 `/gazebo` 后即 `/gazebo/model_states`，不设则为 `/model_states`。采集脚本**两条都订阅**，避免命名假设失效。
- 坐标可直接对齐：spawn 点 `(0,0)` 即建图 `map` 原点。
- **副作用**：`gazebo.sh` / `slam.sh` 共用同一 world，启动后同样会多发布 `/gazebo/model_states`、`/gazebo/link_states` 及 4 个 entity_state service；无行为改变。

**AMCL 末点采集方式（决策 2-A）**：脚本在巡逻启动**前**即以 `--watch` 常驻订阅 `/amcl_pose`，每秒原子写 `pose_cache.json`；`--finalize` 时读取缓存。

> 原因：`/amcl_pose` 为 volatile QoS 且 AMCL 在静止后不再重算（受 `update_min_d`/`update_min_a` 抑制），**巡逻结束后才订阅会永久挂死**。

**存储（决策 1：旁路文件，主表零变更）**：`experiment_logs/truth_last_pose.csv`，7 列 `run_id,gt_x,gt_y,gt_yaw,amcl_x,amcl_y,amcl_yaw`；`run_id` 取主表最后一条，保证同轮对齐。**`patrol_runs.csv` 12 列表头不变**，旧行完全兼容。

**用途**：定性 12.4 记录的末点 yaw 17~18° 偏差——真值≈90° 而 AMCL≈106° ⇒ AMCL 估计问题；两者均≈106° ⇒ 机器人确实未转到位（`yaw_goal_tolerance`=0.25rad≈14°）；真值≈106° 而 AMCL≈90° ⇒ AMCL 与真值脱节。

**实测对照（2026-11-05 共 4 轮，真值 vs AMCL，位置单位 m / 角度单位 rad）**

| run_id | 成功/总 | 耗时 s | 真值末点 | AMCL 末点 | 位置差 | 有效性 |
|:---|:---:|:---:|:---|:---|:---:|:---|
| 20261105_153829_r1 | 10/10 | 225.1 | (-0.007,-0.16,1.73) | (0.037,-0.139,1.885) | 0.05 | **valid** |
| 20261105_154240_r1 | 8/10 | 392.6 | (3.875,-1.373,-4.845→归一化1.438) | (1.818,-2.335,-2.872) | 2.27 | **invalid** |
| 20261105_165259_r1 | 10/10 | 227.7 | (0.018,-0.14,1.702) | (0.055,-0.131,1.892) | 0.038 | **valid** |
| 20261105_220630_r1 | 7/10 | 566.5 | (-3.281,3.181,-0.34) | (1.95,-1.692,-0.371) | 7.15 | **invalid** |

**run1 结论（12.4 的 17~18° 偏差首次拆分）**

- 指令 yaw 90.0°；真值 99.1°（+9.1°，0.159 rad）；AMCL 108.0°（+18.0°，0.314 rad）
- 机器人确实只转到 99.1°，且 0.159 rad < `yaw_goal_tolerance` 0.25 rad ⇒ Nav2 合法判定到达，解释了为何系统性停在 90°~104° 区间
- AMCL 在此之上又多估约 8.9° ⇒ **偏差两源各半**
- 位置差仅 0.05 m ⇒ `map` 与 world 帧基本对齐，排除坐标系帧偏差

**run2 标 invalid 的原因（单 run 内 AMCL 发散，非重启失败、非坐标系问题）**

- wp0~wp6 各到达点与指令点偏差 ≤0.16 m，轨迹正常
- wp6→wp7 途中 1 秒内 `剩余距离` 由 0.337 反跳到 1.816（**+1.48 m 定位跳变**）
- `nav2.log` 两次报 `Starting point in lethal space!` ⇒ AMCL 将机器人估入障碍格，规划器拒绝出解
- wp7(4,-3,-2.356) 与 wp9(0,0,1.571) 各重试 2 次后耗尽 ⇒ 成功数 8/10
- 末点真值↔AMCL 差 2.27 m ⇒ 该轮末点不可用于 yaw 统计
- **待办**：AMCL 发散排查另开卡，本卡不改 AMCL 参数

**run3（165259）结论**：10/10、227.7s，真值 97.5° / AMCL 108.4°（差 10.9°），位置差 0.038 m ⇒ 与 run1 一致，**AMCL 系统性多估 9~11°** 得到第二例佐证，末点有效。

**run4（220630）标 invalid 的原因——单 run 内 AMCL 发散，本次可复现**

- 成功 7/10、耗时 566.5s；末点真值↔AMCL 差 **7.15 m**
- `pose_trace.csv` 逐秒采样（590 行，t=1~590s）给出偏差曲线：

| t (s) | 真值 | AMCL | \|差\| |
|:---:|:---|:---|:---:|
| 31 | (3.39, 2.00) | (3.26, 1.86) | 0.19 |
| 91 | (-4.10, 2.99) | (-4.07, 2.91) | 0.08 |
| 211 | (0.04,-1.40) | (-0.17,-1.30) | 0.23 |
| 236 | (4.21,-3.25) | (3.68,-3.04) | 0.58 |
| 261 | (4.42,-3.39) | (2.28,-2.28) | 2.41 |
| **341** | (4.17,-3.10) | **(-3.82, 2.86)** | **9.97** |
| 421 | (-2.57, 3.67) | (2.33,-2.27) | 7.69 |
| 571 | (-3.36, 3.13) | (2.53,-1.54) | 7.52 |

- **关键事件**：t=340s 单步（1 s 内）AMCL 由 `(3.839,-3.022)` 跳到 `(-3.817,2.860)`，位移 **9.97 m**；此后 250 s 内**未回正**，偏差持续 3~8 m
- 全轮 587 个有效采样中 **325 个（55%）\|差\|>1 m** ⇒ 不是短暂抖动，是**持续性定位错误**
- 跳变点相对真值近似**点对称**（真值 x≈4.1、y≈-3.1 → AMCL x≈-3.8、y≈+2.9），指向地图对称/激光特征退化导致的**全局重定位错解**（属假设，需另卡验证）
- `nav2.log` 报 `Starting point in lethal space!` ⇒ AMCL 把机器人估进障碍格，规划器拒绝出解 ⇒ 3 个点重试耗尽
- **措辞说明**：本轮**本次可复现**（154240 与 220630 两轮均出现 >1 m 的定位跳变），非"偶发"；因仅 2 次样本，发生概率需 T-P1-02B 批量观察
- **待办**：AMCL 发散排查另开卡，本卡不改 AMCL 参数（`min_particles`、`alpha1~4` 等一律不动）

**yaw 归一化**：`yaw_from_quat()` 增加 `atan2(sin,cos)` 归一化到 [-π,π]（+2 行）。四元数双覆盖（`q` 与 `-q` 等价）使原始公式可落在 (-2π,2π]，run2 曾输出 -4.845（等价 1.438），与 AMCL 不可比；归一化后同帧可比。

**采样轨迹**：`--watch` 每次采样除写 `pose_cache.json` 外，另追加一行到同目录 `pose_trace.csv`（7 列 `t_sec,gt_x,gt_y,gt_yaw,amcl_x,amcl_y,amcl_yaw`），用于偏差随时间曲线分析。**不改 `run_one_experiment.sh`**，路径由 `--json` 自动派生。

**world 改动登记（必须留档，否则基线不可复现）**：`robocup_home.world` 的 `<world>` 开头新增 `gazebo_ros_state` 插件块（+6 行），并修复文件末尾换行符。**物理参数、模型、光照、地图几何、`<gui>` 均未改动**；唯一影响是启动后多发布 `/gazebo/model_states`、`/gazebo/link_states` 及 4 个 entity_state service。该 world 被 `gazebo.sh`、`slam.sh`、`run_one_experiment.sh` 共用，故三者均受此影响。

**踩坑**：

1. `gazebo_test.launch.py` 未声明 `headless` 参数，但 `gazebo.sh` 传入 `headless:=true`，属历史遗留，本卡不改。
2. 末点采集**必须在关 Gazebo 之前**（S6 在 S7 前），否则话题消失、真值永久丢失。
3. 就绪等待失败属 S3，**此时巡逻尚未启动，不产生任何 CSV 行**，故用它做失败注入（`READY_TOPICS="/scan /nonexistent_topic"` + `READY_TIMEOUT=5`）零数据污染。
4. 判定"本轮完成"用 **CSV 行数 +1**，不用 `ros2 launch` 进程退出——`autopartol.launch.py` 含 speech/vision 两个常驻节点，launch 进程不会随巡逻结束退出。
5. **`install/` 是普通拷贝，不是软链**：改 `src/` 后必须 `colcon build` 才生效，否则运行的仍是旧副本（表现为"改了代码但行为没变"）。脚本 S2 已加硬校验：检查 install 内 world 是否含 `gazebo_ros_state`、`partol_node.py` 是否含 `need_nl`，缺失即 `exit 2` 报 `install_stale`。
6. **`set -u` 与 ROS `setup.bash` 冲突**：`install/setup.bash` L11 裸引用 `$COLCON_TRACE`，在 `set -u` 下触发 unbound variable 并**直接终止脚本**（表现为此前所有 run 都 `EXIT=1` 且停在 S2 之前）。脚本已用 `set +u` / `set -u` 包裹 source。
7. **`gazebo_ros_state` 是 `WorldPlugin`**，`gzserver -s libgazebo_ros_state.so` 会被 Gazebo 拒绝（`incorrect plugin type`）且**不报错退出**，只在日志留 `[Err]`；必须写进 world SDF。

**CSV 换行守卫**：`append_run_record()` 写前用 `rb` 读末字节，非 `\n` 则先补 `\r\n`；`write_header` 判据改为 `has_content`。**12 列表头、`rejected` 独立、5 项等式、异常只 `warn` 均未改动**。

---

## 十三、2026-11-10 更新：`/odom` 数据源切换 WORLD → ENCODER 并复测通过

> 详细验证记录见 `docs/operations/VERIFY_ODOM_SOURCE.md`（第七、八节）。本节只做索引与待办。

### 13.1 本次完成内容

| 改动 | 文件 | 内容 |
|:---|:---|:---|
| 1 | `urdf/parts/plugins.urdf.xacro` | 差速插件块内新增 `<odometry_source>0</odometry_source>`（+21 行注释，说明双分支、必须写整数、静默回退坑） |
| 2 | `docs/operations/VERIFY_ODOM_SOURCE.md` | 新增第七节（ENCODER 切换复测结果）、第八节（待办） |
| 3 | `HANDOFF.md` | 本节 |

**未改动**：`gazebo.sh`、`slam.sh`、`run_one_experiment.sh`、`nav2_params_hybrid.yaml`、`ekf.yaml` 一律未动。

### 13.2 结论（可直接引用）

- `/odom` 已从 WORLD（世界真值）切换为 ENCODER（轮式积分），**A 组（纯 odom）正式成立**
- 实测位置误差：3.07 m 处 0.343 m（11.2%）、5.10 m 处 1.252 m（24.5%）；yaw 误差 +3.63° / +40.45°
- 误差**横向占 95%~98%** ⇒ 主因是航向多估（转弯时驱动轮空转），不是轮径标定
- 因此 IMU 修航向的 A/B 对比方向明确：A 组横向误差累积，B 组应压住

### 13.3 ⚠️ 对既有基线数据的影响（必须写进报告）

`nav2_params_hybrid.yaml` 中 AMCL 的 `odom_topic: /odom`。修复前 `/odom` 即真值，等于 **AMCL 一直在用完美里程计**，定位误差趋近 0。

**已有 16 个有效 bag 与批量实验的成功率、路径偏差等指标均属乐观上界，与新数据不可直接混用。** 这条本身可作为方法论材料：*仿真默认配置下里程计等价于真值，导致导航评估系统性偏乐观*。

### 13.4 待办记录

| 编号 | 待办 | 优先级 | 说明 |
|:---:|:---|:---:|:---|
| D-01 | **巡航时连续采样漂移曲线** | 🟡 | 每 0.5 s 采一次 `odom` vs `/gazebo/model_states` 写 CSV（`err_pos` / `err_yaw`），yaw 差用 `atan2(sin,cos)` 归一化。现有只有两个单点，无法判定线性/超线性 |
| D-02 | 查两轮之间是否重启仿真 | 🟢 零成本 | 翻 Nav2 终端历史找 `Spin` / `Backing Up` / `Clearing costmap`；出现即说明卡住空转 |
| D-03 | 纯直行 1 m 看 yaw 是否漂 | 🟡 | 只发 `linear.x`，不发角速度。直行也漂 = 左右轮不对称；不漂 = 确认转弯打滑 |
| D-04 | 同路径 1 m / 2 m / 3 m 三点取数 | 🟡 | 线性增长 = 累积漂移；基本恒定 = 坐标系偏移 |
| D-05 | 重启后车未动时取一次数 | 🟡 | 应接近 0；若起步即数十厘米，说明 odom 与 world 原点有偏移 |
| D-06 | AMCL `odom_topic` 是否改为 `/odometry/filtered` | 🟡 M3 决策 | 现状仍为 `/odom`；EKF 场景下 TF 发布者与 AMCL 输入源不一致，需在 M3 验证后决定 |
| D-07 | IMU 协方差补噪声 | 🔴 必要 | `gazebo_ros_imu_sensor` 不填协方差默认全 0 ⇒ robot_localization 视为完美测量，滤波器退化。原「优化项」升级为「前置条件」 |

**建议顺序**：D-02（零成本）→ D-05（排坐标系）→ D-01（拿曲线）→ D-03 / D-04（分离误差来源）→ D-07 → D-06。

### 13.5 踩坑补充

**差速插件 `odometry_source` 的静默回退**：源码用 `Get<int>("odometry_source", WORLD)` 解析，**写成字符串 `ENCODER` 会解析失败**，`Get<int>` 失败时直接返回默认值 WORLD 且**不报任何错误**。表现为"改了、build 了、重启了，行为一点没变"。必须写整数 `0`（ENCODER）/ `1`（WORLD）。

**复测必须重启仿真**：URDF 在 spawn 时刻读入，只重启 Nav2 或只重开 RViz 无效。

---

## 十四、2026-11-12 更新：多轮巡航验证 + AMCL 恢复机制开启

> 详细记录见 `BUGLOG.md` 同日两条（多轮巡航验证、`recovery_alpha` 开启）。本节只做索引与待办。

### 14.1 本次改动

| 改动 | 文件 | 内容 |
|:---|:---|:---|
| 1 | `src/autopartol_robot/config/partol_config.yaml` | `max_rounds: 1` → `3` |
| 2 | `src/pkg03_gazebo_20260814/config/nav2_params_hybrid.yaml` | `recovery_alpha_fast/slow: 0.0/0.0` → `0.1/0.001`，并补 3 行机制注释 |

**未改动**：`partol_node.py`、`gazebo.sh`、`gazebo_ekf.sh`、`nav2_params.yaml`、`wpr_simulation2/config/nav2_params.yaml`、`ekf.yaml`。

### 14.2 验证结果

| 项 | 方法 | 结论 | 强度 |
|:---|:---|:---|:---|
| 多轮巡航 `max_rounds=3` | 改参数 + **肉眼观察**，单次启动连跑 3 轮 | 3 轮跑完，轮次交接过渡流畅，无重定位漂移/空转 | **观察级，n=1** |
| 恢复机制开启 | — | **未实跑**，配置已落盘 | 待验 |

**多轮结论的边界（措辞纪律）**：只能写「本次 3 轮、肉眼观察、过渡流畅」；不得写「多轮问题已解决」或「可无限连跑」。未采 CSV、未比对真值、未记录粒子云。

### 14.3 与 2026-11-01「第二轮漂移 ~90°」的关系（重要，勿混用）

| 场景 | 是否重设初始位姿 | 结果 |
|:---|:---|:---|
| 关掉巡逻节点 → **重新启动脚本**，Gazebo 不重启 | ✅ `init_robot_pose()` 再执行一次，覆盖为 yaw=0，车实际 yaw≈1.571 | 偏差 ~90° → 发散 |
| **一次启动**、`max_rounds=3` 同进程循环 | ❌ `init_robot_pose()` 在 `while` 外，只执行一次 | 无覆盖 → 无 90° 偏差 |

**12.3 节「每次 run 前必须重启 Gazebo」的流程约定依然有效**，其约束对象是「跨 run 重复启动巡逻脚本」，不适用于「同一次启动内的多轮」。

### 14.4 恢复机制参数语义（`recovery_alpha_*`）

```
w_slow += alpha_slow * (w_avg - w_slow)     # 长期平均观测质量
w_fast += alpha_fast * (w_avg - w_fast)     # 当前观测质量
w_diff  = max(0, 1 - w_fast / w_slow)       # 随机粒子注入概率
```

两值同时为 `0.0` ⇒ `w_slow`/`w_fast` 冻结、恒相等 ⇒ `w_diff ≡ 0` ⇒ **注入机制完全关闭**，粒子云收敛到错误位姿后无法自救。

### 14.5 待办记录

| 编号 | 待办 | 优先级 | 说明 |
|:---:|:---|:---:|:---|
| R1 | 故意给错 90° 初始位姿，看是否自救 | 🔴 | 恢复机制存在的直接判据 |
| R2 | 正常行驶是否过度发散 | 🟡 | 若粒子云频繁炸开，`alpha_fast` 下调至 0.05 |
| R3 | 角落旋转后是否仍被粒子云包围 | 🟡 | 若仍发生，根因不只在注入，需查 `update_min_a/d`(0.2/0.25) 与 `max_beams: 60` |
| R4 | 多轮数据级验证 | 🟡 | 采 CSV + 真值，看第 2/3 轮末点是否逐轮劣化（关联 D-01） |
| R5 | 同步 `nav2_params.yaml` 与 `wpr_simulation2` 副本 | 🟢 | 二者仍为 0.0/0.0，做 A/B 对照时会混入变量 |
| R6 | 修正 `partol_config.yaml` 第 17 行注释措辞 | 🟢 | 现注释易被误读为「`max_rounds>1` 也会漂」 |

### 14.6 AMCL 参数单变量对照实验（2026-11-22 ~ 11-23，四组）

**归档**：[docs/experiments/AMCL_PARAM_SWEEP_ARCHIVE.md](file:///home/robot/ros2_ws/docs/experiments/AMCL_PARAM_SWEEP_ARCHIVE.md)（含失败组，原样保留）

执行入口 `scripts/run_amcl_test.sh`：一条命令拉起 Gazebo + Nav2 + RViz2 + 真实巡航链路 `ros2 launch autopartol_robot autopartol.launch.py`，后台每 0.5 s 采真值（`/gazebo/model_states`）与 `/amcl_pose`，收尾自动算指标。分析用 `scripts/amcl_compare.py`（更新时刻口径并排）与 `scripts/odom_spin_probe.py`（原地转向比值探针）。

| 组 | 参数 | 结果 | 判定 |
|:---:|:---|:---|:---|
| A | z .5/.5, α .2 | 10/10，207.7 s，末点 0.033 m | 有效基线 |
| B | z .9/.1, α .2 | 10/10，198.1 s，末点 0.033 m | **有效** |
| C | z .9/.1, α .05 | **8/10，462.0 s，末点 6.892 m** | **失败，已回滚** |
| D | z .9/.1, α .2（回滚复现） | 10/10，199.5 s，末点 **0.009 m**，BT 失败 7（均自恢复） | **B 复现，n=2 定稿** |

**⚠️ 关键前提（2026-11-23 事后发现）**：A~D 四组运行时 `wheel_separation` 为 **0.24，而实际轮距 0.36**（`model.xacro` 轮组 ±0.12 + `wheel.urdf.xacro` 轮心再外移 ±0.06 ⇒ 轮心 ±0.18）。后果：**物理转向速率只有指令的 2/3、`/odom` 航向被放大 1.5 倍**。两者叠加使 `/odom` 恰好与指令一致，形成「里程计很准」的假象。**A~D 四组的 yaw 类指标全部失效，不得作为 AMCL 精度上报**；位置类指标不受影响（轮径自洽）。已修（`plugins.urdf.xacro` 改 0.36 + `colcon build`），探针实测 `odom/真值` 1.5 → **1.055**、`真值/指令` 0.667 → **0.955**，残余 5.5% 为真实轮胎滑移。

**关键方法论（务必沿用）**：`/amcl_pose` 受 `update_min_d: 0.25` / `update_min_a: 0.2 rad` 门限约束，呈阶梯状，与 0.5 s 连续真值之间必然存在「车在走、估计不动」的空档。**`summary.txt` 里的「最大位置误差」是阶梯假象，不能作为精度上报**（A 组 0.433 m 与 B 组 0.474 m 均为此类）。正确口径为「只在 `/amcl_pose` 数值变化的时刻统计」，或改采 TF `map->base_footprint`。A 组该口径下：位置误差 mean 0.102 / max 0.336。

**C 组负结果**：`alpha1~alpha4 0.05` 使航向散开仅 2.6°，远小于旋转期的航向偏差，粒子云覆盖不到真值 → 粒子耗尽 → 118.6 s 位姿瞬移 3.6 m 切换错误假设。**`alpha` 不能按「每步标准差匹配」定标**（该误差是系统性比例偏差、随距离线性累积，非白噪声）。事后确认那 40° 偏差的真实来源正是 `wheel_separation` 错误，C 组结论因此更成立。

**末点航向超调**：A +20.5°、B +17.0°、D +18.1°，而 `yaw_goal_tolerance` 仅 8.6°。D 组末点 AMCL 与真值 yaw 完全一致（误差 0.00°），证明**超调不是 AMCL 估计错，而是车真的多转了**。机理为「判到位瞬间估计滞后 → 判成功 → 停车后补正」，量级 ≈ `update_min_a` 门限 + 容差。修正 `sep` 后物理转速变快，超调可能涨到 22~25°，需在新基线重测。

### 14.7 下一步（**2026-11-27 更正**：E 组已于 11-24 完成，原表全部过时）

> ⚠️ 本节原写于 **2026-11-23**（当时 E 组尚未开跑），11-24 跑完后未回头更新，导致 `HANDOFF_SESSION_20261126` 交接时误判「E1 未开跑」。以下状态以归档第七节（S1~S14）为准：[docs/experiments/AMCL_PARAM_SWEEP_ARCHIVE.md](file:///home/robot/ros2_ws/docs/experiments/AMCL_PARAM_SWEEP_ARCHIVE.md)

| 编号 | 待办 | 状态 | 说明 |
|:---:|:---|:---:|:---|
| E1 | 重建基线 E 组：`sep 0.36` + `z .9/.1` + `alpha 0.2` | ✅ **已完成** | `20261124_203938_sep036_baseline`：10/10、200.4 s、末点 0.033 m、零 Spin/BackUp；yaml md5 与 D 组完全相同，构成天然单变量对照（归档 8.1/8.2） |
| E2 | 单独测 `update_min_a: 0.2 → 0.05` | 🔴 待跑 | E/F/G 三组均未动此值。**但优先序见 E8**：形态未确认前不宜先动 |
| E3 | `max_vel_theta: 1.0` 降到 0.67 | ✅ **无需下调** | 修正 `sep` 后超调未失控：E +7.7°、F +8.5°、G +7.9~17.9°，均落在 `yaw_goal_tolerance 8.6°` 附近，**未出现预期的 22~25°** |
| E4 | `laser_likelihood_max_dist: 2.0` 与 `sigma_hit: 0.05` 匹配性核查 | 🟢 未动 | 仍为不匹配项 |
| E5 | `recovery_alpha_fast/slow` 实跑验证（原 14.5 R1） | ✅ **已完成** | G 组三跑（0/0 两跑 + 0.1/0.001 一跑）均 10/10、无可测差异；**定稿 0.0/0.0**，理由是去掉随机源、提高批量可重复性，非精度更优 |
| E6 | 同步 `worlds/one.world` 的 `wheel_separation` | 🟢 无需处理 | 该 world 无引用，死副本 |
| **E7**（原表遗漏） | **`transform_tolerance: 1.0 → 0.1`** | 🔴 **优先** | 当前值为 nav2 常规值的 10 倍，是「雷达扫描与地图不重合」的**第一嫌疑**，见归档 8.5 / S11 |
| **E8**（原表遗漏） | 确认视觉现象形态（扇形旋转／整体平移／整体弹跳） | 🔴 **阻塞** | 形态决定先动 `update_min_a` 还是 `transform_tolerance`，见归档 8.5 / S14。**这是 E2/E7 的前置** |

### 14.8 踩坑补充

**`params_file` 路径决定是否需 build**：`gazebo.sh` 传的是 `src/` 下绝对路径，改 yaml 即生效；而 `autopartol.launch.py` 用 `get_package_share_directory()` 读 `install/` 副本，改 `partol_config.yaml` **必须 `colcon build`**（除非曾用 `--symlink-install`）。同一次改动里两个文件，生效方式不同。

---

## 十五、2026-11-27 更新：许可统一 + 实验脚本实跑修复 + 单轮冒烟通过

### 15.1 许可统一为 Apache-2.0

| 包 | 改动 |
|:---|:---|
| `src/pkg03_gazebo_20260814` | `package.xml` `<license>MIT</license>` → `Apache-2.0`，目录内 `LICENSE`（原 MIT 全文）替换为根 `LICENSE` 的 Apache-2.0 全文 |
| `src/autopartol_interfaces` | 同上 |

**为什么要连 `LICENSE` 文件一起换**：只改 `package.xml` 会造成「声明说 Apache、同目录文件说 MIT」的新矛盾。

**有意保留不动的三处**（不是遗漏）：

| 位置 | 现状 | 理由 |
|:---|:---|:---|
| `src/pkg02_backup_20260811/package.xml` | `MIT` | 学习备份包，README 标「待定」 |
| `src/pkg01_backup_20260808_py/package.xml` | `TODO: License declaration` | 同上，脚手架默认值，非错误声明 |
| `docs/archive/` 内提及 MIT 的历史记录 | 原样 | 归档件按约定不改写 |
| `rplidar_ros`(BSD) / `wpr_simulation2`(GPLv3) | 原样 | 第三方包，已在根 `NOTICE` 声明 |

### 15.2 文档断链修复

文件搬进子目录后引用未跟随，共修 8 处：`HANDOFF.md` 3 处、`BUGLOG.md` 2 处、`docs/operations/VERIFY_ODOM_SOURCE.md` 1 处、`docs/experiments/AMCL_PARAM_SWEEP_ARCHIVE.md` 2 处。全部为 `docs/VERIFY_ODOM_SOURCE.md` → `docs/operations/`、`docs/AMCL_PARAM_SWEEP_ARCHIVE.md` → `docs/experiments/`。**`docs/archive/` 下的失效引用按约定不动。**

### 15.3 ⚠️ 实验脚本三处实跑修复（`scripts/run_one_experiment.sh`）

**背景**：`setsid` 收摊那套改动是从宿主机侧过期快照整文件 `cp` 进主仓库的，**只做过 `bash -n` 语法检查，从未在本环境实跑**。首次冒烟连挂两轮，暴露两处「路径/判据假设错误」——这类错误 `bash -n` 查不出来。

| # | 症状 | 根因 | 修法 |
|:---:|:---|:---|:---|
| 1 | `fail S2 install_stale:newline_guard_missing` | `INST_NODE` 写死非 symlink 安装路径 `install/autopartol_robot/lib/python3.10/site-packages/autopartol_robot/partol_node.py`；本工作空间是 **`--symlink-install`**，`install/` 里只有 `autopartol-robot.egg-link` 指向 `build/`，无实体文件 | 改为按运行时真实导入路径解析（`python3 -c "import autopartol_robot..."`），取不到再兜底 `src/`，并打印 `partol_node source:` 便于事后核对 |
| 2 | `fail S2 stale_ros_graph:scan_or_amcl_present` | 判据是「话题出现在 `ros2 topic list` 就 fail」。但 **ROS 2 只要有订阅者，话题就会出现在图里**；`capture_truth_pose.py` 第 62 行订阅 `/amcl_pose`，于是 `Publisher count: 0 / Subscription count: 1` 也触发误报 | 新增 `topic_has_publisher()`，改判 `ros2 topic info` 的 `Publisher count > 0`；`wait_topics_gone` 同步改用该判据（原写法会让每轮收尾白等满 20 s） |
| 3 | 语义不符 | `fail` 文案仍写 `scan_or_amcl_present` | 改为 `scan_or_amcl_published`，与实际判据一致 |

**为什么保留 `topics_present`**：`wait_for_topic` 仍在用（等话题就绪时订阅者存在也算就绪，该语义正确），两个函数并存、各管一件事。

**为什么不用 `ros2 daemon stop` 来清幻影话题**：初判是 daemon 缓存，实测 `Publisher count: 0` 但 `Subscription count: 1`，证明是**真实订阅者**不是缓存。且 `wait_topics_gone` 只有 20 s 预算、0.5 s 轮询，用 `--no-daemon` 会每轮都超时，等于废掉收尾验证。

### 15.4 单轮冒烟结果（当前唯一可信参照点）

| 项 | 值 |
|:---|:---|
| 目录 | `experiment_logs/run_one_20261127_201559` |
| `run_id` | `20261127_201631_r1` |
| 结果 | **10/10，failed=0，199.9 s，completed** |
| 末点真值 | `gt (0.053, -0.129, 1.710)` |
| 末点 AMCL | `amcl (0.052, -0.138, 1.779)` |
| 末点位置误差 | **约 0.014 m** |
| 末点航向误差 | **约 3.95°** |
| `巡逻结束，全程统计` | 计数 1（**判据真实触发，非超时收尾**） |
| `fail.log` | 不存在 |
| 残留进程 | 无（`setsid` + 进程组杀生效） |

**`setsid` 收摊逻辑至此实测验证完毕。** 另有一个非噪声观察：本轮 **199.9 s**，而历史同任务（11-05~11-07）为 **219.9 ~ 228.1 s**，快约 10%。差异远超耗时噪声（±1.6%），大概率是 `wheel_separation` 修正后 `/odom` 航向不再被放大 1.5 倍、机器人少做无效纠偏的收益。

### 15.5 「基线重建」已撤回，改为单轮逐步改进

**撤回理由（技术性的，不是省事）**：`run_batch_experiments.sh` 的 `count_valid` / `count_completed` 读 `baseline_summary.csv` **全量**，不区分年代。实测该文件 `valid=7`、`completed=16`，而 `MAX_RUNS=15`：

```bash
if [ "$COMPLETED_NOW" -ge "$MAX_RUNS" ]; then   # 16 >= 15
  log "[STOP] max_runs_reached（前置）"
  exit 0                                        # 直接退出，一轮都不跑
```

**即历史数据会让批跑在启动 Gazebo 之前就停机。** 且用户已明确：**不需要统计意义上的基线，只要「一步一步比之前更好」**。

| | 基线重建（已撤回） | 逐步改进（现行） |
|:---|:---|:---|
| 目的 | N=10 统计均值/方差 | 改一个参数，看是否比上一版好 |
| 轮数 | 10 轮 valid | **1 轮** |
| 是否依赖批脚本 | 是 | **否，直接跑单轮** |
| 判据 | `baseline_summary.csv` | `patrol_runs.csv` 末两行对比 |

**归档、移目录、重建 `baseline_summary.csv` 这一整套动作全部取消，无需执行。**

### 15.6 ⚠️ 指标可信度：单轮能判什么、不能判什么

用历史同配置 4 轮 valid 实测的波动（**这是选判据的唯一依据**）：

| 指标 | 4 轮实测 | 均值 | 标准差 | 相对波动 | 单轮可用性 |
|:---|:---|:---|:---|:---|:---|
| `total_time_s` | 227.4 / 220.4 / 219.9 / 221.8 | 222.4 | **3.5 s** | **1.6%** | ✅ 差 >10 s 可信 |
| `yaw_err_deg` | 11.06 / 2.86 / 6.88 / 10.43 | 7.8 | **3.8°** | 49% | 🟡 差 >5° 可信 |
| `pos_err_m` | 0.0755 / 0.1269 / 0.0262 / 0.0308 | 0.065 | **0.047 m** | **72%** | ❌ **单轮不可信** |

**`pos_err` 同配置能差 4.8 倍（0.026 → 0.127）**。因此：

- **成功率**：10/10 vs 9/10 本身就是强信号，无需统计。
- **耗时**：差 >10 s（约 5%）才算真变化。
- **`pos_err`**：差到 >0.05 m 才当回事，或连跑 2 轮取中位数。**「把 pos_err 从 0.05 优化到 0.02」这类目标，单轮测不出来——那是噪声，不是参数效果。**

**单轮验证的天花板**：在当前噪声水平下，单轮只能确认「没变差」和「快慢」，确认不了「更准」。

### 15.7 遗留项（下次接手先看这里）

| 项 | 状态 | 说明 |
|:---|:---:|:---|
| `scripts/run_one_experiment.sh` 三处修复 | ✅ 已入库 | 见 15.3；当前工作区改动属第十六节 |
| `docs/experiments/AMCL_PARAM_SWEEP_ARCHIVE.md` 两处路径 | ✅ 已入库 | 见 15.2；`6a51916` 提交 |
| 无人值守闭环加固（轮数透传 / 图片核验 / 收摊复检 / 残留恢复） | ✅ **已实跑验证** | 见第十六节；2026-11-28 连跑 4 次，收摊复检 3 clean / 1 假阳性已修 |
| `teardown` 每轮报「20s 内未消失，转 KILL」 | 🟢 不影响正确性 | `TERM` 后 `gzserver` 响应慢，最终靠 `KILL` 收干净（`leftover_exit=1` 已证）。代价是**每轮白等 20 s**，单轮跑可忽略，批量跑再优化 |
| 宿主机侧快照 `/mnt/hgfs/VM_share/ros2_ws` | ✅ 已替换 | 原为落后分支，已整体替换为 `1fb1e5b` 干净副本；**本轮未提交改动不在快照内** |
| `experiment_logs/.batch_run.lock` | 🟢 无需处理 | 11-07 遗留空锁文件；脚本用 `flock -n` 建议锁，进程退出即释放，**不要手工删** |
| `baseline_summary.csv` / `patrol_runs.csv` 历史数据 | 🟢 仅作参照 | 早于 11-10 `/odom` 切换、11-23 `sep` 修正、11-22~23 AMCL 定参，**不可作为当前口径基线** |

---

## 十六、2026-11-28 更新：无人值守闭环加固 + 收摊假阳性修复 + RViz 启动顺序回退

> 详细归档见 `docs/experiments/UNATTENDED_CLOSURE_20261128.md`。本节只留结论与下次接手要用的数字。

### 16.1 本次改动总览（全部落在 `scripts/run_one_experiment.sh`）

| # | 改动 | 解决的故障 | 触发证据 |
|:---:|:---|:---|:---|
| 1 | RViz2 由「S3 就绪检查之后」前移到「Nav2 启动之后、S3 之前」 | 巡逻永久卡在 `waitUntilNav2Active()`，表现为「半天不开始巡航」 | 实跑日志连续刷 `timestamp earlier than all the data in the transform cache` |
| 2 | `wait_topics_gone` 首轮超时不再直接判脏，改为「停 daemon → 预热 → 二次确认」 | 偶发 `[FAIL] step=S7 reason=teardown_dirty:topics_published exit=8` | `run_one_20261128_004741` 报脏；紧接着 `run_one_20261128_005242` 开跑时同一判据报「无发布者」 |
| 3 | `teardown_verify` 进程组未清空时跳过话题判定；首轮预算 5 s → 12 s | 同一根因被写成两个脏项（`proc_group_alive,topics_published`），误导成两个独立故障 | 同上 |
| 4 | `recover_stale` 话题等待 5 s → 12 s | 「连着跑第二次」在清理环节假失败 | 同上 |
| 5 | `max_rounds` 改为 launch 参数透传；`partol_node` 默认值 3 → 1 与 yaml 对齐 | yaml 写 1、代码默认 3 的纸面矛盾（15.7 遗留项） | 改轮数时改 yaml 生效、改代码无效 |
| 6 | 图片核验改用跑前/跑后快照差集，期望数取 CSV 末行 `succeeded` | 日志「图片保存成功」少打一条导致假阴性 | `call_async` 异步竞态：末张图 imwrite 与回调都在日志终句之后 |

### 16.2 「半天不开始巡航」的根因推导

rviz2 启动瞬间三件重活同时发生：编译 GLSL 着色器、上传 202×161 地图 swatch、填满 TF 缓存，CPU 出现明显峰值。该峰值若与 patrol 的 `init_robot_pose` 重叠（`waitUntilNav2Active()` 要连续查 TF 与 costmap），后果链条是：

1. scan/TF 消息积压 → 超过 TF 缓存 10 s 窗口；
2. costmap 整帧丢弃，日志刷 `timestamp earlier than all the data in the transform cache`；
3. `waitUntilNav2Active()` 永不返回 → 巡逻不开始。

**为什么选「前移」而不是「加长 TF 缓存」**：加长缓存要改 `nav2_params_hybrid.yaml` 的 `transform_tolerance`，那属于 14.7 里正在评估的 AMCL 参数，会让本轮实验混入第二个变量；前移只动启动顺序，不碰任何参数，代价为零。

**为什么前移后还要加 S4.5 预热探针**：只前移不等待，RViz 峰值可能刚好落在 patrol 启动那一刻。探针判据取 `rviz.log` 出现 `Trying to create a map`，该行说明地图 swatch 已上传、GLSL 编译与地图加载两个峰值已过。上限 15 s 的理由：实测从启动到该行约 2~6 s（含 GLSL 报错重试），15 s 留 2 倍余量；超时仍继续跑，因为「RViz 慢」不该阻断实验。

### 16.3 收摊复检假阳性的根因

`topic_has_publisher()` 读的是 `ros2 topic info`，即 **ros2 daemon 的图缓存**，不是实时 DDS 图。进程被 KILL 后，参与者要等租约到期才从缓存剔除，这段时间仍报 `Publisher count >= 1`。

反证（这是判定「缓存」而非「残留」的关键证据）：

| 时间 | 判据结果 |
|:---|:---|
| `run_one_20261128_004741` 收摊 | `DIRTY(topics_published)`，exit 8 |
| 约 30 s 后 `run_one_20261128_005242` 开跑（S2 同一判据） | 未报 `scan_or_amcl_published`，收摊复检 clean |

同一套环境在 30 s 内从「有发布者」变成「无发布者」，中间没有任何进程被重新拉起，只可能是缓存剔除。放大因素是采样窗口：每次 `ros2 topic info` 新起一个 CLI 进程约 1 s，每轮要查 `/scan` 与 `/amcl_pose` 两个话题，原 `wait_topics_gone 5` 实际只采到 2~3 个样本。

**修法**：首轮超时后 `ros2 daemon stop` 丢缓存 → 预热一次 `ros2 topic list` 让新 daemon 建完首轮图 → 再轮询 8 s。只有重建图后仍报发布者才判脏。

**为什么不用 `--no-daemon`**：Humble 的 `ros2topic` 动词没有该选项。
**为什么不是把首轮从 5 s 加长到 20 s**：剔除时间取决于租约、不可控，加长只是把误报挪后，且每次收摊都白等。
**预热那一步不能省**：缺它时新 daemon 第一轮可能拿到空图，把真实发布者读成 0，等于用假阴性换假阳性。
**残余风险**：确认窗内图未建完可能漏判真实发布者，兜底在 S2 开跑前的 stale 检查（那时 daemon 已热）。

### 16.4 实跑验证（2026-11-28，4 次，同一配置）

| 目录 | `run_id` | 结果 | 图片 | CSV 行 | 收摊 | exit |
|:---|:---|:---|:---|:---|:---|:---:|
| `run_one_20261128_004741` | `20261128_004803_r1` | 10/10 | 10/10 | 39→40 | ❌ `DIRTY(topics_published)` | **8** |
| `run_one_20261128_005242` | `20261128_005304_r1` | 10/10 | 10/10 | 40→41 | ✅ clean | 0 |
| `run_one_20261128_011930` | `20261128_011953_r1` | 10/10 | 10/10 | 41→42 | ✅ clean（走 KILL 慢路径） | 0 |
| `run_one_20261128_012432` | `20261128_012503_r1` | 10/10 | 10/10 | 42→43 | ✅ clean（走 KILL 慢路径） | 0 |

**修后两次连跑均 `exit 0`，且是「连着跑第二次」**（前一次的收摊结果未人工干预），15.7 的「可重复执行」项成立。

**新出现的固定现象（不是故障）**：修后前两次都打出 `teardown: TERM 后 20s + daemon 重建确认仍报发布者，转 KILL`。说明 `TERM` 对 `gzserver` 确实不生效、必须靠 `KILL`，与 15.7 原有记录一致；但判定前多花约 10 s（2 s 停 daemon + 8 s 确认窗）。

**2026-11-28 10:29~10:42 又连跑 3 次（复测，样本扩到 7）**：`102949` / `103411` / `103842`，均 10/10、图片 10/10、`exit 0`、收摊 clean。其中 **`102949` 走快路径（TERM 生效，未打「转 KILL」）**，后两次走 KILL 慢路径。**快慢路径混合出现说明 TERM 响应不稳定，但两种路径都 `clean`，正确性不受影响**；慢路径每次多约 10 s，会放大耗时噪声。详见 `docs/experiments/UNATTENDED_CLOSURE_20261128.md` 7.5。

### 16.5 噪声底：后续参数改动的评判线

**指标定义**（末点，取自 `truth_last_pose.csv` 同一时刻的 gt 与 amcl）：

1. `pos_err_m = sqrt((amcl_x - gt_x)^2 + (amcl_y - gt_y)^2)`，单位 m；
2. `yaw_err_deg = |wrap(gt_yaw - amcl_yaw)|`，单位 °，wrap 到 (-180, 180]；
3. `total_time_s`（仿真钟，CSV 第 10 列）与墙钟时长 `end_time - start_time`；
4. `succeeded / total_goals`。

**当前配置 7 个同配置样本（11-28，RViz 常开，`max_rounds=1`）**：

| 指标 | 7 次实测 | 均值 | 样本标准差 | 极差 |
|:---|:---|:---|:---|:---|
| `pos_err_m` | 0.0581 / 0.0190 / 0.0242 / 0.0256 / 0.0375 / 0.0149 / 0.0171 | **0.0280** | **0.0152** | **0.0432** |
| `yaw_err_deg` | 1.72 / 0.52 / 9.63 / 1.95 / 4.47 / 1.89 / 0.06 | **2.89** | **3.29** | **9.57** |
| `total_time_s` | 214.7 / 203.4 / 235.2 / 197.7 / 207.6 / 206.0 / 197.1 | **208.8** | **13.1** | **38.1** |
| 墙钟时长 s | 222 / 212 / 241 / 204 / 211 / 208 / 199 | 213.9 | 13.9 | 42.0 |
| `RTF` | 0.967 / 0.959 / 0.976 / 0.969 / 0.984 / 0.990 / 0.990 | 0.977 | 0.012 | 0.031 |

**判据（用极差，不用标准差）**：n=7 时样本标准差仍受离群点牵引，取**极差**作保守阈值：

1. `pos_err_m` 差异 ≤ **0.043 m** → 判为噪声，不可分辨；
2. `yaw_err_deg` 差异 ≤ **9.6°** → 判为噪声，不可分辨；
3. `total_time_s` 差异 ≤ **38 s** → 判为噪声，不可分辨。

**7 样本 vs 4 样本：极差几乎不变（0.0391→0.0432 m、9.11→9.57°、37.5→38.1 s）**，说明 4 样本的估计已足够稳，扩样没有推翻原阈值。但极差**被单个离群点主导**：`011953` 一次同时贡献了最大的 `yaw_err`（9.63°）与最大的 `total_time_s`（235.2 s）；`004803` 贡献了最大的 `pos_err`（0.0581 m）。剔除 `011953` 后 yaw 极差降到 4.41°、耗时极差降到 17.6 s。故上面的阈值是「含最坏情况」的保守值，**不是典型波动**；判断某个改动是否有效时，若新值落在离群点一侧，要补一次复跑再下结论。

**RTF 分时段差异（新发现）**：凌晨 4 次（00:48~01:25）RTF 为 0.959~0.976，上午 3 次（10:29~10:42）为 0.984~0.990。同一配置、同一脚本，RTF 差 0.02~0.03，说明**仿真速度受机器背景负载影响，不受脚本控制**。这解释了为什么耗时噪声比 15.6 的 11-07 数据（标准差 3.5 s）大 4 倍。

**与 15.6 的对比（重要，不可混用）**：15.6 的 4 个样本（11-07 采集）`total_time_s` 标准差仅 3.5 s、极差 7.5 s；本次为 16.6 s / 37.5 s，**放大 4.7 倍**。差异来源未定论（RViz 常开、11-10 `/odom` 切换、11-23 `sep` 修正都可能贡献），**不能直接断言是 RViz 造成的**，需 `--no-rviz` A/B 才能定论。

**直接后果**：15.4 依赖的「快约 10%（约 20 s）」判断在当前配置下**已失效**——10 s 的改进小于 38 s 的极差，测不出来。要恢复耗时判别能力，必须先降噪（关 RViz 或改用心跳/CPU 时间等不随负载漂移的量），否则参数扫描在耗时维度上全是噪声。

### 16.6 遗留项

| 项 | 状态 | 说明 |
|:---|:---:|:---|
| `--no-rviz` A/B 验证 RViz 对耗时噪声的贡献 | ⚠️ 待做 | 用新行 `(end_time - start_time) - total_time_s` 判定；若差额回落到 0~1 s（RTF≈1）即确认 |
| `20261128_011953_r1` 双指标异常 | ⚠️ 待查 | 耗时 235.2 s 与航向误差 9.63° 同时偏大，是 7 样本里的唯一离群点，需看该轮 costmap/AMCL 日志 |
| 收摊 TERM 快慢路径不稳定 | 🟢 不影响正确性 | `102949` 快路径、`103411`/`103842` 慢路径，两种都 clean；慢路径多约 10 s，会放大耗时噪声 |
| 历史 `truth_last_pose.csv` 重复与无效行 | 🟢 仅作参照 | 45 条 CSV 仅 31 个唯一 run_id 有真值（缺 14）；`20261107_172028_r1` 重复 3 次；`20261119_205138_r1` 两条 gt 为初始位姿非末点 |
| `note` 字段不能当质量标记 | 🟢 已知 | `nav_fail_action=skip` 下恒为 `completed`，那两条 0/10 的灾难行也标 completed |
| 无人值守不能自动处置外部遗留实例 | 🟢 设计如此 | `RECOVER=0` 默认只报告不清理（清理会 `rm -rf /dev/shm/gz*`，影响全机）；需人工确认后走 `--clean-only` |
