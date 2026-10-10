## urdf
urdf 是一个 xml 文件，用于描述机器人的运动学模型。

    get_package = get_package_share_directory('pkg03_gazebo_20260814')
    ##// 模型路径
    model_path = os.path.join(get_package, 'urdf', 'model_01.urdf')
介绍：launch文件中对urdf文件的引用分别是包路径和模型路径。

    model_arg = DeclareLaunchArgument(
        name ='model',
        #翻译：默认值
        default_value = model_path,
        #翻译：描述-可以不写-不影响功能
        description = 'Absolute path to robot URDF file/绝对路径到机器人URDF文件'
    )
介绍：引用定义launch文件参数，让启动的时候可以从外部定义模型路径。

    robot_state_publisher = Node(
        #翻译：发布机器人状态节点-ROS2自带功能包
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description,
                     'publish_frequency':20,   #翻译：发布频率-默认20Hz
                     'use_tf_static':True,    #翻译：是否使用静态TF-默认True
                     'ignore_timestamp':False, #翻译：是否忽略时间戳-默认False
                     }]
    )
介绍：node前面的robot_state_publisher可以自定义，不会影响节点名称。  
- robot_state_publisher：这个包是ROS2自带的功能包，用于发布机器人的状态。  
- 输入主要有：
- robot_description：机器人的urdf文件内容
- publish_frequency：发布频率-默认20Hz
- use_tf_static：是否使用静态TF-默认True
- ignore_timestamp：是否忽略时间戳-默认False其中后三个一般默认值即可。可以不写出来。  
- 输出主要有：
    - tf：机器人的tf变换，包括位置、方向、速度等  
- GUI=Graphical User Interface  
意味：图形用户界面  
制作方法：python + tkinter-其中tkinter是的含义是TK图形库的缩写+interface-界面  
工具	        难度	    美观度	            适合场景  
tkinter     ⭐ 最简单	⭐⭐ 一般	        简单工具、快速原型  
PyQt	  ⭐⭐ 中等	⭐⭐⭐ 好看	      复杂界面、专业工具  
rqt 插件 ⭐⭐⭐ 较难	⭐⭐⭐ 好看	        ROS2 标准工具  
Web    	  ⭐⭐ 中等	⭐⭐⭐ 好看	      远程控制、跨平台  

- 构建模型：
- 分别为：
-base-link-尺寸  
-visual-外观显示  
-collision-碰撞测试几何体（觉得应与visual相同）  
-material-材质/颜色  

- 错误：[ERROR] [launch]: Caught exception in launch (see debug for traceback): file not found: [Errno 2] No such file or directory: 'xacro/home/robot/ros2_ws/src/install/pkg03_gazebo_20260814/share/pkg03_gazebo_20260814/urdf/model_01.urdf.xacro'  
- 解释：抓取到异常（回溯看调试信息），说明模型路径错误。
原因：‘xacro ’需要存在空格，否则会报错。

- 运行存在警告：[rviz2-3] Warning: Ignoring XDG_SESSION_TYPE=wayland on Gnome. Use QT_QPA_PLATFORM=wayland to run on Wayland anyway.

                     'publish_frequency':20.0,   #翻译：发布频率-默认20Hz
注意：发布频率-默认20.0Hz，是double类型，如果是int类型，会报错。

Rviz2显示出现问题：排查中
-1.Fixed Frame可以通过输入base_link让白色模型恢复正常显示-但仍然显示no tf data  Actual error: Frame[base_link] does not exist  
robot@ROS2:~$ ros2 node list | grep robot_state_publisher
/robot_state_publisher  
-2.robot_state_publisher存在  

robot@ROS2:~$ ros2 run tf2_tools view_frames
[INFO] [1787145616.121284319] [view_frames]: Listening to tf data for 5.0 seconds...  
[INFO] [1787145621.209997247] [view_frames]: Generating graph in frames.pdf file...  
[INFO] [1787145621.212103676] [view_frames]: Result:tf2_msgs.srv.FrameGraph_Response(frame_yaml='[]')  
-3.通过tf转pdf查看，显示not tf data received  

ai告知如果只存在一个base-link，没有任何关节，那么robot_state_publisher默认不会发布tf变换。  
-4.尝试加入虚拟根  
成功解决问题  
要注意：内部包括内容的标签一行末尾不能有/>，否则会报错。这个代表结束  

- 尝试使用命令更新robot_description参数出现失败
 ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat model_01.urdf)"
cat: model_01.urdf: 没有那个文件或目录
[ERROR] [1787146803.238785098] [rcl]: Failed to parse global arguments
terminate called after throwing an instance of 'rclcpp::exceptions::RCLInvalidROSArgsError'
  what():  failed to initialize rcl: Couldn't parse parameter override rule: '-p robot_description:='. Error: error not set, at ./src/rcl/arguments.c:343
[ros2run]: Aborted  

- ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(xacro /home/robot/ros2_ws/src/pkg03_gazebo_20260814/urdf/model_01.urdf)"

# 注意路径正确，否则会报错