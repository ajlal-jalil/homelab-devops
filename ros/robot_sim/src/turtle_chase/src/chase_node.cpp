// chase_node.cpp
//
// A ROS 2 node that drives a robot toward a goal coordinate by:
//   1. Subscribing to /odom (the robot's current pose)
//   2. Computing the distance and direction to the goal
//   3. Publishing /cmd_vel commands (velocity to the wheels)
// Until the goal is reached.

// ----- Includes: pull in declarations from other headers -----

// std::chrono — for time durations like 100ms
#include <chrono>
// std::sqrt and std::atan2 — math functions
#include <cmath>
// std::shared_ptr and std::make_shared — smart pointers
#include <memory>

// ROS 2 C++ client library — gives us rclcpp::Node, publishers, etc.
#include "rclcpp/rclcpp.hpp"
// Twist message type (linear + angular velocity)
#include "geometry_msgs/msg/twist.hpp"
// Odometry message type (pose + velocity)
#include "nav_msgs/msg/odometry.hpp"

// "using namespace" lets us write `100ms` instead of
// `std::chrono::milliseconds(100)`. The `_literals` are tag types
// that turn 100ms into a chrono duration.
using namespace std::chrono_literals;


// Our node class. It inherits from rclcpp::Node, which gives us
// publishers, subscribers, timers, parameters, logging — for free.
class ChaseNode : public rclcpp::Node {
 public:
    // Constructor: runs once when the node is created.
    // We pass "chase_node" up to the Node base class as the node name.
    ChaseNode() : Node("chase_node") {
        // ----- Parameters -----
        // Declare parameters with default values. These can be overridden
        // at runtime via launch files or command line, without recompiling.
        this->declare_parameter<double>("goal_x", 2.0);
        this->declare_parameter<double>("goal_y", 0.0);
        this->declare_parameter<double>("linear_speed", 0.2);
        this->declare_parameter<double>("position_tolerance", 0.1);

        // Read the parameter values into member variables.
        // .as_double() converts the parameter value to a double.
        goal_x_ = this->get_parameter("goal_x").as_double();
        goal_y_ = this->get_parameter("goal_y").as_double();
        linear_speed_ = this->get_parameter("linear_speed").as_double();
        tolerance_ = this->get_parameter("position_tolerance").as_double();

        // ----- Publisher -----
        // create_publisher<MessageType>("topic_name", queue_depth)
        // Queue depth = how many messages to buffer if subscribers are slow.
        cmd_vel_pub_ = this->create_publisher<geometry_msgs::msg::Twist>(
            "cmd_vel", 10);

        // ----- Subscriber -----
        // create_subscription<MessageType>("topic", queue, callback)
        // std::bind builds a "callable" that invokes our on_odom method
        // on `this` instance, passing through the message argument.
        // std::placeholders::_1 means "first argument from the caller".
        odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
            "odom", 10,
            std::bind(&ChaseNode::on_odom, this, std::placeholders::_1));

        // ----- Timer -----
        // Fires every 100ms (10 Hz) and calls control_step.
        // This is the heartbeat of our control loop.
        timer_ = this->create_wall_timer(
            100ms, std::bind(&ChaseNode::control_step, this));

        // RCLCPP_INFO is a logging macro that integrates with ROS's
        // logging system. Logs appear in the terminal AND can be
        // captured by ros2 bag.
        RCLCPP_INFO(this->get_logger(),
                    "ChaseNode started. Goal: (%.2f, %.2f)",
                    goal_x_, goal_y_);
    }

 private:
    // Called every time a new Odometry message arrives on /odom.
    // SharedPtr<const Message> is the canonical type for ROS callbacks.
    void on_odom(const nav_msgs::msg::Odometry::SharedPtr msg) {
        // Extract the position from the message and store it on `this`.
        current_x_ = msg->pose.pose.position.x;
        current_y_ = msg->pose.pose.position.y;
        odom_received_ = true;
    }

    // Called every 100ms by the timer.
    void control_step() {
	// Don't act until we know where we are.
	if (!odom_received_) {
	    return;
	}

	// Compute distance to goal using Pythagorean theorem.
	const double dx = goal_x_ - current_x_;
	const double dy = goal_y_ - current_y_;
	const double distance = std::sqrt(dx * dx + dy * dy);

	// Build the velocity command. Defaults to all zeros.
	auto cmd = geometry_msgs::msg::Twist()
	
	if (distance < tolerance_) {
	    // We're at the goal. Publish zeros to stop.
	    cmd.linear.x = 0.0;
	    cmd.angular.z = 0.0;
	    // Log success exactly once.
	    if (!goal_announced_) {
	        RCLCPP_INFO(this->get_logger(),
			    "Goal reached at (%.2f, %.2f)",
			    current_x_, current_y);
		goal_announced_ = true;
	    }
	} else {
	    // Drive forward at linear_speed_.
	    cmd.linear.x = linear_speed_;
	    // Steer toward the goal: atan2 gives the angle in radians
	    // from the robot's frame. Multiply by a gain (0.5) to
	    // smooth out the turn.
	    cmd.angular.z = std::atan2(dy, dx) * 0.5;
	}
	cmd_vel_pub_->publish(cmd);
    }

    // ----- Member variables (state of the node) -----
    // The trailing underscore is a convention: easy to tell a member
    // variable from a local variable at a glance.
    
    // Smart pointers to the publisher, subscriber, timer.
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_pub_;
    rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
    rclcpp::TimerBase::SharedPtr timer_;

    // Configuration (set from parameters, never modified after consruction).
    double goal_x_;
    double goal_y_;
    double linear_speed_;
    double tolerance_;

    // Runtime state.
    double current_x_ = 0.0;
    double current_y_ = 0.0;
    double odom_received_ = false;
    double goal_announced_ = false;
};


// Standard ROS 2 main function pattern.
int main(int argc, char** argv) {
    // Initialize the rclcpp library. Must be called before creating nodes.
	rclcpp::init(argc, argv);

	// make_shared<ChaseNode>() creates a ChaseNode and returns a shared_ptr.
	// spin() runs the event loop until the node is shut down.
	rclcpp::spin(std::make_shared<ChaseNode>());

	// Clean up.
	rclcpp::shutdown();
	return 0;
}
