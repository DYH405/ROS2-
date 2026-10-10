import rclpy
from rclpy.node import Node
import requests


class NovelPubNode(Node):
    def __init__(self,node_name):
        super().__init__(node_name)
        self.get_logger().info(f'启动:{node_name}')

    def download(self,url):
        response = requests.get(url)
        response.encoding = 'utf-8'

def main():
    rclpy.init()
    node = NovelPubNode('novel_pub_node')
    rclpy.spin(node)
    rclpy.shutdown()
    