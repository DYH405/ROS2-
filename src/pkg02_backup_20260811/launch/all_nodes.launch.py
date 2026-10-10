from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import TimerAction

def generate_launch_description():

    ## // node01_backup节点
    backup_node = Node(
        package="pkg02_backup_20260811",
        executable="node01_backup",
        name="node01_backup",
    )
    ## // node02_talker节点
    talker_node = Node(
        package="pkg02_backup_20260811",
        executable="node02_talker",
        name="node02_talker",
    )
    ## // node03_subscriber节点
    subscriber_node = Node(
        package="pkg02_backup_20260811",
        executable="node03_listener",
        name="node03_listener",
    )
    ## // node04_client节点
    client_node = Node(
        package="pkg02_backup_20260811",
        executable="node04_client",
        name="node04_client",
        # 显示节点日志
        output="screen",
    )
    ## //客户端需要比服务端后启动-2秒延时
    timer_client = TimerAction(
        period=2.0,
        actions=[client_node]
        )
    ## // node05_server节点
    server_node = Node(
        package="pkg02_backup_20260811",
        executable="node05_server",
        name="node05_server",
        # 显示节点日志
        output="screen",
    )
    ## // node06_action_server节点
    action_server_node = Node(
        package="pkg02_backup_20260811",
        executable="node06_action_server",
        name="node06_action_server",
        # 显示节点日志
        output="screen",
    )
    ## // node07_action_client节点
    action_client_node = Node(
        package="pkg02_backup_20260811",
        executable="node07_action_client",
        name="node07_action_client",
        # 显示节点日志
        output="screen",
    )
    ## //延时2秒启动action_client_node
    timer_action_client = TimerAction(
        period=4.0,
        actions=[action_client_node]
        )
    return LaunchDescription([
#        backup_node,
#        talker_node,
#        subscriber_node,
        #timer_client,  # 携带定时器的客户端节点，2秒后启动
        #server_node,
        action_server_node,
        timer_action_client,
    ])
