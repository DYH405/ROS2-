import launch
import launch_ros
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from ament_index_python.packages import get_package_share_directory 

def _launch_nodes(context): # 运行时组装节点，便于按是否显式传参决定是否覆盖 yaml
    patrol_mission_path = get_package_share_directory('patrol_mission')
    default_param_path = patrol_mission_path + '/config/patrol_config.yaml'

    # 仅当显式传入 max_rounds 时才覆盖 yaml，留空则沿用 patrol_config.yaml 中的值，
    # 避免 launch 默认值把 yaml 永久压住（那样改 yaml 也不生效）
    overrides = {'use_sim_time': True}
    mr = context.launch_configurations.get('max_rounds', '')
    if str(mr).strip():
        overrides['max_rounds'] = int(mr)

    patrol_node = launch_ros.actions.Node(# patrol节点-主节点
        package="patrol_mission",
        executable="patrol_node",
        name="patrol_node",
        # yaml 作为基础配置，overrides 中同名字段覆盖其上
        parameters=[default_param_path, overrides],
        output="screen",
    )

    speaker_node = launch_ros.actions.Node( # 语音节点-子节点，用于语音播报
        package="patrol_speech",
        executable="speech_node",
        name="speech_node",
        parameters=[{'use_sim_time': True}],
        output="screen",
    )

    image_capture_node = launch_ros.actions.Node(# 图片处理节点-子节点
        package="patrol_vision",
        executable="image_capture_node",
        name="image_capture_node",
        parameters=[{'img_save_path': '/home/robot/ros2_ws/patrol_images/'}, {'use_sim_time': True}],
        output="screen",
    )

    return [patrol_node, speaker_node, image_capture_node]

def generate_launch_description():

    # 巡逻轮数：留空则用 patrol_config.yaml 的 max_rounds；传值则覆盖，如 max_rounds:=3
    # run_one_experiment.sh 通过 ROUNDS 环境变量透传
    max_rounds_arg = DeclareLaunchArgument(
        'max_rounds',
        default_value='',
        description='巡逻循环轮数，留空则使用 patrol_config.yaml 中的 max_rounds')

    return launch.LaunchDescription([
        max_rounds_arg,
        OpaqueFunction(function=_launch_nodes),
    ])