import espeakng
import rclpy
from rclpy.node import Node
import requests
from example_interfaces.msg import String
from queue import Queue
import threading
import time


class NovelSubNode(Node):
    def __init__(self,node_name):
        super().__init__(node_name)
        self.get_logger().info(f'启动:{node_name}')
        self.novel_queue = Queue()
        self.empty = 0
        self.novel_sub_ = self.create_subscription(String,'novel_pub',self.novel_callback,10)
        self.speech_thread = threading.Thread(target=self.speak_thread) # 创建线程
        self.speech_thread.start() # python线程不会自己启动，需要手动启动

    def novel_callback(self,msg):
        self.novel_queue.put(msg.data)

    def speak_thread(self):
        speaker = espeakng.Speaker()
        speaker.voice = 'zh'

        while rclpy.ok():
            if self.novel_queue.qsize() > self.empty: # 队列不为空
                text = self.novel_queue.get()
                self.get_logger().info(f'开始朗读:{text}')
                speaker.say(text) # threading.
                speaker.wait() # 等待朗读完成
            else:
                # 让当前线程休眠
                time.sleep(1)

def main():
    rclpy.init()
    node = NovelSubNode('novel_sub_node')
    rclpy.spin(node)
    rclpy.shutdown()
    