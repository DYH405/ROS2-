# ROS2 仿真导航项目 — 交接文档

> 更新时间：2026-10-10
> 当前阶段：第一阶段（理想仿真基线）— 初步完成

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
- 巡逻节点：`autopartol_robot` — 7个巡逻点 + 超时机制
- 联合启动：`autopartol.launch.py`（巡逻+语音+图像）

### 2.4 rosbag 录制 — `record_30s.sh`

- 路径：`src/pkg03_gazebo_20260814/scripts/record_30s.sh`
- 录制话题：`/scan /tf /tf_static /cmd_vel /odom /plan`
- 特性：30秒定时录制、INT 信号安全退出
- 历史数据：`bag_data/` 下有 17 组旧录制（仅含 /odom）

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
- 远端：已推送至 GitHub

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

---

## 四、待打磨任务

### slam.sh 优化

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 中 | 封装话题检查函数 | `check_topic()` — 检查话题是否存在 |
| 中 | 封装数据验证函数 | `check_topic_hz()` — 验证话题数据频率 |
| 低 | 增加重试机制 | 话题检查失败时重试 N 次 |
| 低 | 增加超时机制 | 等待话题出现设超时，避免无限等待 |

### bag_analyzer.py 扩展

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 高 | 支持 /scan 激光雷达数据 | 读取 LaserScan，绘制雷达扫描图 |
| 高 | 支持 /plan 导航规划路径 | 读取 Path，绘制规划路线 |
| 高 | 规划路线 vs 实际轨迹对比图 | 同一画布叠加 /plan 和 /odom |
| 中 | 支持 /cmd_vel 速度分析 | 读取 Twist，绘制速度曲线 |
| 中 | 自动检测话题类型 | 根据 bag 中实际话题自动选择分析 |
| 低 | 生成分析报告 | 文本摘要：总时长、路径长度、平均速度 |
| 低 | 命令行选择分析项 | `--odom` `--scan` `--plan` 参数控制 |

### 其他

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 中 | gazebo.sh 也封装话题检查 | 和 slam.sh 保持一致的代码风格 |
| 低 | 录制新 bag（6 话题完整数据） | 当前 bag_01 只有 /odom，需完整数据验证 |

---

## 五、关键文件索引

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

## 六、环境依赖

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

## 七、Git 状态

- 分支：master
- 远端：`https://github.com/DYH405/ROS2-.git`
- 提交数：2
- 旧 .git 备份：`.git_broken_backup/`（已在 .gitignore 中排除）