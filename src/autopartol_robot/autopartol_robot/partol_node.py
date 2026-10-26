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

        # 重试机制
        self.declare_parameter('nav_retry_count', 2) # 导航重试次数
        self.declare_parameter('nav_fail_action', 'skip') # skip:跳过,stop:停止
        self.declare_parameter('max_rounds', 3) # 最大循环次数
        self.nav_retry_count = self.get_parameter('nav_retry_count').value
        self.nav_fail_action = self.get_parameter('nav_fail_action').value
        self.max_rounds = self.get_parameter('max_rounds').value # 最大循环次数
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
        if not self.goToPose(target_pose):
            self.get_logger().warn('导航目标被拒绝')
            return 'rejected', 0.0
        is_timeout = False # 超时标志位
        elapsed = 0.0 # 防御性初始化，避免循环零次执行时 UnboundLocalError
        last_log_time = 0.0 # 日志节流-上次打印时间
        log_interval = 1.0 # 日志打印间隔(秒)
        while not self.isTaskComplete():
            rclpy.spin_once(self,timeout_sec=0.05) # 有就处理，没有等50ms再返回
            # 超时处理
            elapsed = (self.get_clock().now() - start_time).nanoseconds / 1e9 # 转换为秒
            if elapsed > timeout:
                self.cancelTask()
                is_timeout = True
                break
            # 导航中处理反馈
            feedback = self.getFeedback()
            if feedback is not None and elapsed - last_log_time >= log_interval: # 节流控制，降低日志频率
                self.get_logger().info(f'剩余距离：{feedback.distance_remaining}')
                last_log_time = elapsed
        # self.cancelTask()
        # 结果处理-统计信息
        result = self.getResult()
        if result == TaskResult.SUCCEEDED:
            return 'succeeded', elapsed
        elif result == TaskResult.FAILED:
            return 'failed', elapsed
        elif result == TaskResult.CANCELED:
            if is_timeout:
                return 'timeout', elapsed
            return 'canceled', elapsed
        else:
            return 'unknown', elapsed
    def get_current_pose(self):
        """
        获取当前机器人位姿，有限重试后返回
        """
        max_retries = 5
        for i in range(max_retries):
            try:
                result = self.buffer_.lookup_transform('map', 'base_footprint',
                                                        rclpy.time.Time(seconds=0.0),
                                                        rclpy.time.Duration(seconds=1.0))
                transform = result.transform
                self.get_logger().info(f'平移：{transform.translation}')
                return transform
            except Exception as e:
                self.get_logger().info(f'获取坐标变换失败({i+1}/{max_retries})：{str(e)}')
        self.get_logger().error('获取坐标变换失败，请检查导航是否正常')
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
    # 初始化计数
    round_count = 0 # 轮数计数
    total_success = 0 # 全程成功计数
    total_failed = 0 # 全程失败计数
    total_timeout = 0 # 全程超时计数
    total_canceled = 0 # 全程取消计数
    total_rejected = 0 # 全程拒绝计数

    while rclpy.ok() and round_count < partol.max_rounds:

        # 轮次计时-开始
        round_start_time = partol.get_clock().now()
        partol_failed = False # 导航失败标志
        success_count = 0 # 每轮清零
        timeout_count = 0
        canceled_count = 0
        rejected_count = 0
        failed_count = 0
        rclpy.spin_once(partol,timeout_sec=0.0) # 有就处理，没有就直接返回
        points = partol.get_target_points()
        round_count += 1 # 轮数计数
        for point in points:
            rclpy.spin_once(partol,timeout_sec=0.0) # 有就处理，没有就直接返回
            x,y,yaw = point[0],point[1],point[2]
            target_pose = partol.get_pose_by_xyyaw(x,y,yaw) # 目标点
            partol.speak_text(f'正在导航到目标点：{x},{y},{yaw}')
            nav_succeeded = False
            for attempt in range(partol.nav_retry_count + 1):
                status, nav_time = partol.nav_to_pose(target_pose)
                if status == 'succeeded':
                    nav_succeeded = True
                    break
                elif status in ('rejected', 'canceled'):
                    partol.get_logger().warn(f'导航{status}，确定性失败，不重试')
                    break
                if attempt < partol.nav_retry_count:
                    partol.get_logger().warn(
                        f'导航{status}，第{attempt+1}次重试（共{partol.nav_retry_count}次）')
                else:
                    partol.get_logger().error(f'导航{status}，重试耗尽')
            if nav_succeeded:
                success_count += 1
                partol.speak_text(f'已经到达目标点：{x},{y},{yaw}，正在保存图片...')
                partol.record_img()
                pose_result = partol.get_current_pose()
                if pose_result is None:
                    partol.get_logger().warn(f'目标点{x},{y},{yaw}位姿获取失败，跳过记录')
            else:
                failed_count += 1
                if status == 'timeout':
                    timeout_count += 1
                elif status == 'canceled':
                    canceled_count += 1
                elif status == 'rejected':
                    rejected_count += 1
                if partol.nav_fail_action == 'stop':
                    partol_failed = True
                    break
        round_elapsed_time = (partol.get_clock().now() - round_start_time).nanoseconds / 1e9
        total_points = len(points)  # 总目标点数
        partol.get_logger().info(
            f'第{round_count}轮完成，'
            f'成功{success_count}/{total_points},'
            f'失败{failed_count}, 超时{timeout_count}, 拒绝{rejected_count},'
            f'耗时{round_elapsed_time:.1f}秒'
            )
        total_success += success_count
        total_failed += failed_count
        total_timeout += timeout_count
        total_canceled += canceled_count
        total_rejected += rejected_count
        if partol_failed:
            break
    partol.get_logger().info(
        f'巡逻结束，全程统计：'
        f'成功{total_success}, 失败{total_failed}, '
        f'超时{total_timeout}, 取消{total_canceled}, 拒绝{total_rejected}'
    )
    partol.destroy_node()
    rclpy.shutdown()