from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator,TaskResult
import rclpy
from rclpy.node import Node
from tf2_ros import TransformListener,Buffer  # 坐标监听器
from tf_transformations import euler_from_quaternion,quaternion_from_euler 
from autopartol_interfaces.srv import SpeechText
from autopartol_interfaces.srv import CaptureImage



class PartolNode(BasicNavigator):
    def __init__(self,
                 node_name='partol_node'):
        super().__init__(node_name)
        self.get_logger().info('partol_node node started')
        # 声明相关参数
        self.declare_parameter('initial_point',[0.0,0.0,0.0]) # 初始点
        self.declare_parameter('target_point',[0.0,0.0,0.0,1.0,1.0,1.57]) # 目标点
        self.initial_pose = self.get_parameter('initial_point').value
        self.target_pose = self.get_parameter('target_point').value
        self.buffer_ = Buffer()  # 坐标监听器-缓冲区
        self.listener_ = TransformListener(self.buffer_,self)  # 坐标监听器
        self.speech_client_ = self.create_client(SpeechText,'speech_text')

        # 客户端-图像处理
        self.capture_client_ = self.create_client(CaptureImage,'capture_image')

    def get_pose_by_xyyaw(self,x,y,yaw):
        '''
        return PoseStamped
        '''
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x
        pose.pose.position.y = y
        # 返回顺序，xyzw
        quat = quaternion_from_euler(0,0,yaw)
        pose.pose.orientation.x = quat[0]
        pose.pose.orientation.y = quat[1]
        pose.pose.orientation.z = quat[2]
        pose.pose.orientation.w = quat[3]
        return pose
    def init_robot_pose(self):
        """
        初始化机器人位姿,本身继承,使用self而不是nav
        """
        self.initial_pose = self.get_parameter('initial_point').value
        init_pose = self.get_pose_by_xyyaw(self.initial_pose[0],
                                           self.initial_pose[1],
                                           self.initial_pose[2])
        self.setInitialPose(init_pose)
        self.waitUntilNav2Active() # 等待导航器激活
    def get_target_points(self):
        """
        通过参数点获取目标点集合
        """
        points = []
        self.target_pose = self.get_parameter('target_point').value
        for index in range(int(len(self.target_pose)/3)): # index是循环次数
            x = self.target_pose[index*3]
            y = self.target_pose[index*3+1]
            yaw = self.target_pose[index*3+2]
            points.append([x,y,yaw]) # append:append object to list 把对象加到末尾
            self.get_logger().info(f'获取目标点{index}->{x},{y},{yaw}')
        return points
    def nav_to_pose(self,target_pose):
        """
        target_pose: PoseStamped
        新增:超时机制,导航超时60秒,取消任务
        """
        start_time = self.get_clock().now() # 记录开始时间
        timeout = 60.0 # 超时时间
        self.goToPose(target_pose)
        while not self.isTaskComplete():
            # 超时处理
            elapsed = (self.get_clock().now() - start_time).nanoseconds / 1e9 # 转换为秒
            if elapsed > timeout:
                self.cancelTask()
                self.get_logger().info('导航超时,取消任务')
                break
            # 导航中处理反馈
            feedback = self.getFeedback()
            self.get_logger().info(f'剩余距离：{feedback.distance_remaining}')
        # self.cancelTask()
        # 结果处理
        result = self.getResult()
        if result == TaskResult.SUCCEEDED:
            self.get_logger().info('导航成功')
            return True
        elif result == TaskResult.FAILED:
            self.get_logger().error('导航失败')
            return False
        elif result == TaskResult.CANCELED:
            self.get_logger().info('导航取消')
            return False
        elif result == TaskResult.UNKNOWN:
            self.get_logger().error('导航未知')
            return False
    def get_current_pose(self):
        """
        获取当前机器人位姿
        """
        while rclpy.ok():
            max_retries = 5 # 最大重试次数
            for i in range(max_retries):
                try:
                    result = self.buffer_.lookup_transform('map', 'base_footprint',
                                                            rclpy.time.Time(seconds=0.0),
                                                            rclpy.time.Duration(seconds=1.0))
                    transform = result.transform
                    self.get_logger().info(f'平移：{transform.translation}')
                    # self.get_logger().info(f'旋转：{transform.rotation}')
                    # rotatiomn_euler = euler_from_quaternion([transform.rotation.x,
                    #                                         transform.rotation.y,
                    #                                         transform.rotation.z,
                    #                                         transform.rotation.w])
                    # self.get_logger().info(f'旋转欧拉角：{rotatiomn_euler}')
                    return transform
                except Exception as e:
                    self.get_logger().info(f'获取坐标换失败：{str(e)}')
            self.get_logger().error('获取坐标换失败，请检查导航是否正常')
            #self.wait_for_seconds(1.0)
            return None

    def speak_text(self,text):
        """
        text: str
        回调函数存放在内部，避免变量无法传递
        且直接调用,无需self.前缀
        """
        for i in range(20): # 重试20次
            if self.speech_client_.wait_for_service(timeout_sec=1.0):
                break
        else:
            self.get_logger().error('语音合成服务未就绪,重试20次失败')
            return

        request = SpeechText.Request()
        request.text = text
        future = self.speech_client_.call_async(request)
        # 先进行注释，减少阻塞-推荐方案：多线程
        #rclpy.spin_until_future_complete(self,future)
        # 回调函数-内部子函数无需self.前缀
        def speech_done(future):
            response = future.result()
            if response is not None:
                if response.result == True:
                    self.get_logger().info(f'语音合成成功：{text}')
                else:
                    self.get_logger().info(f'语音合成失败：{text}')
            else:
                self.get_logger().warn('服务请求失败')
        future.add_done_callback(speech_done)


    def record_img(self): # 保存图片-客户端调用
        """
        保存图片-客户端调用
        """
        for i in range(20): # 重试20次
            if self.capture_client_.wait_for_service(timeout_sec=1.0):
                break
        else:
            self.get_logger().error('图片保存服务未就绪,重试20次失败')
            return

        request = CaptureImage.Request() # 请求-无参数请求
        future = self.capture_client_.call_async(request)

        def record_done(future):
            response = future.result()
            if response is not None:
                if response.result == True:
                    self.get_logger().info(f'图片保存成功')
                else:
                    self.get_logger().info(f'图片保存失败')
            else:
                self.get_logger().warn('服务请求失败')
        future.add_done_callback(record_done)


        
def main():
    rclpy.init()

    partol = PartolNode()  #节点
    partol.speak_text('正在准备初始化位置')

    partol.init_robot_pose() # 初始化机器人位姿
    partol.speak_text('初始化位置完成')



    while rclpy.ok():
        partol_failed = False # 导航失败标志
        rclpy.spin_once(partol,timeout_sec=1.0)
        points = partol.get_target_points()
        for point in points:
            rclpy.spin_once(partol,timeout_sec=0.0)
            x,y,yaw = point[0],point[1],point[2]
            target_pose = partol.get_pose_by_xyyaw(x,y,yaw) # 目标点
            partol.speak_text(f'正在导航到目标点：{x},{y},{yaw}')
            success = partol.nav_to_pose(target_pose)
            if success:
                partol.speak_text(f'已经到达目标点：{x},{y},{yaw}，正在保存图片...')
                partol.record_img()
                partol.get_current_pose()
            else:
                # 导航失败-停止
                partol.speak_text(f'导航失败，请检查导航参数')
                partol_failed = True
                break
        if partol_failed:
            break
    rclpy.shutdown()
    partol.destroy_node()