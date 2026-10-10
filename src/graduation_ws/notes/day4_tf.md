# Day 4: TF树理解

## 今日目标
- 启动老师的仿真例程；
- 查看TF树；
- 观察三个主要变换；
- 记录静态和动态变换；
- 画出自己的TF树。

## 观察任务
机器人不动时数据是否变化；
前进时哪个变换变化；
旋转时四元数如何变化；
SLAM运行时 map → odom是否存在；
建图停止或重启后发生什么。
## 验收任务
当前TF树从 map到雷达的完整路径是什么？
哪些TF是静态的？
哪些TF会随机器人运动变化？
哪个节点发布 map → odom？
哪个节点发布 odom → base？

## 实际完成
- [Y] 启动仿真仿真例程；
- [Y] 查看TF树；
- [x] 观察三个主要变换；
- [Y] 记录静态和动态变换；
- [Y] 画出自己的TF树。
- [Y] 当前TF树从 map到雷达的完整路径是什么？
- [Y] 哪些TF是静态的？
- [Y] 哪些TF会随机器人运动变化？
- [Y] 哪个节点发布 map → odom？
- [Y] 哪个节点发布 odom → base？

## 指令信息
ros2 run tf2_tools view_frames  // 查看TF2中的TF树。  
ros2 run tf2_ros tf2_echo map odom  // 查看map到odom的变换信息  
ros2 run tf2_ros tf2_echo odom base_footprint  // 查看odom到base_footprint的变换信息  
ros2 run tf2_ros tf2_echo base_link laser  // 查看base_link到laser的变换信息  

ros2 topic info /tf --verbose  // 查看TF2中的TF树  
ros2 topic info /tf_static --verbose  // 查看TF2中的静态TF树  
ros2 topic info /tf_static --verbose  // 查看TF2中的静态TF树  
ros2 node list  // 查看所有节点  
ros2 node info robot_state_publisher  // 查看robot_state_publisher节点的信息  
## 关键操作记录
记录一遍总是好的，也会更理解一点
- 信息1：了解到urdf中可以提前设定材料的颜色，rgba，代表红色，绿色，蓝色，透明度的各项占比，有点类似于提前定义参数再进行使用  
[model_01.urdf](file:///home/robot/ros2_ws/src/pkg03_gazebo_20260814/urdf/model_01.urdf)

- 信息2：使用了tf-pdf呈现 观测到tf的具体关系。odom：大概率由gazebo仿真器发布，相关参数：频率50.202hz，我查询了相关信息，  
有说实际里程计的频率不会这么高；缓冲长度：4.96：最新时间戳：785.678，最老时间戳：780.727。了解到如果仿真时间等于或者略大于最新时间戳，  
代表odom是在正常更新，如果差距时间过大就表示数据断流了，这是一个验证查询的方法  
[frames_2026-08-15_22.16.56.pdf](file:///home/robot/ros2_ws/src/basic_diff_drive_chassis_gazebo_8_9/tf_pdf/frames_2026-08-15_22.16.56.pdf)

- 信息3：base_footprint是由robot_state_publisher发布，也有可能由里程计节点发送这个阶段的变换。我观察的所以模块的名称都是默认的，  
只有odom到base_footprint、base_footprint到左轮和右轮存在真实频率、缓冲长度和新鲜时间戳信息，其他比如雷达，imu与base_link连接的都是静态变化，频率为10000，缓存、时间戳都是0.0

- 信息4：了解到这些与base_link连接的都是robot_state_publisher发布的，读取urdf文件，根据urdf文件中的设定关系发布出来的。
-当前TF树从map到雷达的路径是：map-odom-base_footprint-base_link-lidar
-静态的有雷达，IMU，相机，base_link这些
-动态的有odom，base_footprint，差速底盘的左右轮子，全向底盘的四个轮子
-仿真中由SLAM发布map-odom，导航中由ACLM发布
-仿真中由gazebo发布odom-base，实物小车是由设定的底盘节点发布odom-base

- 信息5：
    能够比较好的理解到自己实物小车的TF树关系，以及每个TF节点的频率、缓冲长度、新鲜时间戳信息。  
    脑海中也能画出自己的TF树，以及每个TF节点的关系。

## 遗留问题
- urdf文件的理解与编写尚未完成，launch文件的编写也需要完成
- Action服务器的编写尚未进行

## 下一步任务
- 完成urdf文件的编写
- 完成launch文件的编写
- 完成Action服务器的编写
- 完成观测任务
- 完成验收任务
- 数据查验
- 为下一周实物小车做准备


