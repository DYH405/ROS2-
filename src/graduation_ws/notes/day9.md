## urdf
rviz配置文件
launch中gazebo配置
-s：system plugin-系统插件
init.so',# 提供/clock时钟同步-
factory.so',# 提供模型工厂-增加删除模型
            '-topic', 'robot_description',#模型数据话题
如果世界没有模型，首先ros2 topic list | grep description，是否存在数据

            '-z', '0.10'#必须严格等于 URDF 中 base_footprint 到 base_link 的 z 偏移值
问题：无法加载模型

2.模型加载出错，世界已经生成
