# ROS2 仿真导航项目 — 交接文档

> 更新时间：2026-10-17
> 当前阶段：第一阶段（理想仿真基线）— 打磨中

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
- 巡逻节点：`autopartol_robot` — 8个巡逻点 + 超时机制
- 联合启动：`autopartol.launch.py`（巡逻+语音+图像）

> ⚠️ **IMU 状态说明**：当前 IMU（`/imu/data`）仅作为 Gazebo 仿真传感器存在，**未接入 `robot_localization` / EKF 融合链路**。定位仍依赖 AMCL（基于 `/scan` + `/odom`），不属于多传感器融合定位。如需融合，需额外引入 `robot_localization` 节点并配置 EKF/UKF。

### 2.4 rosbag 录制 — `record_30s.sh`（已优化）

- 路径：`src/pkg03_gazebo_20260814/scripts/record_30s.sh`
- 录制话题：`/scan /tf /tf_static /cmd_vel /odom /plan /amcl_pose`（7个）
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

### 4.1 第一阶段补齐（高优先级）

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 🔴 | bag_analyzer 支持 /scan | 读取 LaserScan，绘制雷达扫描图 |
| 🔴 | bag_analyzer 支持 /plan | 读取 Path，绘制规划路线 |
| 🔴 | 规划路线 vs 实际轨迹对比图 | 同一画布叠加 /plan 和 /odom |
| 🔴 | bag_analyzer 统计报告 | 路径长度、平均速度、耗时、位置误差 |
| 🔴 | 录制新 bag（7话题完整数据） | 当前 bag_01 只有 /odom，需完整数据验证 |

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
| 🟡 | bag_analyzer 支持 /cmd_vel | 读取 Twist，绘制速度曲线 |
| 🟢 | bag_analyzer 自动检测话题 | 根据 bag 中实际话题自动选择分析 |
| 🟢 | bag_analyzer 命令行参数 | `--odom` `--scan` `--plan` 参数控制 |

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
| partol_config.yaml | `src/autopartol_robot/config/partol_config.yaml` | 7个巡逻点配置 |
| autopartol.launch.py | `src/autopartol_robot/launch/autopartol.launch.py` | 巡逻联合启动 |
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
- 远端：`https://github.com/DYH405/ROS2-.git`
- 提交数：5
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

### 9.3 待完成：plan 分组拼接 → reference path

多点巡逻导航中，136 条 `/plan` 属于不同导航目标，不能只取最后一条。需要：

1. **`group_plans_by_goal(plan_data, threshold=0.5)`**：按终点坐标分组（同一目标的重规划终点不变，终点距离 > 0.5m 视为新目标）
2. **`build_reference_path(goal_groups)`**：每组取最后一条 plan，拼接为完整 reference path
3. **`plot_comparison(odom_data, ref_points, bag_path)`**：reference path vs 实际轨迹，同一画布叠加，保存为 `comparison.png`
4. **统计报告**：路径长度、平均速度、耗时、位置误差

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

原 4.1 节高优先级任务进度：

| 任务 | 状态 |
|:---|:---:|
| bag_analyzer 支持 /plan | ✅ 已完成 |
| bag_analyzer 支持 /scan | 🔴 待完成 |
| 规划路线 vs 实际轨迹对比图 | 🔴 待完成（需先完成 plan 分组拼接） |
| bag_analyzer 统计报告 | 🔴 待完成 |
| 录制新 bag（7话题完整数据） | ✅ 已完成（bag_20261017_234254） |