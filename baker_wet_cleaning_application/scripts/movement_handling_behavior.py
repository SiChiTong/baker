#!/usr/bin/env python

import rospy
from geometry_msgs.msg import PoseStamped, Pose2D, Point32, Quaternion

import cv2
import numpy as np
from cv_bridge import CvBridge, CvBridgeError
import std_srvs.srv
import dynamic_reconfigure.client

import behavior_container
import move_base_behavior
import room_exploration_behavior
import move_base_path_behavior
import trolley_movement_behavior
import tool_changing_behavior

class MovementHandlingBehavior(behavior_container.BehaviorContainer):

	#========================================================================
	# Description:
	# Handles the wet cleanig process (i.e. Floor cleaning, Trashcan)
	# for all rooms provided in a given list
	#========================================================================
	# Serivces to be used:
	# room_exploration_service_str_ = 
	#       '/room_exploration_server'
	# move_base_path_service_str_ =
	#		'/move_base_path'
	# move_base_wall_follow_service_str_ =
	#		'/move_base_wall_follow'
	# move_base_service_str_ =
	#		'move_base'
	#========================================================================

		
	# Method for setting parameters for the behavior
	def setParameters(self, database_handler, segmented_map, room_information_in_meter, sequence_data, robot_frame_id):
		# Parameters set from the outside
		self.database_handler_= database_handler
		self.segmented_map_ = segmented_map
		self.sequence_data_ = sequence_data
		# Parameters set autonomously
		self.room_exploration_service_str_ = '/room_exploration/room_exploration_server'
		self.move_base_path_service_str_ = '/move_base_path'
		self.move_base_wall_follow_service_str_ = '/move_base_wall_follow'
		self.move_base_service_str_ = 'move_base'
		self.start_cleaning_service_str_ = '/brush_cleaning_module_interface/start_brush_cleaner'
		self.stop_cleaning_service_str_ = '/brush_cleaning_module_interface/stop_brush_cleaner'
		self.coverage_monitor_dynamic_reconfigure_service_str_ = '/room_exploration/coverage_monitor_server'
		self.stop_coverage_monitoring_service_str_ = "/room_exploration/coverage_monitor_server/stop_coverage_monitoring"
		self.trolley_movement_service_str_ = ""
		self.tool_changing_service_str_ = ""
		self.robot_radius_ = self.database_handler_.database_.robot_properties_.exploration_robot_radius_
		self.coverage_radius_ = self.database_handler_.database_.robot_properties_.exploration_coverage_radius_
		self.field_of_view_ = self.database_handler_.database_.robot_properties_.exploration_field_of_view_
		
		# DEPRECATED Use database handler
		self.room_information_in_meter_ = room_information_in_meter
		self.robot_frame_id_ = robot_frame_id
		# Get a opencv representation of the segmented image
		self.bridge_ = CvBridge()
		self.opencv_segmented_map_ = self.bridge_.imgmsg_to_cv2(self.segmented_map_, desired_encoding = "passthrough")

	# Method for returning to the standard pose of the robot
	def returnToRobotStandardState(self):
		# save current data if necessary
		# undo or check whether everything has been undone
		pass

	# Implemented Behavior
	def executeCustomBehavior(self):
		self.move_base_handler_ = move_base_behavior.MoveBaseBehavior("MoveBaseBehavior", self.interrupt_var_, self.move_base_service_str_)
		self.room_explorer_ = room_exploration_behavior.RoomExplorationBehavior("RoomExplorationBehavior", self.interrupt_var_, self.room_exploration_service_str_)
		self.path_follower_ = move_base_path_behavior.MoveBasePathBehavior("MoveBasePathBehavior_PathFollowing", self.interrupt_var_, self.move_base_path_service_str_)
		self.wall_follower_ = move_base_path_behavior.MoveBasePathBehavior("MoveBasePathBehavior_WallFollowing", self.interrupt_var_, self.move_base_wall_follow_service_str_)
		self.trolley_mover_ = trolley_movement_behavior.TrolleyMovementBehavior("TrolleyMovementBehavior", self.interrupt_var_, self.trolley_movement_service_str_)
		self.tool_changer_ = tool_changing_behavior.ToolChangingBehavior("ToolChangingBehavior", self.interrupt_var_, self.tool_changing_service_str_)



		# TOOL CHANGE ACCORDING TO CLEANING TASK
		# ======================================

		self.tool_changer_.setParameters(self.database_handler_)
		self.tool_changer_.executeBehavior()

		for current_checkpoint_index in range(len(self.sequence_data_.checkpoints)):



			# TROLLEY MOVEMENT TO CHECKPOINT
			# ==============================

			self.trolley_mover_.setParameters(self.database_handler_)
			self.trolley_mover.executeBehavior()


			for current_room_index in self.sequence_data_.checkpoints[current_checkpoint_index].room_indices:


				# HANDLING OF SELECTED ROOM
				# =========================


				self.printMsg("Moving to next room with current_room_index = " + str(current_room_index))

				# Interruption opportunity
				if self.handleInterrupt() == 2:
					return

				# Room exploration
				"""
				For room exploration:
				input_map = self.getMapSegmentAsImageMsg(current_room_index)
				map_resolution = self.database_handler_.database_.global_map_data_.map_resolution_
				map_origin = self.database_handler_.database_.global_map_data_.map_origin_
				robot_radius = 0.325
				coverage_radius = 0.25
				field_of_view = [Point32(x=0.04035, y=0.136), Point32(x=0.04035, y=-0.364), Point32(x=0.54035, y=-0.364), Point32(x=0.54035, y=0.136)] # this field of view represents the off-center iMop floor wiping device
				starting_position = Pose2D(x=1., y=0., theta=0.)
				planning_mode = 2
				"""
				current_room_center = self.room_information_in_meter_[current_room_index].room_center
				current_room_map = self.getMapSegmentAsImageMsg(self.opencv_segmented_map_, current_room_index)
				self.room_explorer_.setParameters(
					current_room_map,
					self.database_handler_.database_.global_map_data_.map_resolution_,
					self.database_handler_.database_.global_map_data_.map_origin_,
					robot_radius = self.robot_radius_,
					coverage_radius = self.coverage_radius_,
					field_of_view = self.field_of_view_,		# this field of view represents the off-center iMop floor wiping device
					starting_position = Pose2D(x=current_room_center.x, y=current_room_center.y, theta=0.),	# todo: determine current robot position
					planning_mode = 2
				)
				self.room_explorer_.executeBehavior()

				# If no trajectory was created - move on to next room
				if (self.room_explorer_.exploration_result_ == None):
					continue
			
				# Interruption opportunity
				if self.handleInterrupt() == 2:
					return

				#rospy.sleep(20)
				#continue

				# Robot movement into next room
				"""
				For movement to room:
				goal_position = self.segmentation_data_.room_information_in_meter[current_room_index].room_center
				goal_orientation = Quaternion(x=0., y=0., z=0., w=0.)
				header_frame_id = 'base_link'
				"""
				self.printMsg("Moving to room_center in meter=" + str(self.room_information_in_meter_[current_room_index].room_center))
				self.move_base_handler_.setParameters(
					self.room_information_in_meter_[current_room_index].room_center,
					Quaternion(x=0., y=0., z=0., w=0.),	# todo: normalized quaternion
					'base_link'
				)
				self.move_base_handler_.executeBehavior()
			
				# Interruption opportunity
				if self.handleInterrupt() == 2:
					return
			
				# baker_brush_cleaning_module_interface: turn on the cleaning device (service "start_brush_cleaner")
				'''
				self.printMsg("Start cleaning with " + self.start_cleaning_service_str_)
				rospy.wait_for_service(self.start_cleaning_service_str_) 
				try:
					req = rospy.ServiceProxy(self.start_cleaning_service_str_, std_srvs.srv.Trigger)
					resp = req()
					print "Start cleaning returned with success status " + str(resp.success)
				except rospy.ServiceException, e:
					print "Service call to " + self.start_cleaning_service_str_ + " failed: %s" % e
				'''
			
				# coverage_monitor_server: set the robot configuration (robot_radius, coverage_radius, coverage_offset) with dynamic reconfigure
				#                          and turn on logging of the cleaned path (service "start_coverage_monitoring")
				try:
					print "Calling dynamic reconfigure at the coverage_monitor_server to set robot radius, coverage_radius, and coverage offset and start coverage monitoring."
					client = dynamic_reconfigure.client.Client(self.coverage_monitor_dynamic_reconfigure_service_str_, timeout=5)
					rospy.wait_for_service(self.coverage_monitor_dynamic_reconfigure_service_str_ + "/set_parameters")
					client.update_configuration({"map_frame":self.database_handler_.database_.global_map_data_.map_header_frame_id_, "robot_frame":self.robot_frame_id_,
												"coverage_radius":self.coverage_radius_,
												"coverage_circle_offset_transform_x":0.5*(self.field_of_view_[0].x+self.field_of_view_[2].x),
												"coverage_circle_offset_transform_y":0.5*(self.field_of_view_[0].y+self.field_of_view_[1].y),
												"coverage_circle_offset_transform_z":0.0,
												"robot_trajectory_recording_active":True})
				except rospy.ServiceException, e:
					print "Dynamic reconfigure request to " + self.coverage_monitor_dynamic_reconfigure_service_str_ + " failed: %s" % e
			
				# Explored path follow
				"""
				For path follow movement:
				target_poses = exploration_result.coverage_path_pose_stamped
				area_map = current_room_map
				path_tolerance = 0.2
				goal_position_tolerance = 0.5
				goal_angle_tolerance = 1.57
				"""
				self.path_follower_.setParameters(
					self.room_explorer_.exploration_result_.coverage_path_pose_stamped,
					current_room_map,
					0.2,
					0.5,
					1.57
				)
				self.path_follower_.executeBehavior()
			
				# Interruption opportunity
				if self.handleInterrupt() == 2:
					return

				# Wall follow
				"""
				For wall following movement:
				target_poses = exploration_result.coverage_path_pose_stamped
				path_tolerance = 0.2
				goal_position_tolerance = 0.4
				goal_angle_tolerance = 3.14
				"""
				'''
				self.wall_follower_.setParameters(
					self.room_explorer_.exploration_result_.coverage_path_pose_stamped,
					current_room_map,
					0.2,
					0.4,
					3.14
				)
				self.wall_follower_.executeBehavior()
				'''
			
				# Interruption opportunity
				if self.handleInterrupt() == 2:
					return

				# Mark the current room as finished
				#self.database_handler_.checkoutCompletedRoom(self.database_handler_.due_rooms_cleaning_[self.sequence_data_.checkpoints[current_checkpoint_index].room_indices[current_room_index]], False, False)
				self.database_handler_.checkoutCompletedRoom(self.database_handler_.getRoomFromSequencingResult(self.sequencing_result_, current_checkpoint_index, current_room_index), 1)
				
				# coverage_monitor_server.cpp: turn off logging of the cleaned path (service "stop_coverage_monitoring")
				self.printMsg("Stop coverage monitoring with " + self.stop_coverage_monitoring_service_str_)
				rospy.wait_for_service(self.stop_coverage_monitoring_service_str_) 
				try:
					req = rospy.ServiceProxy(self.stop_coverage_monitoring_service_str_, std_srvs.srv.Trigger)
					resp = req()
					print "Stop coverage monitoring returned with success status " + str(resp.success)
				except rospy.ServiceException, e:
					print "Service call to " + self.stop_coverage_monitoring_service_str_ + " failed: %s" % e
			
				'''
				# baker_brush_cleaning_module_interface: turn off the cleaning device (service "stop_brush_cleaner")
				self.printMsg("Stop cleaning with " + self.stop_cleaning_service_str_)
				rospy.wait_for_service(self.stop_cleaning_service_str_) 
				try:
					req = rospy.ServiceProxy(self.stop_cleaning_service_str_, std_srvs.srv.Trigger)
					resp = req()
					print "Stop cleaning returned with success status " + str(resp.success)
				except rospy.ServiceException, e:
					print "Service call to " + self.stop_cleaning_service_str_ + " failed: %s" % e
				'''



	# Method for returning the segment of the map corresponding to the order number as cv_bridge
	def getMapSegmentAsImageMsg(self, opencv_segmented_map, current_room_index):
		self.printMsg("Creating room map for room " + str(current_room_index))
		image_height, image_width = opencv_segmented_map.shape
		tmp_map_opencv = np.zeros((image_height, image_width), np.uint8)
		for x in range(image_width):
			for y in range(image_height):
				if (opencv_segmented_map[y, x] == current_room_index + 1):
					tmp_map_opencv[y, x] = 255
					# print "%i %i %i" % (self.opencv_segmented_map_[y, x], x, y)
		return self.bridge_.cv2_to_imgmsg(tmp_map_opencv, encoding = "mono8")
