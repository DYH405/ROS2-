import launch
import launch_ros
from ament_index_python.packages import get_package_share_directory 

def generate_launch_description():

    autopartol_robot_path = get_package_share_directory('autopartol_robot')
    default_param_path = autopartol_robot_path + '/config/partol_config.yaml'

    partol_node = launch_ros.actions.Node(# partol节点-主节点
        package="autopartol_robot",
        executable="partol_node",
        name="partol_node",
        parameters=[default_param_path, {'use_sim_time': True}],
        output="screen",
    )

    speaker_node = launch_ros.actions.Node( # 语音节点-子节点，用于语音播报
        package="robot_speech",
        executable="speech_node",
        name="speech_node",
        parameters=[{'use_sim_time': True}],
        output="screen",
    )

    image_capture_node = launch_ros.actions.Node(# 图片处理节点-子节点
        package="robot_vision",
        executable="image_capture_node",
        name="image_capture_node",
        parameters=[{'img_save_path': '/home/robot/ros2_ws/patrol_images/'}, {'use_sim_time': True}],
        output="screen",
    )

    return launch.LaunchDescription([
        partol_node,
        speaker_node,
        image_capture_node,
    ])