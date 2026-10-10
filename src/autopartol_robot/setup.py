from setuptools import find_packages, setup
from glob import glob # 用于递归查找所有文件
package_name = 'autopartol_robot'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name+"/launch", glob("launch/*.launch.py")),
        ('share/' + package_name+"/config", ['config/partol_config.yaml'])
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='robot',
    maintainer_email='2146145550@qq.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'partol_node = autopartol_robot.partol_node:main',
        ],
    },
)
