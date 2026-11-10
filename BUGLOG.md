# BUGLOG - 问题记录

## 2026-10-26 while循环被意外删除导致导航瞬间返回unknown

**现象**：所有7个巡逻点在2毫秒内全部返回unknown，机器人没有移动

**根因**：`nav_to_pose()` 中 `while not self.isTaskComplete()` 循环被意外删除，`goToPose()` 发送目标后立刻调 `getResult()`，目标还没执行完就返回unknown

**修改前**（partol_node.py 第85-90行）：
```python
elapsed = 0.0
last_log_time = 0.0
log_interval = 1.0
# self.cancelTask()
# 结果处理-统计信息
result = self.getResult()          # 直接取结果，目标还没执行
```

**修改后**（partol_node.py 第85-102行）：
```python
elapsed = 0.0
last_log_time = 0.0
log_interval = 1.0
while not self.isTaskComplete():   # 恢复循环，等待导航完成
    rclpy.spin_once(self,timeout_sec=0.05)
    elapsed = (self.get_clock().now() - start_time).nanoseconds / 1e9
    if elapsed > timeout:
        self.cancelTask()
        is_timeout = True
        break
    feedback = self.getFeedback()
    if feedback is not None and elapsed - last_log_time >= log_interval:
        self.get_logger().info(f'剩余距离：{feedback.distance_remaining}')
        last_log_time = elapsed
# self.cancelTask()
# 结果处理-统计信息
result = self.getResult()
```

**修复项**：
- 恢复while循环：`goToPose()`只发送目标，必须循环等待`isTaskComplete()`才能取结果
- `timeout_sec=0.05`：顺手修复忙等问题（之前是0.0）

---

## 2026-10-26 use_sim_time作为Node()关键字参数导致launch报错

**现象**：`ros2 launch autopartol_robot autopartol.launch.py` 报错 `TypeError: Action.__init__() got an unexpected keyword argument 'use_sim_time'`

**根因**：`use_sim_time` 是ROS2节点的参数，不是 `launch_ros.actions.Node` 的关键字参数

**修改前**（autopartol.launch.py）：
```python
Node(
    parameters=[default_param_path],
    output="screen",
    use_sim_time=True,   # 错误：Node()没有这个参数
)
```

**修改后**：
```python
Node(
    parameters=[default_param_path, {'use_sim_time': True}],
    output="screen",
)
```

**修复项**：三个Node（partol_node、speaker_node、image_capture_node）的 `use_sim_time` 都从关键字参数移入 `parameters` 字典

---

## 2026-10-25 巡逻统计计数器跨轮累加，日志数字不可信（P0）

**现象**：`max_rounds > 1` 时，第2轮起日志打印 `成功14/7`、`成功21/7` 等错误数字

**根因**：`success_count`/`failed_count`/`timeout_count`/`canceled_count` 四个计数器在 `while` 循环外初始化（第189-192行），循环内无清零，导致跨轮累加。日志分母 `total_points` 是本轮点数（7），分子却是全程累计值

**修改前**（partol_node.py）：
```python
# while 外初始化（只执行一次）
success_count = 0
timeout_count = 0
canceled_count = 0
failed_count = 0

while rclpy.ok() and round_count < partol.max_rounds:
    # 循环内没有清零
    ...
    partol.get_logger().info(f'成功{success_count}/{total_points},')  # 累加值/本轮值
```

**修改后**（partol_node.py）：
```python
# while 外初始化（保留，作为全程累计起点）
success_count = 0
timeout_count = 0
canceled_count = 0
failed_count = 0
total_success = 0  # 全程累计
total_failed = 0
total_timeout = 0
total_canceled = 0

while rclpy.ok() and round_count < partol.max_rounds:
    # 每轮清零
    success_count = 0
    timeout_count = 0
    canceled_count = 0
    failed_count = 0
    ...
    # 每轮日志（现在是本轮真实值）
    partol.get_logger().info(f'成功{success_count}/{total_points},')
    # 累加到全程
    total_success += success_count
    total_failed += failed_count
    total_timeout += timeout_count
    total_canceled += canceled_count

# while 结束后打印全程汇总
partol.get_logger().info(f'巡逻结束，全程统计：成功{total_success}, 失败{total_failed}, 超时{total_timeout}, 取消{total_canceled}')
```

**修复项**：
- while 循环内每轮清零四个计数器，日志打印本轮真实值
- 新增四个全程累计变量（total_success/total_failed/total_timeout/total_canceled）
- while 循环结束后打印全程汇总日志

**注意**：当前 `max_rounds=1`（每轮重启 Gazebo），此 bug 不会触发。但代码逻辑本身有误，`max_rounds>1` 时必触发

---

## 2026-10-25 rclpy.shutdown() 与 destroy_node() 顺序反了（P2）

**现象**：`rclpy.shutdown()` 在 `destroy_node()` 之前执行，不符合 ROS2 官方推荐顺序

**根因**：`destroy_node()` 需要向 DDS 层注销话题、释放资源，依赖 rclpy 运行时。先 shutdown 再 destroy 可能导致资源释放不干净

**修改前**（partol_node.py）：
```python
rclpy.shutdown()
partol.destroy_node()
```

**修改后**（partol_node.py）：
```python
partol.destroy_node()
rclpy.shutdown()
```

**修复项**：交换两行顺序，符合 ROS2 官方推荐：先 destroy_node 再 shutdown

---

## 2026-10-25 巡逻目标点配置更新

**变更内容**（partol_config.yaml）：

| 编号 | 原坐标 | 新坐标 | 说明 |
|---|---|---|---|
| 5 | -4.0, -0.5, -2.356 | **4.0, -1.0, -0.785** | 改为东南方向 |
| 6 | 4.0, -2.5, -0.785 | **4.0, -3.0, -2.356** | 改为西南方向 |
| 新增5.5 | 无 | **-4.0, -2.0, -1.571** | 4-5之间新增，朝南 |
| 新增8 | 无 | **0.0, 0.0, 1.571** | 回到原点，朝北 |

更新后共 9 个目标点

---

## 2026-11-01 不重启 Gazebo 时第二轮 AMCL 重定位漂移（记录不修，改流程约定）

**现象**：第一轮巡逻结束后，只关闭巡逻节点脚本、Gazebo 保持运行，再执行一次巡逻。开始时 RViz 中小车定位四处漂移，持续重定位，一段时间后雷达边界才与地图边缘重合。漂移期间导航不可信。

**根因**：`init_robot_pose()` 无条件用 `initial_point` 给 AMCL 设初始位姿：

```python
self.initial_pose = self.get_parameter('initial_point').value   # [0.0, 0.0, 0.0]
init_pose = self.get_pose_by_xyyaw(..., self.initial_pose[2])   # yaw = 0.0（朝东）
self.setInitialPose(init_pose)
```

- 巡逻点表末点为 `[0.0, 0.0, 1.571]` → yaw = 1.571（朝北）
- 不重启 Gazebo 时机器人物理位姿保留上一轮终态（yaw ≈ 1.571）
- AMCL 被告知 yaw = 0 → **偏差约 90°**

AMCL 粒子云按错误初始假设撒开 → 与地图匹配失败 → 粒子发散 → RViz 四处漂移 → 随运动与观测累积逐步收敛。

**触发条件**：末点 yaw 与 `initial_point` yaw 不一致，且不重启 Gazebo。

**处置（方案 A，本卡不修代码）**：每次实验 run 前重启 Gazebo，机器人回到 yaw = 0，与 `initial_point` 一致。写入交接文档 12.3 节，并由 T-P1-02 批量脚本强制执行。

**未采用的方案**：
- 方案 B（末点改 yaw=0）：会削弱"回到原点朝北"的巡逻语义
- 方案 C（保留现状）：批量实验会污染全部 run

**不改的原因**：`init_robot_pose()` 的"无条件覆盖初始位姿"在单轮实验下是正确且必要的（保证每次 run 起点确定）；漂移的真正来源是"跨 run 复用同一仿真实例"，属于实验流程问题，不是代码问题。

**实测证据**：见交接文档 12.4 节（数值待真实 Gazebo 采集，不得估算填充）。

---

## 2026-11-01 CSV 表头 11→12 列未同步导致列错位（已处置）

**现象**：新增 `rejected` 字段后表头变 12 列，但已存在的 CSV 仍是 11 列表头，新数据行追加后整体错位一列。`total_time_s` 被读成 `0`，`max_rounds` 被读成 `252.5`：

```
20261101_175657_r1,...,9,9,0,0,0,0,252.5,1,completed
                                ↑ total_time_s 读到 0，max_rounds 读到 252.5
```

**根因**：`append_run_record()` 的写表头条件只判断「文件不存在 或 大小为 0」：

```python
write_header = not path.exists() or path.stat().st_size == 0
```

**它不校验列数**。只要表头已存在，字段增删后仍会闷头追加，静默错列，且无任何告警。

**处置**：
- 原文件备份为 `experiment_logs/patrol_runs_v1_11cols_backup.csv`
- 主文件重写为 12 列，历史两行补 `rejected=0`，第 3 行（本就 12 列）原样保留
- 交接文档 12.1 节固定 12 列表头与字段语义

**遗留风险（本卡不修，列入后续候选）**：再次增删字段时会重演。建议后续卡给 `append_run_record()` 加「列数不匹配则 warn 并拒绝写入」的防御。

---

## 2026-11-01 failed 计数口径拆分（变更记录）

**变更内容**：`failed_count` 不再包含 `timeout`/`canceled`/`rejected`，四类失败各自独立计数。

**原因**：原口径下 `failed` 是"所有失败之和"，与验收等式 `succeeded+failed+timeout+canceled == total_goals` 冲突（超时/取消会被重复计入）。拆分后五类互斥，等式恒成立：

```
succeeded + failed + timeout + canceled + rejected == total_goals
```

**配套变更**：
- CSV 表头新增 `rejected`（第 9 列，`canceled` 之后），共 12 列
- `nav_fail_action` 由 `stop` 改为 `skip`，保证每个点都会尝试、必落五分支之一，等式不会因中途停止而少项
- console 日志同步打印「拒绝{rejected_count}」

**注意**：`skip` 下 `partol_failed` 恒为 `False`，CSV 的 `note` 字段恒为 `completed`；单点失败不再中止本轮。

---

## 2026-11-01 巡逻点新增过渡点（9 → 10）

**变更内容**（partol_config.yaml）：在第 8 点与第 9 点之间插入过渡点。

| 索引 | 坐标 | 说明 |
|:---:|:---|:---|
| 7 | `4.0,-3.0,-2.356` | 原第8点（西南），不变 |
| **8** | **`2.0,-3.0,3.1416`** | **新增过渡点**，yaw = 初始角 0° + 180°（朝西） |
| 9 | `0.0,0.0,1.571` | 原第9点（原点朝北），不变 |

**影响**：巡逻点总数 9 → 10，`total_goals` 语义同步改为 10，验收等式右侧由 9 改为 10。

**注意**：yaw = 3.1416 恰好位于 [-π, π] 边界。HANDOFF 10.2.2 曾记录"yaw 超出 [-π,π] 导致粒子发散"，3.1416 未超出，但若后续观察到该点附近定位异常，可改用 `-3.1416`（等价朝向）。

---

## 2026-11-04 虚拟机内 git push 异常 → 主机共享文件夹推送

**现象**：在虚拟机 `~/ros2_ws` 执行 `git push` 失败，提交无法上传远端；改在主机（共享文件夹路径）执行推送后成功。本卡 T-P1-01-PUSH 的提交即由主机侧完成。

**证据**（2026-11-04 采集，2026-11-05 逐字节复核并更正）：

```
$ git remote -v
origin  `https://github.com/DYH405/ROS2-.git` (fetch)
origin  `https://github.com/DYH405/ROS2-.git` (push)

$ git config --get remote.origin.url | od -c
0000000   h   t   t   p   s   :   /   /   g   i   t   h   u   b   .   c
0000020   o   m   /   D   Y   H   4   0   5   /   R   O   S   2   -   .
0000040   g   i   t  \n

$ GIT_TERMINAL_PROMPT=0 timeout 20 git fetch origin ; echo "fetch_exit=$?"
fetch_exit=124
```

- **`git remote -v` 输出里的反引号是显示层假象**：`git config` 原始值与 `od -c` 逐字节核对均无反引号（结尾为 `R O S 2 - . g i t \n`），URL 本身干净
- `fetch_exit=124` = 20 秒内无任何响应被 `timeout` 强杀 → VM 内**无法与 GitHub 建立连接**
- VM 内 HEAD = `4cf679e`，VM 内 `origin/master` = `f44c7ac`（**落后 1 条**，因推送在主机侧执行，VM 的远端跟踪引用未更新）

**根因**（2026-11-05 更正）：**VM 侧网络不可达 GitHub（网络/DNS 层）**，与 remote URL 配置无关。原记录"URL 残留反引号导致认证失败"的结论**已被上述逐字节证据推翻**，作废。

**处置**：本卡只写文档，**不修 remote**（URL 本身正确，无可修之处）。推送改由主机共享文件夹执行；VM 内推送能力待排查网络后修复，修复前每次提交后需在主机侧推送。

**教训**：

1. **`git remote -v` 的显示可能误导判断**——确认 URL 是否被污染，必须用 `git config --get remote.origin.url | od -c` 逐字节回读，不能只看 `remote -v`。
2. 推送/拉取失败先做分层诊断：`GIT_TERMINAL_PROMPT=0 timeout 20 git fetch origin; echo $?` → **124/超时 = 网络层**，**128 = 认证或 URL 层**，不要跳步直接猜 URL。
3. VM 与主机共享同一仓库时，两边 remote 配置与 remote-tracking 引用需**分别核对**；一处推送不代表另一处状态同步。
4. `git status` 不显示「ahead」不等于已推送——本环境中 VM 侧引用长期滞后，**"推送成功"必须以主机侧或 `git fetch` 后回读为准**。

---

## 2026-11-05 CSV 数据行缺换行导致两条 run 粘连

**现象**：`experiment_logs/patrol_runs.csv` 第 4 个物理行出现 `...252.5,1,completed20261101_192218_r1,...`，即 `20261101_175657_r1` 的 `completed` 与下一条 `run_id` 粘连为一行。`wc -l` 得 7 行（表头 1 + 数据 6），但实际含 **7 条 run**，严格按行解析会丢一条记录并污染 `note` 字段。

**证据**：

```
$ wc -l experiment_logs/patrol_runs.csv
7
$ tail -c 40 experiment_logs/patrol_runs.csv | od -c
... 1 , c o m p l e t e d \r \n     ← 文件末行换行正常
```

- 粘连发生在**文件中间**，不在末尾；末尾 `\r\n` 完好，证明 `csv.writer` 的写入行为本身正确
- 修复前备份 `patrol_runs_pre_tp102a_backup.csv`（7 行）
- 修复后 `patrol_runs.csv` 8 行，`rows=8 all12=True`（表头 1 + 数据 7，全部 12 字段）

**根因**：缺换行来自 **T-P1-01-FIX 期间人工重写文件**（末行未落 `\n`），非 `append_run_record()` 的代码缺陷。

**处置**：① 备份后按 `completed` 与 `run_id` 边界拆行；② 给 `append_run_record()` 加**防御守卫**——写前用 `rb` 读末字节，非 `\n` 则先补 `\r\n`；`write_header` 判据改为 `has_content`。12 列表头、`rejected` 独立、5 项等式、异常只 `warn` 全部未动。

**教训**：

1. **`wc -l` 的行数不等于记录数**——文件被人工编辑后必须逐行验证字段数（`csv.reader` + `len(row)==12`），不能只看行数。
2. **写文件脚本要有幂等防御**：追加前检查末字节换行，代价 3 行代码，可避免整条记录被后续解析吞掉。
3. **人工改数据文件前必须备份并命名可追溯**（本次 `*_pre_tp102a_backup.csv`），否则出错无法回退。
4. 判定"本轮实验完成"若依赖 CSV 行数，粘连会直接导致**误判为未完成而超时**——这也是本卡优先修该缺陷的原因。

---

## 2026-11-05 `gzserver -s` 加载 `libgazebo_ros_state.so` 失败（插件类型不匹配）

**现象**：为获取 `/gazebo/model_states` 真值，在 `gazebo_test.launch.py` 的 `gzserver` 参数追加 `-s libgazebo_ros_state.so`。gzserver 正常启动、机器人正常 spawn，但 `/gazebo/model_states` 始终不出现。

**证据**：

```
[Err] [gazebo_shared.cc:46] System is attempting to load a plugin,
      but detected an incorrect plugin type. Plugin filename[libgazebo_ros_state.so].

$ nm -C -D /opt/ros/humble/lib/libgazebo_ros_state.so | grep gazebo::WorldPlugin
00000000000662e0 D typeinfo for gazebo::WorldPlugin
00000000000662d0 D typeinfo for gazebo::PluginT<gazebo::WorldPlugin>

$ strings -a /opt/ros/humble/lib/libgazebo_ros_state.so | grep -iE "model_states|link_states"
model_states
link_states
```

**根因**：`gazebo_ros_state` 是 **`WorldPlugin`**，而 `gzserver -s` 只能加载 **`SystemPlugin`**。类型不匹配 → Gazebo 拒绝加载，但**不致命、不退出**，只在日志留一条 `[Err]`，极易被忽略。

**处置**：撤销 `-s` 那行，改为在 `robocup_home.world` 的 `<world>` 内声明：

```xml
<plugin name="gazebo_ros_state" filename="libgazebo_ros_state.so">
  <ros><namespace>/gazebo</namespace></ros>
  <update_rate>30.0</update_rate>
</plugin>
```

**教训**：

1. **Gazebo 插件先查类型再选加载方式**：`nm -C -D <so> | grep WorldPlugin|SystemPlugin|ModelPlugin` 一条命令即可判定；`SystemPlugin` 走 `-s`，`WorldPlugin`/`ModelPlugin` 走 SDF 声明。
2. **`-s` 加载失败不致命、不报错退出**，只留 `[Err]`——排查"话题不存在"时必须先 `grep -i error` 启动日志，不能只看进程是否存活。
3. **`gazebo_ros_state` 的话题名是相对名**（源码内为 `model_states`/`link_states`），最终名字由 `<ros><namespace>` 决定：设 `/gazebo` → `/gazebo/model_states`，不设 → `/model_states`。**订阅方应同时兼容两种命名**，不要硬编码。
4. 改 `world` 会影响所有共用该 world 的启动脚本（本仓 `gazebo.sh`、`slam.sh`、批量脚本），改动前需评估对建图/巡逻基线的影响面。

---

## 2026-11-05 单 run 内 AMCL 发散（两轮复现：154240 差 2.27m / 220630 差 7.15m）

**现象**：两轮均出现 >1 m 的 AMCL 定位跳变，末点真值与 AMCL 严重不符，成功数下降、耗时翻倍。

| run_id | 成功/总 | 耗时 s | 末点真值 | 末点 AMCL | 位置差 |
|:---|:---:|:---:|:---|:---|:---:|
| 20261105_154240_r1 | 8/10 | 392.6 | (3.875,-1.373) | (1.818,-2.335) | 2.27 m |
| 20261105_220630_r1 | 7/10 | 566.5 | (-3.281,3.181) | (1.95,-1.692) | 7.15 m |

**证据**：

```
# 220630：pose_trace.csv 逐秒采样，t=340s 单步跳变 9.97m 且此后不回正
339.0,4.180,-3.092,-0.821,3.839,-3.022,-0.711
340.0,4.172,-3.098,-0.994,-3.817,2.860,2.221   ← 1 秒内位移 9.97 m
571.0,-3.360,3.130,-0.000,2.530,-1.540,-0.000  ← 250s 后仍偏 7.52 m
# 该轮 587 个有效采样中 325 个（55%）|gt-amcl|>1 m

# 154240：patrol.log wp6→wp7 途中剩余距离反向跳变
[1793864751.712] 剩余距离：0.33698388934135437
[1793864752.625] 剩余距离：1.8163375854492188   ← +1.48 m

# nav2.log：AMCL 把机器人估进障碍格，规划器拒绝出解
[1793887626.414] [planner_server]: GridBased: failed to create plan,
                 invalid use: Starting point in lethal space!
```

**根因**：**单 run 内 AMCL 定位跳变（本次可复现）**。正常阶段 `|gt-amcl|` 稳定在 0.08~0.25 m（220630 的 t=31~211 s、165259 全轮 mean 0.165 m / max 0.52 m），跳变发生后误差升至 2~10 m 且**长期不收敛**，导致规划器以"起点在致命格"拒绝出解、目标点重试耗尽。

220630 跳变点相对真值近似**点对称**（真值 ≈(4.1,-3.1) → AMCL ≈(-3.8,+2.9)），指向地图对称性/激光特征退化引发的**全局重定位错解**（属假设，待另卡验证）。

**排除项**：

| 假设 | 排除依据 |
|:---|:---|
| 重启失败 | `run_one_experiment.sh` S1 已 `pkill -9 gzserver/gzclient/nav2_container` + `rm -rf /dev/shm/gz* /dev/shm/rmw*`；各轮真值起点不同（153829≈(0,0)、154240≈(3.9,-1.4)、220630≈(-3.3,3.2)），证明确为独立新实例 |
| 真值坐标系问题 | `/gazebo/model_states` 为 Gazebo world 系；两轮正常段（153829 差 0.05 m、165259 差 0.038 m）证明帧对齐正常 |
| 全局漂移（缓慢累积） | 正常段偏差 ≤0.25 m 且不随时间增长；跳变是单步突变（1 s 内 9.97 m），非渐进 |
| yaw 公式缺陷 | yaw 归一化只影响角度输出范围，不影响位置；位置跳变在归一化前后同样存在 |

**处置**：154240、220630 末点标 **invalid**，不纳入 yaw 统计；本卡不改 AMCL 参数（`min_particles`、`alpha1~4` 等一律不动），发散排查另开卡。仅 2 次样本，发生概率需 T-P1-02B 批量观察（**不写"偶发"，也不写"已修复"**）。

**教训**：

1. **CSV 的 `succeeded` 统计不等于轨迹可信**——必须与真值交叉校验后才可用于统计，否则发散轮次会被当作正常样本。
2. **真值链路是判断"谁错"的唯一手段**：单看 AMCL 或单看 Nav2 日志都无法区分"机器人没走到"与"定位估错"。
3. **偏差曲线比末点更有效**：末点只给一个数，`pose_trace.csv` 逐秒采样才能定位跳变发生的时刻与幅度（220630 靠它锁定 t=340s、9.97 m）。
4. **"成功率高"与"定位正确"是两个独立指标**：165259 是 10/10 且 mean 偏差 0.165 m，才可作为基线；只看 10/10 会漏掉发散轮。

## 2026-11-07 批脚本重复执行导致两套实验并发（数据污染，已处置）

**现象**：同一批命令（`BATCH_ID=b1c`）被连续执行两次，两套批脚本同时运行，抢占同一个 Gazebo 实例。

**观察（记录事实，不下结论）**：

| 观察项 | 实测 |
|:---|:---|
| `batch_ledger.csv` | b1c 记 6 条流水，但只有 3 轮真实执行：seq=1 出现两次（251s / 286s），seq=3 出现两次（852s / 855s） |
| `baseline_summary.csv` | 同一 `run_id=20261107_172028_r1` 写出 3 行，分别指向 `171909` / `171938` / `172013` 三个目录 |
| 三目录 truth.log | 首行 run_id 全部相同（`20261107_172028_r1`），gt 末点完全相同（0.017,-0.155,1.729） |
| 三目录 amcl 末点 | 差异巨大：(1.734,0.830) / (2.355,1.107) / (0.009,-0.180) |
| 三目录采样行数 | 20 / 28 / 243（前两个采集进程起步极晚，很快被另一实例清理掉） |
| `patrol_runs.csv` | 新增 `172448_r1`（7.4s，0/10）、`172447_r1`（12.0s，0/10）两条瞬时全败行 |
| 批脚本 out 文件 | `batch_b1c_1.out`/`_2.out`/`_3.out` 只剩 3 个，两次执行的同名文件互相覆盖 |

**机制**：`capture_truth_pose.py` 的 `last_run_id()` 取 `patrol_runs.csv` **最后一行**作为本轮 run_id（[capture_truth_pose.py:L42-48](file:///home/robot/ros2_ws/scripts/capture_truth_pose.py#L42-L48)），并发时多个采集进程读到同一行，于是同一 run_id 落到多个目录；同时 `run_one_experiment.sh` 的 `cleanup()` 用 `pkill -9 -f partol_node` 按名字全局杀，会打掉另一实例正在跑的巡逻节点。

**处置（已修，均带注释）**：

| 编号 | 改动 | 位置 |
|:---|:---|:---|
| D9 | 批脚本加 `flock` 非阻塞单实例锁，第二实例立即 `[ABORT]` 退出 | [run_batch_experiments.sh](file:///home/robot/ros2_ws/scripts/run_batch_experiments.sh#L49-L63) |
| D8 | 汇总侧按 run_id 去重，保留 `pose_trace.csv` 采样最多的一条，其余标 `note=dup_of=<目录>` 只留痕不统计 | [summarize_baseline.py](file:///home/robot/ros2_ws/scripts/summarize_baseline.py#L441-L476) |
| D11 | `cleanup()` 分阶段：`PIDS` 空（S1 清残留）按名字全局杀；`PIDS` 非空（EXIT 收尾）只杀本轮子孙 | [run_one_experiment.sh](file:///home/robot/ros2_ws/scripts/run_one_experiment.sh#L29-L57) |
| P2 | 单轮输出文件名加启动时刻 `batch_${BATCH_ID}_${BATCH_RUN_TS}_${SEQ}.out`，避免覆盖 | [run_batch_experiments.sh](file:///home/robot/ros2_ws/scripts/run_batch_experiments.sh#L190-L191) |

**保留不删**：`patrol_runs.csv` 的 `172448_r1`、`172447_r1` 两条 0/10 畸形行原样保留（数据完整性）。这两条没有对应的 `run_one_*` 目录，故本就不会进入 `baseline_summary.csv`；`171909`、`171938` 两个目录的原始数据亦保留，仅在统计口径剔除。

**教训**：

1. **体检输出出现「gzserver + nav2_container + capture --watch + partol_node + speech_node」五件套同时在线，且 `--watch` 指向一个活跃目录，说明有一轮实验正在进行，不是残留**——此时绝不能启动新批次。
2. **按名字全局 `pkill` 是并发场景下的自毁操作**：只应杀本轮 PID 派生的子孙；全局清扫只适用于「本轮尚未启动任何节点」的阶段。
3. **run_id 不能靠「读别人表的最后一行」推导**：并发时会读到同一行，必须由本轮自身携带；当前仅在 D9 串行化后不再触发，属治标。

## 2026-11-07 AMCL 伪吸引子假设（M3 假设清单新增，待验证，未下结论）

**来源**：2026-11-07 评审要求，M3 假设清单新增条目。

**假设 H2**：AMCL 存在**伪吸引子**——激光观测与地图在若干位姿处形成局部最优，粒子云收敛到错误位姿后不再脱离；EKF 融合 IMU 航向先验能否抑制这种误收敛。

**验证前提（当前不具备）**：需先接入 `robot_localization`，把 IMU 角速度/航向进 EKF 链路。当前 IMU 未接入（见 HANDOFF 2.3），故 H2 属研究内容 3 范围，不在 P1 基线内展开。**本条只登记假设，不构成结论。**

**支撑事实（仅记录）**：

| 事实 | 数据 |
|:---|:---|
| 跳变后长期不回正 | `220630` 跳变 9.97m 后 217s 不回正，末点 7.149m；`203153` 跳变 8.014m 后 256s 不回正，末点 8.014m |
| 跳变落点贴近巡逻点 | `220630`(-3.817,2.860)→wp3 0.23m；`190212`(-3.745,2.918)→wp3 0.27m；`194611`(-4.283,2.699)→wp3 0.41m；`160101`(-4.454,3.106)→wp3 0.47m；`203153`(-4.510,3.166)→wp3 0.54m |
| 同落点不同恢复 | `220630` 与 `190212` 落点相距 0.09m，但越阈持续 217s vs 110s、末点 7.149m vs 0.272m（n=2，不下结论） |

**已排除的原因（批 1e 跳变率上升，2026-11-07 核查）**：

| 候选原因 | 排除依据 |
|:---|:---|
| 仿真场景与地图不一致 | `robocup_home.world` 的 diff **只新增 `gazebo_ros_state` 插件（+6 行），无任何几何/家具/障碍改动**；地图 `robocup_home_map`（2026-08-13）、`my_map`（2026-08-21）mtime 早于全部实验，且场景几何自建图后未变 |
| 巡逻逻辑被改 | `partol_node.py` 的 diff 只有 CSV 末行补 CRLF（+10 行），不涉及目标点序列与导航流程 |
| 并发抢占 | 批 1e 两次执行是**串行**（19:35 与 20:25），`flock` 锁未报 ABORT，`[PRE]` 无 `unexpected_file_change` |

**跳变率实测（只记事实）**：

| 区间 | truth 轮 | 含 `jump_gt_1m` | 比例 |
|:---|:---:|:---:|:---:|
| 批 1e 之前 | 10 | 4 | 40% |
| 批 1e（连续 5 轮） | 5 | 5 | **100%** |
| 累计 | 15 | 9 | 60% |

**同时观察**：批 1e 五轮的跳变时刻为 213 / 252 / 276 / 281 / 545 s，而 7 个 valid 轮的总耗时全部落在 220~230 s（mean 224.3 s、std 3.6 s）。跳变时刻与 valid 轮的结束时刻在时间上接近甚至重叠，**故「跳变率上升」与「批 1e 各轮实际运行更久」两件事无法从现有数据分离**，需专门设计对照实验才能区分，当前不做推断。

---

## 2026-11-08 M3 EKF 融合配置落地（改动 1-3），待验证清单 9 项

**状态**：代码已写入 `src/`，**未 build、未实跑**。批量实验仍在运行，`install/` 内仍是旧副本，运行中进程不受影响。

**落地内容**：

| 改动 | 文件 | 内容 |
|:---|:---|:---|
| 1 | `urdf/parts/plugins.urdf.xacro` | 宏签名加 `params="publish_odom_tf"`，L24 改为 `${publish_odom_tf}` |
| 2 | `urdf/model.xacro` | 新增 `xacro:arg publish_odom_tf` default=`true`，透传给宏 |
| 3 | `config/ekf.yaml` | 新建，robot_localization 融合配置 |

**默认值保持 `true`，`gazebo_test.launch.py` 不传该参数，基线解析结果与改动前逐字一致**（已用 `xacro urdf/model.xacro | grep publish_odom_tf` 待验，见下 V1）。

**与任务书原稿的两处偏离**：

| 项 | 任务书原稿 | 落地值 | 理由 |
|:---|:---|:---|:---|
| `use_sim_time` | 未声明 | `true` | EKF 定时器若不跟仿真时钟，`sensor_timeout: 0.1` 会把墙钟与仿真时间戳相减，导致判定全超时或永不超时，`frequency: 50.0` 失效 |
| `imu0_config` 的 `ax` | `true` | `false` | Gazebo 线性加速度是速度差分得来，抖动大且与 `/odom` 的 vx 高度相关，融合等于重复加权；协方差为 0 时抖动会被当作完美测量灌进速度估计。待 IMU 补噪声后再评估 |

另新增 `print_diagnostics: true`（只打印诊断表，不改融合结果），用于 V3/V5 取证。

**待验证清单（首次实跑时逐条查验，结论栏留空待填）**：

| 编号 | 待验证项 | 查验命令 | 判据 | 结论 |
|:---:|:---|:---|:---|:---|
| V1 | 默认参数未破坏基线 | `xacro urdf/model.xacro \| grep publish_odom_tf` | 输出 `true` | 待验 |
| V2 | 参数能透传到底 | `xacro urdf/model.xacro publish_odom_tf:=false \| grep publish_odom_tf` | 输出 `false` | 待验 |
| V3 | `/odom` twist 协方差是否全 0 | `ros2 topic echo --once /odom --field twist_covariance` | 对角有非零值 = 无雷；全 0.0 = 需 relay 重发带协方差的消息（插件未暴露参数，无法直接改） | 待验 |
| V4 | `/imu` 三组协方差是否全 0 | `ros2 topic echo --once /imu --field orientation_covariance`（另两组同理） | 全 0.0 = 需在 `imu.urdf.xacro` 的 `<sensor>` 内补 gaussian 噪声 | 待验 |
| V5 | EKF 参数是否真的加载 | `ros2 param get /ekf_filter_node frequency` | 返回 `50.0`；若为 `30.0` 说明 yaml 顶层 key 与 launch `name=` 不一致 | 待验 |
| V6 | `use_sim_time` 是否生效 | `ros2 param get /ekf_filter_node use_sim_time` | 返回 `True` | 待验 |
| V7 | TF 发布权是否真的交接 | **减法验证**：起 launch 但不启 `ekf_node`，`ros2 run tf2_ros tf2_echo odom base_footprint` | 该 TF **应完全不存在**（证明 `publish_odom_tf:=false` 生效）；再启 EKF 后 TF 回来 = EKF 接管成功 | 待验 |
| V8 | 融合输出频率是否 50Hz | `ros2 topic hz /odometry/filtered` | ≈50Hz；显著偏离说明仿真时钟未对齐或数据积压 | 待验 |
| V9 | yaw 是否锁死或阶梯抖动 | `ros2 topic echo /odometry/filtered --field pose.pose.orientation.z`（原地小幅转向对照） | 平滑跟随 = 正常；第一帧即固定不动或阶梯跳变 = 零协方差问题（关联 V3/V4） | 待验 |

**已知设计风险（不影响本次链路验证，但影响 M3 结论能否成立）**：

Gazebo 的 `/odom` 是**理想积分**——不打滑、无噪声、几乎不漂。这意味着「EKF 融合比纯里程计更准」在这套仿真里**天然缺少可对比的误差来源**。链路跑通 ≠ 论点成立。要做出可写入报告的对比，需额外设计：

- 对比组：A = 纯 `/odom`，B = `/odometry/filtered`
- 真值：`/gazebo/model_states` 的世界位姿作 ground truth
- 制造差异：给轮子加打滑/接触噪声，或给 `/odom` 人为注入噪声后再喂 EKF
- 指标：转向过程的 yaw 瞬时误差 + 长时间累积角误差，比终点位置误差更能体现"IMU 修航向"的价值

**另一条隐含假设需写入报告**：Gazebo IMU 的 yaw 是**世界系绝对朝向**，而真机 IMU 的 yaw 相对磁北。本配置 `world_frame: odom` 之所以成立，仅因为仿真中 odom 系原点与 world 原点重合、姿态始终对齐。换真机不可直接照搬。