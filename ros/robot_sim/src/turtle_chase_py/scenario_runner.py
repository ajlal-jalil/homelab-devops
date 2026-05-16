"""
scenario_runner.py - the test harness for our robot scenario.

This Python ROS 2 node:
    1. Connects to the running simulator via ROS topics
    2. Watches the robot's odometry to detect goal arrival
    3. Records every relevant message to a ROS 2 bag for debuggability
    4. Writes a JUnit XML test report so CI can render pass/fail
    5. Exits with code 0 on success and 1 on timeout

Usage:
    ros2 run turtle_chase_py scenario_runner

Reads its configuration from constants below - for a real production
system you'd parametrize these via ROS parameters.
"""

# ----- Standard library imports -----

# math: trigonometry and sqrt
import math
# os: filesystem operations (mkdir, getsize)
import os
# subprocess: launch external commands like 'ros2 bag record'
import subprocess
# sys: program exit codes
import sys
# time: monotonix time for timeouts
import time
# datetime: human-readable timestamps for the JUnit report
from datetime import datetime
# xml.etree.ElementTree: write structutred XML
from xml.etree.ElementTree import Element, SubElement, ElementTree

# ----- ROS 2 imports -----

#rclpy: ROS 2 Python client library
import rclpy
# Node: the base class - same role as rclcpp::Node in C++
from rclpy.node import Node
#Odometry message - same structure as in C++, just a different language binding
from nav_msgs.msg import Odometry


# ----- Configuration constants -----
# Centralized at the top so they're easy to find and tweak.

GOAL_X = 2.0                # meters
GOAL_Y = 0.0
TOLERANCE = 0.15            # meters; how close before "reached"
TIMEOUT_SECONDS = 60        # how long to wait before declaring failure

# These paths point inside the container. The Kubernetes Job mounts a
# PersistentVolumeClaim at /artifacts so we can survive pod death.
BAG_DIR = "/artifacts/scenario_bag"
RESULT_FILE = "/artifacts/test_results.xml"


class ScenarioRunner(Node):
    """A ROS node that observes /odom and signals when the goal is reached."""

    def __init__(self):
        # Call the parent (Node) constructor, passing our node name.
        # Equivalent to C++'s ': Node("scenario_runner")' initializer list.
        super().__init__('scenario_runner')

        # Subscribe to /odom. The signature is:
        #   create_subscription(message_type, topic_name, callback, queue_size)
        # Notice we pass the unbound method 'sel.on_odom' - Python
        # automatically binds 'self' for you. Cleaner than C++'s std::bind.
        self.subscription = self.create_subscription(
            Odometry, 'odom', self.on_odom, 10)

        # Mutable state lives on 'self' (the instance).
        self.current_x = None         # None = "no data yet"
        self.current_y = None
        self.start_time = time.time() # seconds since epoch
        self.goal_reached = False
        self.goal_reached_at = None

    def on_odom(self, msg):
        """Callback: runs whenever a new /dom message arrives."""
        # Extract the position from the deply nested message structure.
        # msg.pose is a PoseWithCovariance.
        # msg.pose.pose is a Pose.
        # msg.pose.pose.position is a Point with x, y, z.
        self.current_x = msg.pose.pose.position.x
        self.current_y = msg.pose.pose.position.y

        # If we haven't already declared success, check distance.
        if not self.goal_reached:
            dx = GOAL_X - self.current_x
            dy = GOAL_Y - self.current_y
            distance = math.sqrt(dx * dx + dy * dy)
            if distance < TOLERANCE:
                self.goal_reached = True
                self.goal_reached_at = time.time() - self.start_time
                # ROS-aware logging - appears in pod logs AND can be
                # captured by ros2 bag.
                self.get_logger().info(
                    f'Goal reached after {self.goal_reached_at:.2f}s')

    def timed_out(self):
        """True if we've been running longer than the budget."""
        return time.time() - self.start_time > TIMEOUT_SECONDS


def write_junit(passed: bool, duration: float, message: str):
    """Write a minimal JUnit XML report.

    JUnit XML is the de factor test result format. CI systems
    (GitHub Actions, Jenkins, GitLab) parse it natively and render a
    pretty pass/fail UI. By writing it from a robotics test, we get
    that UI for free.

    Type hints (the ': bool', ': float', ': str') tell readers and
    static analyzers what types each parameter expects. They don't
    affect runtime behavior.
    """
    # Make sure the directory exists. exist_ok=True means "don't error
    # if it's already there."
    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)

    # Build the XML tree as a series of nested elements.
    testcase = Element('testsuite', {
        'name': 'turtle_chase.scenario',
        'tests': '1',
        'failures': '0' if passed else '1',
        'time': f'{duration:.2f}',
        'timestamp': datetime.utcnow().isoformat(),
    })
    if not passed:
        # Failures get a <failure> child element.
        failure = SubElement(testcase, 'failure', {
            'message': message,
            'type': 'AssertionError',
        })
        failure.text = message

    # Write the tree to disk as XML.
    ElementTree(testsuite).write(
            RESULT_FILE, encoding='utf-8', xml_declaration=True)


def main():
    """ Entry point - registered in setup.py as 'scenario_runner'."""
    # Initialize ROS 2. Must be called before creating any nodes.
    rclpy.init()
    runner = ScenarioRunner()

    # ----- Start the bag recorder as a background subprocess -----
    # Make the artifacts directory.
    os.makedirs(os.path.dirname(BAG_DIR), exist_ok=True)
    # Popen launches the process and returns immediately (non-blocking).
    # We discard stdout/stderr because they're noisy and we'll see
    # everything we care about in the bag file itself.
    bag_proc = subprocess.Popen(
        ['ros2', 'bag', 'record', '-o', BAG_DIR,
         '/odom', '/cmd_vel', '/scan'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    runner.get_logger().info('Scenario started. waiting for goal...')
    try:
        # The main spin loop. spin_once does one pass through the
        # event loop with a timeout, so we can also check our own
        # exit conditions between calls.
        while rclpy.ok():
            rclpy.spin_once(runner, timeout_sec=0.1)
            if runner.goal_reached or runner.timed_out():
                break
    finally:
        # 'finally' runs whether we exited normall, via exception, or
        # via Ctrl-C. We always want to stop the bag recorder, otherwise
        # the bag file stays partially open and unreadable.
        bag_proc.terminate()
        try:
            bag_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            bag_proc.kill()

    duration = time.time() - runner.start_time

    # Branch on success vs failure. Both write a JUnit report.
    if runner.goal_reached:
        msg = f'Goal reached at t={runner.goal_reached_at:.2f}s'
        runner.get_logger().info(msg)
        write_junit(passed=True, duration=duration, message=msg)
        rc = 0
    else:
        msg = (f'Timeout: did not reach ({GOAL_X}, {GOAL_Y}) within'
               f'{TIMEOUT_SECONDS}s. Last position: '
               f'({runner.current_x}, {runner.current_y})')
        runner.get_logger().error(msg)
        write_junit(passed=False, duration=duration, message=msg)
        rc = 1

    # Clean shutdown - destroy the node, then shut down the rclpy library.
    runner.destroy_node()
    rclpy.shutdown()

    # Exit with appropriate code so CI can detect pass/fail
    sys.exit(rc)


# Standard Python idiom: only run main() if this file is executed
# directly (not imported). when ros2 run invokes us via the entry_point,
# this is what runs.
if __name__ == __main__':
    main()
