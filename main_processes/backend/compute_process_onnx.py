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


class BackendComputeProcessOnnx(BackendComputeProcess):
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
        import onnxruntime as rt
        import onnx

        is_onnx_file = True
        try:
            _ = onnx.load(self.model_path)
        except:
            is_onnx_file = False

        if not is_onnx_file:
            # this is zip file
            import shutil

            base_dir_path = os.path.dirname(self.model_path)
            big_onnx_model_dir = os.path.join(base_dir_path, "big_onnx")

            if not os.path.exists(big_onnx_model_dir):
                os.makedirs(big_onnx_model_dir)

            shutil.unpack_archive(self.model_path, big_onnx_model_dir, format="zip")

            os.remove(self.model_path)

            # update model_path
            self.model_path = os.path.join(big_onnx_model_dir, "model.onnx")

        providers = []
        if not self.use_gpu:
            providers.append("CPUExecutionProvider")
        else:
            providers.append("CUDAExecutionProvider")

        self.onnx_sess = rt.InferenceSession(self.model_path, providers=providers)

        # if not self.use_gpu:
        #     self.onnx_sess.set_providers(["CPUExecutionProvider"])
        # else:
        #     self.onnx_sess.set_providers(["CUDAExecutionProvider"])

    def _infer(self, feed_dict: Dict, output_tensor_names: List[str]) -> List:
        outputs = self.onnx_sess.run(output_tensor_names, feed_dict)
        return outputs

    def request_entering(self, extra_metadata: Dict):
        extra_metadata[self.component_model.model_uuid]["model_t0"] = time.time()

    def request_exiting(self, extra_metadata: Dict):
        model_t0 = extra_metadata[self.component_model.model_uuid].pop("model_t0")
        extra_metadata[self.component_model.model_uuid]["model_lat"] = (
            time.time() - model_t0
        )
