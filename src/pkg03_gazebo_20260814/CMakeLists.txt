cmake_minimum_required(VERSION 3.8)
project(pkg03_gazebo_20260814)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(urdf REQUIRED)
find_package(xacro REQUIRED)

# config 必须一起 install：ekf_test.launch.py 通过 get_package_share_directory()
# 读取 install/ 下的 config/ekf.yaml，src/ 里的文件不会被运行时看到。
# 漏装这一项的表现是 EKF 节点启动即退出（报参数文件不存在），而不是报配置错误。
install(
  DIRECTORY 
  launch
  worlds
  urdf
  config
  DESTINATION share/${PROJECT_NAME}/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()