#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import shutil
import traceback

import yaml
from xml.etree import ElementTree as et
import time
from os import path
import numpy as np

from performance_modelling_py.utils import backup_file_if_exists, print_info, print_error
from performance_modelling_py.component_proxies.ros1_component import Component
from global_planning_performance_modelling_ros.metrics import compute_metrics


class BenchmarkRun(object):
    def __init__(self, run_id, run_output_folder, benchmark_log_path, environment_folder, parameters_combination_dict, benchmark_configuration_dict, show_ros_info, headless):
        """print("PRINTT:\n")
        print(run_id,'\n')
        print(run_output_folder,'\n')
        print(benchmark_log_path,'\n')
        print(environment_folder,'\n')
        print(parameters_combination_dict,'\n')
        print(benchmark_configuration_dict,'\n')
        print(show_ros_info,'\n')
        print(headless,'\n')"""

        # run configuration
        self.run_id = run_id
        self.run_output_folder = run_output_folder
        self.benchmark_log_path = benchmark_log_path
        self.run_parameters = parameters_combination_dict
        self.benchmark_configuration = benchmark_configuration_dict
        self.components_ros_output = 'screen' if show_ros_info else 'log'
        self.headless = headless

        # environment parameters
        self.environment_folder = environment_folder
        self.map_info_file_path = path.join(environment_folder, "data", "map.yaml")
        """self.gazebo_model_path_env_var = ":".join(map(
            lambda p: path.expanduser(p),
            self.benchmark_configuration['gazebo_model_path_env_var'] + [path.dirname(path.abspath(self.environment_folder)), self.run_output_folder]
        ))
        self.gazebo_plugin_path_env_var = ":".join(map(
            lambda p: path.expanduser(p),
            self.benchmark_configuration['gazebo_plugin_path_env_var']
        ))
        beta_1, beta_2, beta_3, beta_4 = self.run_parameters['beta']
        laser_scan_max_range = self.run_parameters['laser_scan_max_range']
        laser_scan_fov_deg = self.run_parameters['laser_scan_fov_deg']
        laser_scan_fov_rad = laser_scan_fov_deg*np.pi/180""" #closed gazebo part
        global_planner_name = self.run_parameters['global_planner_name']
        print(global_planner_name)

        # run variables
        self.aborted = False

        # prepare folder structure
        run_configuration_path = path.join(self.run_output_folder, "components_configuration")
        run_info_file_path = path.join(self.run_output_folder, "run_info.yaml")
        backup_file_if_exists(self.run_output_folder)
        os.mkdir(self.run_output_folder)
        os.mkdir(run_configuration_path)

        # components original configuration paths
        components_configurations_folder = path.expanduser(self.benchmark_configuration['components_configurations_folder'])
        original_supervisor_configuration_path = path.join(components_configurations_folder, self.benchmark_configuration['components_configuration']['supervisor'])
        original_move_base_configuration_path = path.join(components_configurations_folder, self.benchmark_configuration['components_configuration']['move_base'][global_planner_name])
        self.original_rviz_configuration_path = path.join(components_configurations_folder, self.benchmark_configuration['components_configuration']['rviz'])
        original_robot_urdf_path = path.join(environment_folder, "gazebo", "robot.urdf")
        #original_amcl_configuration_path = path.join(components_configurations_folder, self.benchmark_configuration['components_configuration']['amcl'])
        #original_gazebo_world_model_path = path.join(environment_folder, "gazebo", "gazebo_environment.model")
        #original_gazebo_robot_model_config_path = path.join(environment_folder, "gazebo", "robot", "model.config")
        #original_gazebo_robot_model_sdf_path = path.join(environment_folder, "gazebo", "robot", "model.sdf")                      #we are not using simulation right now
        

        # components configuration relative paths
        supervisor_configuration_relative_path = path.join("components_configuration", self.benchmark_configuration['components_configuration']['supervisor'])
        move_base_configuration_relative_path = path.join("components_configuration", self.benchmark_configuration['components_configuration']['move_base'][global_planner_name])
        robot_realistic_urdf_relative_path = path.join("components_configuration", "gazebo", "robot_realistic.urdf")
        #amcl_configuration_relative_path = path.join("components_configuration", self.benchmark_configuration['components_configuration']['amcl'])
        #gazebo_world_model_relative_path = path.join("components_configuration", "gazebo", "gazebo_environment.model")
        #gazebo_robot_model_config_relative_path = path.join("components_configuration", "gazebo", "robot", "model.config")
        #gazebo_robot_model_sdf_relative_path = path.join("components_configuration", "gazebo", "robot", "model.sdf")
        #robot_gt_urdf_relative_path = path.join("components_configuration", "gazebo", "robot_gt.urdf")                            #we are not using simulation right now
        

        # components configuration paths in run folder
        self.supervisor_configuration_path = path.join(self.run_output_folder, supervisor_configuration_relative_path)
        self.move_base_configuration_path = path.join(self.run_output_folder, move_base_configuration_relative_path)
        self.robot_realistic_urdf_path = path.join(self.run_output_folder, robot_realistic_urdf_relative_path)
        #self.amcl_configuration_path = path.join(self.run_output_folder, amcl_configuration_relative_path)
        #self.gazebo_world_model_path = path.join(self.run_output_folder, gazebo_world_model_relative_path)
        #gazebo_robot_model_config_path = path.join(self.run_output_folder, gazebo_robot_model_config_relative_path)
        #gazebo_robot_model_sdf_path = path.join(self.run_output_folder, gazebo_robot_model_sdf_relative_path)
        #self.robot_gt_urdf_path = path.join(self.run_output_folder, robot_gt_urdf_relative_path)                                  #we are not using simulation right now
        

        # copy the configuration of the supervisor to the run folder and update its parameters
        with open(original_supervisor_configuration_path) as supervisor_configuration_file:
            supervisor_configuration = yaml.load(supervisor_configuration_file)
        supervisor_configuration['run_output_folder'] = self.run_output_folder
        supervisor_configuration['pid_father'] = os.getpid()
        supervisor_configuration['ground_truth_map_info_path'] = self.map_info_file_path
        if not path.exists(path.dirname(self.supervisor_configuration_path)):
            os.makedirs(path.dirname(self.supervisor_configuration_path))
        with open(self.supervisor_configuration_path, 'w') as supervisor_configuration_file:
            yaml.dump(supervisor_configuration, supervisor_configuration_file, default_flow_style=False)

        # copy the configuration of move_base to the run folder
        if not path.exists(path.dirname(self.move_base_configuration_path)):
            os.makedirs(path.dirname(self.move_base_configuration_path))
        shutil.copyfile(original_move_base_configuration_path, self.move_base_configuration_path)

        # copy the configuration of the robot urdf to the run folder and update the link names for realistic data
        if not path.exists(path.dirname(self.robot_realistic_urdf_path)):
            os.makedirs(path.dirname(self.robot_realistic_urdf_path))
        shutil.copyfile(original_robot_urdf_path, self.robot_realistic_urdf_path)

        # write run info to file
        run_info_dict = dict()
        run_info_dict["run_id"] = self.run_id
        run_info_dict["run_folder"] = self.run_output_folder
        run_info_dict["environment_folder"] = environment_folder
        run_info_dict["run_parameters"] = self.run_parameters
        run_info_dict["local_components_configuration"] = {
            'supervisor': supervisor_configuration_relative_path,
            'move_base': move_base_configuration_relative_path,
            'robot_realistic_urdf': robot_realistic_urdf_relative_path,
            #'amcl': amcl_configuration_relative_path,
            #'gazebo_world_model': gazebo_world_model_relative_path,
            #'gazebo_robot_model_sdf': gazebo_robot_model_sdf_relative_path,
            #'gazebo_robot_model_config': gazebo_robot_model_config_relative_path,
            #'robot_gt_urdf': robot_gt_urdf_relative_path,
        }

        with open(run_info_file_path, 'w') as run_info_file:
            yaml.dump(run_info_dict, run_info_file, default_flow_style=False)

    def log(self, event):

        if not path.exists(self.benchmark_log_path):
            with open(self.benchmark_log_path, 'a') as output_file:
                output_file.write("timestamp, run_id, event\n")

        t = time.time()

        print_info("t: {t}, run: {run_id}, event: {event}".format(t=t, run_id=self.run_id, event=event))
        try:
            with open(self.benchmark_log_path, 'a') as output_file:
                output_file.write("{t}, {run_id}, {event}\n".format(t=t, run_id=self.run_id, event=event))
        except IOError as e:
            print_error("benchmark_log: could not write event to file: {t}, {run_id}, {event}".format(t=t, run_id=self.run_id, event=event))
            print_error(e)

    def execute_run(self):

        # components parameters
        rviz_params = {
            'rviz_config_file': self.original_rviz_configuration_path,
            'headless': self.headless,
        }
        state_publisher_param = {
            'robot_realistic_urdf_file': self.robot_realistic_urdf_path,
        }
        navigation_params = {
            'params_file': self.move_base_configuration_path,
            'map_file':self.map_info_file_path,
        }
        supervisor_params = {
            'params_file': self.supervisor_configuration_path,
        }
        #localization_params = {
        #    'params_file': self.amcl_configuration_path,
        #    'map': self.map_info_file_path,
        #}
        

        # declare components
        roscore = Component('roscore', 'global_planning_performance_modelling', 'roscore.launch')
        state_publisher = Component('state_publisher','global_planning_performance_modelling','robot_state_launcher.launch',state_publisher_param)
        rviz = Component('rviz', 'global_planning_performance_modelling', 'rviz.launch', rviz_params)
        navigation = Component('move_base', 'global_planning_performance_modelling', 'move_base.launch', navigation_params)
        supervisor = Component('supervisor', 'global_planning_performance_modelling', 'global_planning_benchmark_supervisor.launch', supervisor_params)
        #environment = Component('gazebo', 'global_planning_performance_modelling', 'gazebo.launch', environment_params)
        #recorder = Component('recorder', 'global_planning_performance_modelling', 'rosbag_recorder.launch', recorder_params)
        #localization = Component('amcl', 'global_planning_performance_modelling', 'amcl.launch', localization_params)
       
        # set gazebo's environment variables
        #os.environ['GAZEBO_MODEL_PATH'] = self.gazebo_model_path_env_var
        #os.environ['GAZEBO_PLUGIN_PATH'] = self.gazebo_plugin_path_env_var

        # launch components
        roscore.launch()
        rviz.launch()
        navigation.launch()
        supervisor.launch()
        #environment.launch()
        #recorder.launch()
        #localization.launch()
        
        # launch components and wait for the supervisor to finish
        self.log(event="waiting_supervisor_finish")
        supervisor.wait_to_finish()
        # localization.wait_to_finish()
        self.log(event="supervisor_shutdown")

        # shut down components
        navigation.shutdown()
        rviz.shutdown()
        roscore.shutdown()
        #localization.shutdown()
        #recorder.shutdown()
        #environment.shutdown()
        print_info("execute_run: components shutdown completed")

        # compute all relevant metrics and visualisations
        # noinspection PyBroadException
        try:
            self.log(event="start_compute_metrics")
            # compute_metrics(self.run_output_folder)
        except:
            print_error("failed metrics computation")
            print_error(traceback.format_exc())

        self.log(event="run_end")
        print_info("run {run_id} completed".format(run_id=self.run_id))
