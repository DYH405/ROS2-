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

**证据**（2026-11-04 只读采集）：

```
origin  `https://github.com/DYH405/ROS2-.git` (fetch)
origin  `https://github.com/DYH405/ROS2-.git` (push)
```

- 远端 URL **字面含反引号**，与 HANDOFF「坑11：Git 远端 URL 反引号」同类
- VM 内 HEAD = `4cf679e`，VM 内 `origin/master` = `f44c7ac`（**落后 1 条**，因推送在主机侧执行，VM 的远端跟踪引用未更新）

**根因**（推断，待验证）：remote URL 中残留反引号，git 将反引号视为 URL 的一部分 → 连接/认证失败。坑11 的 `git remote set-url origin "https://..."` 用的是**双引号**，而双引号不转义反引号，故若原字符串已含反引号则修不掉。

**处置**：本卡只写文档，**不修 remote**（改配置需另开卡）。推送改由主机共享文件夹执行；VM 内推送能力待修复，修复前每次提交后需在主机侧推送。

**教训**：

1. 设置 URL 用**单引号** `git remote set-url origin 'https://...'`，或直接 `git config --edit` 手改；设置后**必须 `git remote -v` 回读确认无反引号**。
2. 双引号防不住反引号，坑11 的教训记录不完整。
3. VM 与主机共享同一仓库时，两边 remote 配置与 remote-tracking 引用需**分别核对**；一处推送不代表另一处状态同步。
4. `git status` 不显示「ahead」不等于已推送——本环境中 VM 侧引用长期滞后，**"推送成功"必须以主机侧或 `git fetch` 后回读为准**。