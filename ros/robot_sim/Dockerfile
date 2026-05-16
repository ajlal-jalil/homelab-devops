# ===== STAGE 1: BUILD =====
# Use the full ROS 2 Humble desktop image, which includes the build
# toolchain (gcc, cmake, etc.) and ROS development libraries.
FROM osrf/ros:humble-desktop AS build

# Don't prompt for input during apt operations. Required in CI.
ENV DEBIAN_FRONTEND=noninteractive

# Install the ROS-specific build tooling.
# colcon: the build orchestrator (runs CMake for each package)
# rosdep: installs ROS package dependencies declared in package.xml
# build-essential: gcc, make, basic C/C++ build chain
RUN apt-get update && apt-get install -y \
    python3-colcon-common-extensions \
    python3-rosdep \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up the workspace inside the container.
WORKDIR /workspace
# Copy our source tree (relative to the Dockerfile) into the container.
COPY src/ src/

# rosdep reads package.xml files and installs the apt packages they
# declare as dependencies. This is the "magic" that means we don't
# need to maintain a separate apt list — the package.xml IS the list.
RUN apt-get update && \
    rosdep install --from-paths src --ignore-src -r -y && \
    rm -rf /var/lib/apt/lists/*

# Source the ROS 2 environment, then build everything in the workspace.
# --merge-install puts all built artifacts in a single install/ tree
# (instead of one per package), which simplifies later sourcing.
# -DCMAKE_BUILD_TYPE=Release enables compiler optimizations.
RUN . /opt/ros/humble/setup.sh && \
    colcon build --merge-install \
                 --cmake-args -DCMAKE_BUILD_TYPE=Release


# ===== STAGE 2: RUNTIME =====
# Start fresh from the same base. We need ROS at runtime because our
# binaries dynamically link against ROS libraries.
FROM osrf/ros:humble-desktop AS runtime

ENV DEBIAN_FRONTEND=noninteractive

# Install simulator and TurtleBot3 packages.
# We didn't need these for building, only for running the simulation.
RUN apt-get update && apt-get install -y \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-turtlebot3 \
    ros-humble-turtlebot3-simulations \
    ros-humble-turtlebot3-gazebo \
    ros-humble-rosbag2 \
    ros-humble-rosbag2-storage-default-plugins \
    && rm -rf /var/lib/apt/lists/*

# Copy ONLY the install/ tree from the build stage. We leave the
# build tooling and source code behind, keeping the runtime image lean.
COPY --from=build /workspace/install /workspace/install

# TurtleBot3 needs to know which model variant to use.
# "burger" is the smallest and simplest.
ENV TURTLEBOT3_MODEL=burger

# Source ROS and our workspace whenever bash starts.
# This is what `source` lines do — they set environment variables so
# `ros2 run` can find our binaries.
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /workspace/install/setup.bash" >> /root/.bashrc

# Default command — overridden by the Kubernetes Job's `command`/`args`.
CMD ["/bin/bash"]
