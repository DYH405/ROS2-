# Day 5:Action
2026.8.17

## 今日目标
- 完成urdf文件的编写
- 完成launch文件的编写
- 完成Action服务器的编写
- 完成观测任务
- 完成验收任务
- 数据查验
- 为下一周实物小车做准备

# Action部分
- 能解释目标、反馈、结果和取消；  
- 运行一个官方Action示例；  
- 使用命令行发送、观察和取消目标；  
暂时不要求自己完整写Action服务器。  

## 实际完成
- [Y] Action服务器的编写

# 基本概念
Action:  
请求-反馈-结果  
## 关键操作记录  

# 服务器端-编写过程问题
信息-1：  
auto server = node->create_action_server<Fibonacci>，补全器为什么会推荐我使用这个，这和你给出的  rclcpp_action::create_server，有什么区别？  
第一个实际上不存在，第二个是ROS2的Action API。  
信息-2：  
const rclcpp_action::GoalUUID & uuid,  
Action-中可能存储多个目标，每个目标都有一个唯一的UUID。  
信息-3：  
std::shared_ptr<Fibonacci::Goal> goal)  
携带的数据是目标，即用户请求的计算任务。  
->rclcpp_action::GoalResponse  
设定返回值  
信息-4：  
这里为什么使用的是rclcpp::get_logger("server")？而不是node->get_logger()？  
原因：因为这里的[]没有捕获外部node，所以不能使用node->get_logger()。改为使用全局的rclcpp::get_logger("server")。  
RCLCPP_INFO(rclcpp::get_logger("server"), "拒绝目标：%ld 太大", goal->order);  
信息-5：  
//##开新线程不影响主程序  
std::thread([node, goal_handle](){  
初始化一个空的数组，其中vector/int/list/push_back都可以改变，其中list是可以自定义的。  
std::vector<int> list;  
list.push_back(0);  

编译错误：    
没有ACCEPT这个枚举值。这是ROS1的用法，ROS2的用法是：ACCEPT_AND_EXECUTE  
return rclcpp_action::CancelResponse::ACCEPT;   
错误2：  
result->list = list;这个的第一个list必须用sequence  
错误3：  
[](const rclcpp_action::GoalUUID & uuid,  
std::shared_ptr<Fibonacci::Goal> goal),这里应该是<const Fibonacci::Goal>参数不匹配导致错误  

## 今日总结
- 学习了Action的基本概念
- 完成了Action服务器的编写
## 缺陷
- 整个Action双端任务只完成了一半  
- 在游戏上花费了太多时间，导致没有完成Action客户端的编写
- urdf-launch-观测-验收-数据查验-为下一周实物小车做准备都没有推进

## 优化方向与自我约束
- 降低在游戏上的时间花费，比前一天少一个时辰
- 推进urdf-launch文件编写
- 进入第二周SLAM任务阶段