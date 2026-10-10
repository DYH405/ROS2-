from cv_bridge import CvBridge # 把mag的image转换为cv2的numpy 格式
import cv2 # 图片处理
from sensor_msgs.msg import Image
from rclpy.node import Node # 节点类
from tf2_ros import TransformListener,Buffer  # 坐标监听器
import rclpy
from autopartol_interfaces.srv import CaptureImage
from datetime import datetime # 日期时间模块

class ImageCaptureNode(Node):
    def __init__(self):
        super().__init__('image_capture_node')

        # 图像处理相关
        self.declare_parameter('img_save_path','') # 图片保存路径
        self.img_save_path = self.get_parameter('img_save_path').value # 图片保存路径
        self.cv_bridge_ = CvBridge() # 图片格式转换器
        self.latest_img_ = None # 最新图片
        self.img_sub_ = self.create_subscription(Image,'/camera/image_raw',self.img_callback,10) # 图片订阅器
        self.buffer_ = Buffer()  # 坐标监听器-缓冲区
        self.listener_ = TransformListener(self.buffer_,self)  # 坐标监听器

        # 服务端
        self.save_img_ = self.create_service(CaptureImage,'capture_image',self.record_img)
        # 把图片赋予时间辍
        self.group_name_ = datetime.now().strftime('%Y%m%d_%H%M')

    def img_callback(self,msg):
        """
        图片回调函数
        """
        self.latest_img_ = msg # 最新图片
    def record_img(self,request,response):
        if self.latest_img_ is not None:
            pose = self.get_current_pose()
            if pose is None:
                self.get_logger().warn('无法获取当前机器人位姿，无法保存图片')
                response.result = False
                return response # 返回响应
            cv_image = self.cv_bridge_.imgmsg_to_cv2(self.latest_img_) # 第二个参数可选，默认为bgr8
            # 新增时间辍-分组-一次运行的所有图片为一组
            cv2.imwrite(
                f'{self.img_save_path}img_{self.group_name_}_{pose.translation.x:3.2f}_{pose.translation.y:3.2f}_{pose.translation.z:3.2f}.png',
                cv_image)
            response.result = True
            return response # 返回响应
        else:
            self.get_logger().warn('当前没有图片，无法保存')
            response.result = False
            return response # 返回响应
    
    def get_current_pose(self):
        """
        获取当前机器人位姿
        """
        max_retries = 5 # 最大重试次数
        for i in range(max_retries):
            try:
                result = self.buffer_.lookup_transform('map', 'base_footprint',
                                                        rclpy.time.Time(seconds=0.0),
                                                        rclpy.time.Duration(seconds=1.0))
                transform = result.transform
                self.get_logger().info(f'平移：{transform.translation}')
                return transform
            except Exception as e:
                self.get_logger().info(f'获取坐标换失败：{str(e)}')
        self.get_logger().error('获取坐标换失败，请检查导航是否正常')
        return None
def main():
    rclpy.init()
    node = ImageCaptureNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()