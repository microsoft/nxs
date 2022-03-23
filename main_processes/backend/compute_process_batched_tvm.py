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

import tvm
import tvm.contrib.graph_executor as rt


class BackendComputeProcessBatchedTvm(BackendComputeProcess):
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
        # the model_path should be a zip file
        import shutil

        base_dir_path = os.path.dirname(self.model_path)
        self.tvm_modules_dir = os.path.join(base_dir_path, "tvm_modules")

        if not os.path.exists(self.tvm_modules_dir):
            os.makedirs(self.tvm_modules_dir)

        shutil.unpack_archive(self.model_path, self.tvm_modules_dir, format="zip")

        if not self.use_gpu:
            self.ctx = tvm.cpu()
        else:
            self.ctx = tvm.cuda()

        self.module_dict = {}

        for profile_unit in self.component_model.profile:
            bs = profile_unit.batch_size
            if bs <= self.max_batch_size:
                module_path = os.path.join(self.tvm_modules_dir, f"bs_{bs}.so")
                lib = tvm.runtime.load_module(module_path)
                self.module_dict[bs] = rt.GraphModule(lib["default"](self.ctx))

    def _infer(self, feed_dict: Dict, output_tensor_names: List[str]) -> List:
        bs = 1
        for input_name in feed_dict:
            bs = len(feed_dict[input_name])
            break

        module = self.module_dict[bs]
        if not self.use_gpu:
            set_input = module["set_input_zero_copy"]
        else:
            set_input = module["set_input"]

        for input_name in feed_dict:
            tvm_data = tvm.nd.array(feed_dict[input_name], device=self.ctx)
            set_input(input_name, tvm_data)

        module.run()

        outputs = []
        for i in range(len(output_tensor_names)):
            outputs.append(module.get_output(i).numpy())

        return outputs

    def request_entering(self, extra_metadata: Dict):
        extra_metadata[self.component_model.model_uuid]["model_t0"] = time.time()

    def request_exiting(self, extra_metadata: Dict):
        model_t0 = extra_metadata[self.component_model.model_uuid].pop("model_t0")
        extra_metadata[self.component_model.model_uuid]["model_lat"] = (
            time.time() - model_t0
        )
