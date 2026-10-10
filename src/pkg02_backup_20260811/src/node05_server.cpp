#include <rclcpp/rclcpp.hpp>
#include <example_interfaces/srv/add_two_ints.hpp>


//## 使用命名空间-简化代码
using AddTwoInts = example_interfaces::srv::AddTwoInts;
int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("node05_server");

    RCLCPP_INFO(node->get_logger(), "服务端已启动\n");

  //## 定义服务端
  auto server = node->create_service<example_interfaces::srv::AddTwoInts>(
    "add_two_ints",
    [node](
        const std::shared_ptr<AddTwoInts::Request> request,
      
        std::shared_ptr<AddTwoInts::Response> response
    ){
        response->sum = request->a + request->b;

        RCLCPP_INFO(node->get_logger(),
                    "收到计算请求：%ld + %ld=%ld",
                    request->a, request->b, response->sum);
    }

);

  rclcpp::spin(node);

  rclcpp::shutdown();

  return 0;
}