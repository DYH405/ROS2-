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

 //## 定义Qos服务质量配置-手动参数配置-链式调用最后一个才用分号
 auto qos_settings = rclcpp::QoS(10)   //-10条消息缓存
    .best_effort()                     //尽力而为
    .durability_volatile()             //瞬态
    .lifespan(rclcpp::Duration::from_seconds(1.0)); //1秒内有效
 
    auto node = std::make_shared<rclcpp::Node>("node02_talker"); 
//定义发布者节点
 auto talker = node->create_publisher<std_msgs::msg::String>(
    "topic_1",
    qos_settings
 );
 
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
      std::chrono::seconds(5),
      //定时器回调函数和发布者回调函数无需参数，不需要捕获变量
      [&node, &talker](){
        RCLCPP_INFO(node->get_logger(), "我是定时器回调函数\n");
         //标准消息类型-直接赋值
            auto msg = std_msgs::msg::String();
            msg.data = "我已准备就绪！";
            RCLCPP_INFO(node->get_logger(), "我已发布：%s", msg.data.c_str());
            talker->publish(msg);
    }
  );
 rclcpp::spin(node);

 RCLCPP_INFO(node->get_logger(), "节点关闭\n");
 rclcpp::shutdown();
 
 return 0;
}