# CMakeLists.txt tells CMake how to build this C++ package

# Minimum CMake version. 3.8 is the floor for ROS 2 Humble
cmake_minimum_required(VERSION 3.8)
project(turtle_chase)

# Set the C++ standard. C++17 is widely used in ROS 2 code.
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

# Enable strict compiler warnings on GCC and CLang.
# -Wall: most warnings, -Wextra:more, -Wpedantic: standards_strict.
# Catching warnings early prevents bugs.
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies declared in package.xml
# REQUIRED means "fail the build if not found."
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)

# Link the executable against the ROS dependencies it needs.
# ament_target_dependencies handles include paths AND linker flags
# in one call - much simpler than vanilla CMake's two-step process.
ament_target_dependencies(chase_node
  rclcpp
  geometry_msgs
  nav_msgs
)

# Install the binary so other code can find it via "ros2 run".
install(TARGETS chase_node
  DESTINATION lib/${PROJECT_NAME})

# Install launch and config files.
install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME})

# If tests are enabled, run linters automatically.
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

# Generate the package files that ament_cmake needs.
# This MUST be the last call in the file.
ament_package()
