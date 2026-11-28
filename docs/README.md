# docs 索引

| 文件 | 一句话 | 什么时候该看 |
|:---|:---|:---|
| [operations/VERIFY_ODOM_SOURCE.md](operations/VERIFY_ODOM_SOURCE.md) | 验证 `/odom` 究竟是直取世界位姿还是编码器积分，并记录切 ENCODER 后的复测结论 | 里程计跳变、TF 冲突、怀疑 `/odom` 不是带误差的积分数据时 |
| [experiments/AMCL_PARAM_SWEEP_ARCHIVE.md](experiments/AMCL_PARAM_SWEEP_ARCHIVE.md) | AMCL 七组单变量对照（A~G）归档，含 C 组失败实验与 G 组异常跑；A~D 组 yaw 指标因 `wheel_separation` 0.24→0.36 修正而作废，E~G 组为修正后同源数据、yaw 恢复有效 | 调 amcl 参数、想复用已扫过的取值、核对 `wheel_separation` 相关结论时 |
| [experiments/UNATTENDED_CLOSURE_20261128.md](experiments/UNATTENDED_CLOSURE_20261128.md) | 无人值守闭环加固归档：RViz 启动前移修「半天不巡航」、收摊 daemon 缓存假阳性修复、图片快照差集核验，附当前配置噪声底（`pos_err` 极差 0.039 m / 耗时极差 37.5 s） | 改任何参数前先查噪声底判断阈值；排查 `exit 8`、图片数不符、巡航不启动时 |
| [logs/日志.md](logs/日志.md) | 按日期记录的任务卡完成情况、当日结论与遗留问题 | 回溯某日做了什么、某任务卡为何未通过时 |
| [archive/ROADMAP_FAULT_DETECTION_ARCHIVE.md](archive/ROADMAP_FAULT_DETECTION_ARCHIVE.md) | 原 P2–P5（故障检测与分级恢复）规划的归档，不驱动当前主线 | 想找回早期 P2–P5 规划、确认某方向为何搁置时 |
| [archive/handoff/HANDOFF_SESSION_20261123.md](archive/handoff/HANDOFF_SESSION_20261123.md) | 一次性交接，仅服务 2026-11-22 ~ 11-23：M3 EKF 前置验证全过程、`wheel_separation` 0.24→0.36 修正、A~D 组 yaw 指标作废说明 | 想复原那两天为何改参数、E~G 组基线从何而来时 |
| [archive/handoff/HANDOFF_SESSION_20261126.md](archive/handoff/HANDOFF_SESSION_20261126.md) | 一次性交接，仅服务 2026-11-25 ~ 11-26：仓库整理六阶段、docs 目录收拢、`HANDOFF.md` 现状段校正；记录 7 个 `package.xml` 已改未提交与 8 项待决策 | 想复原这轮为何只改文档、`package.xml` 改到哪一步、下一步先跑什么时 |