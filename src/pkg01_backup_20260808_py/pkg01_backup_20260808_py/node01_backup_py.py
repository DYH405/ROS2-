import rclpy
from rclpy.node import Node

def main(argv=None):
    rclpy.init(args=argv)
    node = Node('node01_backup')
    node.get_logger().info('Hello from node01_backup.')
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()