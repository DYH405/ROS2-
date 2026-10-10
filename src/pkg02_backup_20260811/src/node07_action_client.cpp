#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>  // 包含action服务器的头文件
#include "example_interfaces/action/fibonacci.hpp"  //斐波那契数列action

using Fibonacci = example_interfaces::action::Fibonacci;

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);
    auto node = rclcpp::Node::make_shared("node07_action_client");
    //## 创建action客户端
    auto client = rclcpp_action::create_client<Fibonacci>(
        node, 
        "fibonacci");

        if(!client->wait_for_action_server(std::chrono::milliseconds(500))){
            RCLCPP_ERROR(node->get_logger(), "Action 服务端未响应");
            return 1;
        }

        //## 构造Goal目标
        auto goal = std::make_shared<Fibonacci::Goal>();
        goal->order = 10;

        //## 把goal定义位send_goal_options
        rclcpp_action::Client<Fibonacci>::SendGoalOptions send_goal_options;

        //然后把参数都放在send_goal_options中-反馈回调
        send_goal_options.feedback_callback = 
            [node](auto, const std::shared_ptr<const Fibonacci::Feedback> feedback){
                //这里ss是可以自定义的，类似与int a = 10
                std::stringstream ss;
                for(int num : feedback->sequence) ss << num << " ";
                RCLCPP_INFO(node->get_logger(), "实时反馈: %s", ss.str().c_str());  
            };
        send_goal_options.result_callback = 
            [node](const rclcpp_action::ClientGoalHandle<Fibonacci>::WrappedResult & result){
                if(result.code == rclcpp_action::ResultCode::SUCCEEDED){
                    std::stringstream ss;
                    for(int num : result.result->sequence)ss << num << " ";
                    RCLCPP_INFO(node->get_logger(), "最终结果: [%s]", ss.str().c_str());
                }else{
                    RCLCPP_ERROR(node->get_logger(), "任务被取消");
                }
            };
            //## 异步发送请求
            client->async_send_goal(*goal, send_goal_options);
            RCLCPP_INFO(node->get_logger(), "目标已发送，等待反馈...");
            rclcpp::spin(node);
            rclcpp::shutdown();
            return 0;
}