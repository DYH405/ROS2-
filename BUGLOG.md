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