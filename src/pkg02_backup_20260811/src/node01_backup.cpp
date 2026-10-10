#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
//## 三种定时时间
/*
std::chrono::milliseconds(500)
std::chrono::seconds(1)
std::chrono::duration<double>(0.1)
*/
int main(int argc, char * argv[])
{
 rclcpp::init(argc, argv);
 
 auto node = std::make_shared<rclcpp::Node>("node01_backup"); 
 
 RCLCPP_INFO(node->get_logger(), "我的枪去而复返，你的生命有去无回！\n");

 //--------------------------------------------
//--------------------------------------------
 /*while(rclcpp::ok())
  {
    RCLCPP_INFO(node->get_logger(), "别投，我还能秀！\n");
  }*/
//--------------------------------------------
//--------------------------------------------
//## 订阅类回调函数
 /*auto subscription =node->create_subscription<std_msgs::msg::String>(
    "chat_topic",
    10,
    [&node](const std_msgs::msg::String::SharedPtr msg) {
      RCLCPP_INFO(node->get_logger(),
                 "我听到了：%s", 
                  msg->data.c_str());
    }
  );*/

// ## 定时器类回调函数
 auto timer = node->create_wall_timer(
      std::chrono::seconds(1),
      [&node](){
        RCLCPP_INFO(node->get_logger(), "我是定时器回调函数\n");
    }
  );
 rclcpp::spin(node);

 RCLCPP_INFO(node->get_logger(), "节点关闭\n");
 rclcpp::shutdown();
 
 return 0;
}