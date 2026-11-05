# ROS2 仿真导航项目 — 交接文档

> 更新时间：2026-11-05
> 当前阶段：P1 收口（可复现基线）

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
- Nav2 参数：`src/pkg03_gazebo_20260814/config/nav2_params.yaml`
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

> ⚠️ **IMU 状态说明**：当前 IMU（`/imu`）仅作为 Gazebo 仿真传感器存在，**未接入 `robot_localization` / EKF 融合链路**。定位仍依赖 AMCL（基于 `/scan` + `/odom`），不属于多传感器融合定位。如需融合，需额外引入 `robot_localization` 节点并配置 EKF/UKF。

### 2.4 rosbag 录制 — `record_30s.sh`（已优化）

- 路径：`src/pkg03_gazebo_20260814/scripts/record_30s.sh`
- 录制话题：`/scan /tf /tf_static /cmd_vel /odom /plan /amcl_pose /imu /clock`（9个）
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
- 当前 HEAD：`4cf679e`（feat: 巡逻实验指标落盘与AMCL漂移收口）
- VM 内 origin/master：`f44c7ac`（本地缓存的远端跟踪引用，**未随主机侧推送更新**，见 12.9）
- 提交数：**21**（2026-11-04 `git rev-list --count HEAD` 实测）；旧记录「5」为 2026-10-22 重建时的口径，已过旧
- 旧 .git 备份：`.git_broken_backup/`（已在 .gitignore 中排除）

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

**实测对照（2026-11-05 两轮，真值 vs AMCL，位置单位 m / 角度单位 rad）**

| run_id | 成功/总 | 耗时 s | 真值末点 | AMCL 末点 | 位置差 | 有效性 |
|:---|:---:|:---:|:---|:---|:---:|:---|
| 20261105_153829_r1 | 10/10 | 225.1 | (-0.007,-0.16,1.73) | (0.037,-0.139,1.885) | 0.05 | **valid** |
| 20261105_154240_r1 | 8/10 | 392.6 | (3.875,-1.373,-4.845→归一化1.438) | (1.818,-2.335,-2.872) | 2.27 | **invalid** |

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