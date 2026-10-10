import rclpy
from rclpy.node import Node
from tf2_ros import TransformListener,Buffer
from geometry_msgs.msg import TransformStamped
from tf_transformations import euler_from_quaternion   
import math

class TFListener(Node):
    def __init__(self):
        super().__init__('dynamic_tf_listener')
        self.buffer = Buffer()
        self.listener_ = TransformListener(self.buffer,self)
        self.timer_ = self.create_timer(0.01, self.get_transform)

    def get_transform(self):
        try:
            result = self.buffer.lookup_transform('map', 'base_footprint',
                                                    rclpy.time.Time(seconds=0.0),
                                                    rclpy.time.Duration(seconds=1.0))
            transform = result.transform
            self.get_logger().info(f'平移：{transform.translation}')
            self.get_logger().info(f'旋转：{transform.rotation}')
            rotatiomn_euler = euler_from_quaternion([transform.rotation.x,
                                                    transform.rotation.y,
                                                    transform.rotation.z,
                                                    transform.rotation.w])
            self.get_logger().info(f'旋转欧拉角：{rotatiomn_euler}')
        except Exception as e:
            self.get_logger().info(f'获取坐标换失败：{str(e)}')

def main():
    rclpy.init()
    node = TFListener()
    rclpy.spin(node)
    rclpy.shutdown()
