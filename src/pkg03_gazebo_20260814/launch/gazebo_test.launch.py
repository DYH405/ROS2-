import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch.substitutions import Command 
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
 
def generate_launch_description():
    pkg_share = get_package_share_directory('pkg03_gazebo_20260814')
 
    model_path = os.path.join(pkg_share, 'urdf', 'model.xacro')
    world_path = os.path.join(pkg_share, 'worlds', 'robocup_home.world')
 
    robot_description_content = ParameterValue(
        Command(['xacro ', model_path]),
        value_type=str
    )
 
    # 启动 Gazebo，并加载 world
    gazebo_node = ExecuteProcess(
        cmd=[
            'gzserver',
            #'gazebo',
            '--verbose',
            world_path,
            '-s', 'libgazebo_ros_init.so',
            '-s', 'libgazebo_ros_factory.so'
        ],
        output='screen'
    )
 
    # 发布机器人状态
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description_content}],
        output='screen'
    )
 
    # 将机器人模型注入(spawn)到 Gazebo 环境中
    spawn_entity_node = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-topic', 'robot_description',
            '-entity', 'basic_diff_drive_robot',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.10'
        ],
        output='screen'
    )
 
    # 延时注入，等待 Gazebo 引擎完全就绪
    delayed_spawn_entity_node = TimerAction(
        period=3.0,
        actions=[spawn_entity_node]
    )
 
    return LaunchDescription([
        gazebo_node,
        robot_state_publisher_node,
        delayed_spawn_entity_node
    ])