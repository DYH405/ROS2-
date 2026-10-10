import rclpy
from rclpy.node import Node
import requests
from example_interfaces.msg import String
from queue import Queue

class NovelPubNode(Node):
    def __init__(self,node_name):
        super().__init__(node_name)
        self.get_logger().info(f'启动:{node_name}')
        self.novel_queue_ = Queue()    # 创建队列
        self.novel_pub_ = self.create_publisher(String,'novel_pub',10)
        self.create_timer(5.0,self.timer_callback)


    def timer_callback(self):
        if self.novel_queue_.qsize() > 0:
            line = self.novel_queue_.get()
            msg = String()
            msg.data = line
            self.novel_pub_.publish(msg)
            self.get_logger().info(f'发布：{msg}')

    def download(self,url): # erl：网址
        response = requests.get(url)
        response.encoding = 'utf-8'
        text = response.text
        self.get_logger().info(f'{url} 内容：{len(text)}-> {text[0:5]}')
        #self.novel_pub_.publish()
        for line in text.splitlines():
            self.novel_queue_.put(line)


def main():
    rclpy.init()
    node = NovelPubNode('novel_pub_node')
    node.download('http://0.0.0.0:8000/novel1.txt')
    rclpy.spin(node)
    rclpy.shutdown()
    