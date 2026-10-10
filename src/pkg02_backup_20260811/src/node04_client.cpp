#include <rclcpp/rclcpp.hpp>
#include <example_interfaces/srv/add_two_ints.hpp>

//## 使用命名空间-简化代码
using AddTwoInts = example_interfaces::srv::AddTwoInts;
int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("node04_client");

  //## 定义服务客户端
  auto client = node->create_client<AddTwoInts>("add_two_ints");

  //## 等待服务端-这个与node->get_logger()类似，只是这里等待的是服务端，而不是日志
  if (!client->wait_for_service(std::chrono::seconds(2))) {
        RCLCPP_ERROR(node->get_logger(), "服务 'add_two_ints' 不可用，请先启动服务端！");
        return 1;
  }
  //## 构建请求-类似于auto-msg
  auto request = std::make_shared<AddTwoInts::Request>();
  request->a = 2;
  request->b = 3;

  //日志打印-发送计算请求
  RCLCPP_INFO(node->get_logger(), "发送计算请求：%ld + %ld", request->a, request->b);

  //## 异步发送请求-类似于小票-future
  auto future = client->async_send_request(
    request,
    [node](rclcpp::Client<AddTwoInts>::SharedFuture result_future){
      auto response = result_future.get();
      RCLCPP_INFO(node->get_logger(), "收到回复: 结果是 %ld", response->sum);
    }
  );
  RCLCPP_INFO(node->get_logger(), "等待服务端回复...");
  rclcpp::spin(node);

  rclcpp::shutdown();
  return 0;
}
