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
     
     auto node = std::make_shared<rclcpp::Node>("node03_listener"); 
 //定义订阅者节点
 auto listener = node->create_subscription<std_msgs::msg::String>(
     "topic_1",
     qos_settings,
     [node](const std_msgs::msg::String::SharedPtr msg) { //按值捕获node，避免循环引用问题
       RCLCPP_INFO(node->get_logger(),
                  "我听到了：%s", 
                   msg->data.c_str());
     }
   );

  rclcpp::spin(node);

  RCLCPP_INFO(node->get_logger(), "节点关闭\n");
  rclcpp::shutdown();
  return 0;
}


