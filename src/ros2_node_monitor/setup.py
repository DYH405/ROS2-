from setuptools import setup, find_packages
import os

setup(
    name='ros2_node_monitor',
    version='0.0.0',
    packages=find_packages(exclude=['config']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + 'ros2_node_monitor']),
        ('share/ros2_node_monitor', ['package.xml']),
        (os.path.join('share', 'ros2_node_monitor', 'config'),
            ['config/monitor_config.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='robot',
    maintainer_email='robot@todo.todo',
    description='ROS2 node lifecycle monitor with GUI visualization',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'node_monitor = ros2_node_monitor.gui_app:main',
        ],
    },
)