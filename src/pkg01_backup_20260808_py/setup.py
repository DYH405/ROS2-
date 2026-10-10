from setuptools import find_packages, setup

package_name = 'pkg01_backup_20260808_py'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='robot',
    maintainer_email='robot@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'node01_backup_py = pkg01_backup_20260808_py.node01_backup_py:main',
            'tf_static = pkg01_backup_20260808_py.tf_static:main',
            'tf_listener = pkg01_backup_20260808_py.tf_listener:main',
            'get_robot_pose = pkg01_backup_20260808_py.get_robot_pose:main',
            'nav_to_pose = pkg01_backup_20260808_py.nav_to_pose:main',
            'waypoint_follow = pkg01_backup_20260808_py.waypoint_follow:main',
            'person_node = pkg01_backup_20260808_py.person_node:main',
            'writer = pkg01_backup_20260808_py.writer:main',
            'novel_pub_node = pkg01_backup_20260808_py.novel_pub_node:main',
            'learn_thread = pkg01_backup_20260808_py.learn_thread:main',
            'novel_sub_node = pkg01_backup_20260808_py.novel_sub_node:main',
            'speaker = pkg01_backup_20260808_py.speaker:main',
        ],
    },
)