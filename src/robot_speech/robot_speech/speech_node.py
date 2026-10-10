import rclpy
from rclpy.node import Node
from autopartol_interfaces.srv import SpeechText
import espeakng


class SpeechNode(Node):
    def __init__(self):
        super().__init__('speech_node')
        self.speech_service_ = self.create_service(
            SpeechText, 'speech_text', self.speech_text_callback)
        self.speaker_ = espeakng.Speaker()
        self.speaker_.voice = 'zh'

    def speech_text_callback(self, request, response):
        self.get_logger().info(f'收到语音请求：{request.text}')
        self.speaker_.say(request.text)
        self.speaker_.wait()
        response.result = True
        return response


def main():
    rclpy.init()
    node = SpeechNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()