import os
import time
import json
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List
from configs import BACKEND_INTERNAL_CONFIG, NXS_BACKEND_CONFIG, NXS_CONFIG
from nxs_types.infer import NxsInferRequestMetadata
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.model import NxsModel
from nxs_types.scheduling_data import NxsSchedulingPerComponentModelPlan
from nxs_libs.interface.backend.input import (
    BackendInputInterface,
    BackendInputInterfaceFactory,
    BackendInputInterfaceType,
)
from nxs_libs.interface.backend.output import (
    BackendOutputInterface,
    BackendOutputInterfaceFactory,
    BackendOutputInterfaceType,
)
from nxs_utils.logging import NxsLogLevel, write_log
from main_processes.backend.compute_process import BackendComputeProcess

import tensorflow.compat.v1 as tf

tf.disable_v2_behavior()


class BackendComputeProcessTfv1(BackendComputeProcess):
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        model_path: str,
        use_gpu: bool,
        transforming_fn_path: str,
        input_interface_args_list: List[Dict],
        output_interface_args: Dict,
        allow_infer_flag,
        stop_flags,
        next_process_stop_flag,
        extra_params: Dict = ...,
    ) -> None:
        super().__init__(
            args,
            component_model,
            component_model_plan,
            model_path,
            use_gpu,
            transforming_fn_path,
            input_interface_args_list,
            output_interface_args,
            allow_infer_flag,
            stop_flags,
            next_process_stop_flag,
            extra_params=extra_params,
        )

    def _load_model(self) -> None:
        tf_graph = tf.Graph()

        if not self.use_gpu:
            tf_config = tf.ConfigProto()
        else:
            import GPUtil

            tf_config = tf.ConfigProto()
            tf_config.gpu_options.allow_growth = True
            max_gpu_usage = 0
            for profile_unit in self.component_model.profile:
                if profile_unit.batch_size <= self.component_model_plan.batch_size:
                    max_gpu_usage = max(max_gpu_usage, profile_unit.gpu_mem_usage)

            gpu = GPUtil.getGPUs()[0]

            tf_config.gpu_options.per_process_gpu_memory_fraction = (
                float(max_gpu_usage) / gpu.memoryTotal
            )

        tf_config.gpu_options.allow_growth = True

        with tf.gfile.GFile(self.model_path, "rb") as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())

        with tf_graph.as_default() as graph:
            tf.import_graph_def(graph_def, name="")

        tf_sess = tf.Session(graph=tf_graph, config=tf_config)
        input_tensors_dict = {}
        output_tensors = []
        for model_input in self.component_model.model_desc.inputs:
            input_tensors_dict[model_input.name] = tf_graph.get_tensor_by_name(
                model_input.name + ":0"
            )
        for model_output in self.component_model.model_desc.outputs:
            output_tensors.append(tf_graph.get_tensor_by_name(model_output.name + ":0"))

        self.tf_sess = tf_sess
        self.input_tensors_dict = input_tensors_dict
        self.output_tensors = output_tensors

    def _infer(self, feed_dict: Dict, output_tensor_names: List[str]) -> List:
        input_dict = {}

        for input_name in self.input_tensors_dict:
            input_dict[self.input_tensors_dict[input_name]] = feed_dict[input_name]

        return self.tf_sess.run(self.output_tensors, feed_dict=input_dict)

    def request_entering(self, extra_metadata: Dict):
        extra_metadata[self.component_model.model_uuid]["model_t0"] = time.time()

    def request_exiting(self, extra_metadata: Dict):
        model_t0 = extra_metadata[self.component_model.model_uuid].pop("model_t0")
        extra_metadata[self.component_model.model_uuid]["model_lat"] = (
            time.time() - model_t0
        )
