# Multi-stage Dockerfile for the turtle_chase ROS 2 workspace.
#
# Stage 1: build — compile the C++ and install Python with full ROS toolchain.
# Stage 2: runtime — same base image (we need ROS at runtime too) but copy
# only the install/ tree from the build stage. This keeps the image
# reasonably small and the layers cached when only application code changes.

FROM osrf/ros:humble-desktop AS build

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    python3-colcon-common-extensions \
    python3-rosdep \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up workspace
WORKDIR /workspace
COPY src/ src/

# Use rosdep to install ROS dependencies declared in package.xml
# (rosdep is already initialized in the osrf/ros base image)
RUN apt-get update && \
    rosdep install --from-paths src --ignore-src -r -y && \
    rm -rf /var/lib/apt/lists/*

# Build with colcon — the install/ tree is what we'll copy out
RUN . /opt/ros/humble/setup.sh && \
    colcon build --merge-install \
                 --cmake-args -DCMAKE_BUILD_TYPE=Release

# ---------- runtime stage ----------
FROM osrf/ros:humble-desktop AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# Gazebo + TurtleBot3 simulation packages
# These pull in the simulator, the robot model, and the navigation stack
RUN apt-get update && apt-get install -y \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-turtlebot3 \
    ros-humble-turtlebot3-simulations \
    ros-humble-turtlebot3-gazebo \
    ros-humble-rosbag2 \
    ros-humble-rosbag2-storage-default-plugins \
    && rm -rf /var/lib/apt/lists/*

# Copy our compiled workspace from the build stage
COPY --from=build /workspace/install /workspace/install

# TurtleBot3 needs this env var set to pick a model variant
ENV TURTLEBOT3_MODEL=burger

# Source ROS and our workspace on every shell invocation
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /workspace/install/setup.bash" >> /root/.bashrc

# Default to a shell — the Kubernetes Job will override CMD
CMD ["/bin/bash"]
