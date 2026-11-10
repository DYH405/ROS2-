# =============================================================================
# M3 EKF 链路验证用 launch（与 gazebo_test.launch.py 同构，只多一个 EKF 节点）
#
# 与 gazebo_test.launch.py 的唯一区别：xacro 解析时显式传 publish_odom_tf:=false，
# 让差速插件停止发布 odom -> base_footprint，把这条 TF 的发布权交给 EKF。
#
# 为什么必须成对：插件和 EKF 同时发同一条 TF 边，RViz 里车身会来回抽。
# 为什么单独开这个文件而不是改 gazebo_test：批量实验的 AMCL 依赖插件发的这条
# TF，gazebo_test.launch.py 保持原样（不传该参数 -> 默认 true），基线不受影响。
#
# 验证思路是"减法"：先注释掉 ekf_node 只起其余部分，此时
# tf2_echo odom base_footprint 应当完全查不到该 TF —— 这直接证明
# publish_odom_tf:=false 透传成功；再把 ekf_node 放回来，TF 恢复 = EKF 接管成功。
# =============================================================================

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
    ekf_config_path = os.path.join(pkg_share, 'config', 'ekf.yaml')

    # 与 gazebo_test 的唯一差异：末尾追加 publish_odom_tf:=false。
    # 'xacro ' 后面那个空格不能删，拼接后才是一条合法命令。
    # 注意这里读的是 install/ 下的 model.xacro 副本，改完 src 必须重新 build 才生效。
    robot_description_content = ParameterValue(
        Command(['xacro ', model_path, ' publish_odom_tf:=false']),
        value_type=str
    )

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

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description_content}],
        output='screen'
    )

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

    delayed_spawn_entity_node = TimerAction(
        period=3.0,
        actions=[spawn_entity_node]
    )

    # 唯一新增的节点。name 必须与 ekf.yaml 顶层 key 'ekf_filter_node' 逐字一致，
    # 否则参数静默不加载、节点以全默认值运行且不报任何错。
    # use_sim_time 写在 ekf.yaml 里，不在这里重复设置。
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        parameters=[ekf_config_path],
        output='screen'
    )

    return LaunchDescription([
        gazebo_node,
        robot_state_publisher_node,
        delayed_spawn_entity_node,
        ekf_node
    ])