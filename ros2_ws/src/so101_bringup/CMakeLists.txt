cmake_minimum_required(VERSION 3.8)
project(so101_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch worlds
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/so101_follower_driver.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
