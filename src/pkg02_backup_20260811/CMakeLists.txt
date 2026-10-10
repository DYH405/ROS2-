cmake_minimum_required(VERSION 3.8)
project(pkg02_backup_20260811)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
#添加include需要再cmake中添加find_package函数
#-std_msgs第一个添加点
find_package(std_msgs REQUIRED)
find_package(example_interfaces REQUIRED)
find_package(rclcpp_action REQUIRED)



#//统一放置节点名称
set(NODE_NAMES
  node01_backup
  node02_talker
  node03_listener
  node04_client
  node05_server
  node06_action_server
  node07_action_client
  person_cpp
)
#//创建循环所有节点
foreach(NODE_NAME ${NODE_NAMES})
  add_executable(${NODE_NAME} src/${NODE_NAME}.cpp)
  target_include_directories(${NODE_NAME} PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
  target_compile_features(${NODE_NAME} PUBLIC c_std_99 cxx_std_17)
  ament_target_dependencies(${NODE_NAME}
    "rclcpp"
    #-std_msgs第一个添加点
    "std_msgs"
    "example_interfaces"
    "rclcpp_action"
  )
endforeach()



#add_executable(node01_backup src/node01_backup.cpp)
###添加node02_talker节点-第一个添加点
#add_executable(node02_talker src/node02_talker.cpp)

#target_include_directories(node01_backup  PUBLIC
#  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
#  $<INSTALL_INTERFACE:include>)
###添加node02_talker节点-第二个添加点
#target_include_directories(node02_talker  PUBLIC
#  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
#  $<INSTALL_INTERFACE:include>)
###添加node01_backup节点-第三个添加点
#target_compile_features(node01_backup PUBLIC c_std_99 cxx_std_17)  # Require C99 and C++17
#target_compile_features(node02_talker PUBLIC c_std_99 cxx_std_17)
###添加node02_talker节点-第四个添加点
#ament_target_dependencies(node01_backup "rclcpp" #-std_msgs第二个添加点 
#"std_msgs")
#ament_target_dependencies(node02_talker "rclcpp" #-std_msgs第三个添加点
#  "std_msgs")
#添加node02_talker节点-第五个添加点
install(TARGETS ${NODE_NAMES} 
  DESTINATION lib/${PROJECT_NAME})
  
#添加launch文件
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})



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
