import rclpy
from rclpy.node import Node
class PersonNode(Node):
    def __init__(
            self,
            node_name:str,
            name:str,
            age:int
            ) ->None:
        print("PersonNode")
        super().__init__(node_name)
        self.name = name
        self.age = age

    def eat(self,food_name:str):
        """
        方法：吃东西
        ：食物名字
        """
        self.get_logger().info(f'{self.name},{self.age}爱吃{food_name}')
def main():
    rclpy.init()
    node = PersonNode("yuxiang", "りん", 18)
    node.eat('鱼想ROS')
    rclpy.spin(node)
    rclpy.shutdown()
        
