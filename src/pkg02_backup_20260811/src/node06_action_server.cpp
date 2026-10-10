#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>  // 包含action服务器的头文件
#include "example_interfaces/action/fibonacci.hpp"  //斐波那契数列action


//## 使用命名空间-简化代码
using Fibonacci = example_interfaces::action::Fibonacci;
using FibonacciGoalHandle = rclcpp_action::ServerGoalHandle<Fibonacci>;
using FibonacciGoalHandleSharedPtr = std::shared_ptr<FibonacciGoalHandle>;

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("node06_action_server");

  //## 定义action服务器
  auto server = rclcpp_action::create_server<Fibonacci>(
    node,
    "fibonacci",    // action服务器的名称
    [](const rclcpp_action::GoalUUID & uuid,
        std::shared_ptr<const Fibonacci::Goal> goal)
        ->rclcpp_action::GoalResponse{
            (void)uuid;
            //## 处理goal-如果数字大于40就拒绝
            if (goal->order > 40) {
                //先打印日志-便于观察
                RCLCPP_INFO(rclcpp::get_logger("server"), "拒绝目标：%d 太大", goal->order);
                return rclcpp_action::GoalResponse::REJECT; // 拒绝目标
            }
            RCLCPP_INFO(rclcpp::get_logger("server"), "接受目标：%d 成功", goal->order);
            return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE; // 接受目标
        },
        // ##处理取消请求
        [](const FibonacciGoalHandleSharedPtr goal_handle)->rclcpp_action::CancelResponse{
            (void)goal_handle;
            RCLCPP_INFO(rclcpp::get_logger("server"), "收到取消请求");
            return rclcpp_action::CancelResponse::ACCEPT; // 接受取消请求
        },
        // ##执行任务
        [node](const FibonacciGoalHandleSharedPtr goal_handle)-> void{
                //##开新线程不影响主程序
                std::thread([node, goal_handle](){
                    auto goal = goal_handle->get_goal();
                    int order = goal->order;

                    //初始化数列-一个动态空数组
                    std::vector<int> list;
                    list.push_back(0);
                    if (order > 0) list.push_back(1);
                    

                    //定义反馈和结果-用于action服务器的通信
                    auto feedback = std::make_shared<Fibonacci::Feedback>();
                    auto result = std::make_shared<Fibonacci::Result>();

                    for(int i=2;i<=order;i++){
                        //检查是否需要取消
                        if (goal_handle->is_canceling()){
                            result->sequence = list;
                            //告知项目已经取消，然后这个result是结果
                            goal_handle->canceled(result);
                            RCLCPP_INFO(node->get_logger(), "任务已取消目标");
                            return;
                        }
                        //计算下一个斐波那契数
                        int next = list[i-1] + list[i-2];
                        list.push_back(next);
                        //更新反馈
                        feedback->sequence.push_back(next);
                        goal_handle->publish_feedback(feedback);

                        //模拟工作耗时
                        std::this_thread::sleep_for(std::chrono::milliseconds(500));
                        
                    }

                    //## 循环结束
                    result->sequence = list;
                    goal_handle->succeed(result);
                    RCLCPP_INFO(node->get_logger(), "任务已完成");
                   //线程分离-避免阻塞主程序
                }).detach();
            }
        );
        RCLCPP_INFO(node->get_logger(), "Action服务器已启动。等待请求目标...");
        rclcpp::spin(node);
        rclcpp::shutdown();
        return 0;
}
    



