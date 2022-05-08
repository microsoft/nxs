import time
import numpy as np
from typing import Dict
from nxs_types.model import NxsModel
from nxs_types.nxs_args import NxsBackendArgs
from nxs_types.scheduling_data import NxsSchedulingPerComponentModelPlan

from main_processes.backend.input_process import BackendInputProcess


class BackendBasicInputProcess(BackendInputProcess):
    def __init__(
        self,
        args: NxsBackendArgs,
        component_model: NxsModel,
        component_model_plan: NxsSchedulingPerComponentModelPlan,
        preprocessing_fn_path: str,
        input_interface_args_dict: Dict[str, Dict],
        output_interface_args: Dict,
        dispatcher_args: Dict,
        stop_flag,
        next_process_stop_flag,
        dispatcher_update_shared_list=None,
        global_dispatcher_input_shared_list=None,
        global_dispatcher_output_shared_list=None,
        process_update_shared_list=None,
        extra_params: Dict = {},
    ) -> None:
        super().__init__(
            args,
            component_model,
            component_model_plan,
            preprocessing_fn_path,
            input_interface_args_dict,
            output_interface_args,
            dispatcher_args,
            stop_flag,
            next_process_stop_flag,
            dispatcher_update_shared_list,
            global_dispatcher_input_shared_list,
            global_dispatcher_output_shared_list,
            process_update_shared_list,
            extra_params=extra_params,
        )

    def request_entering(self, extra_metadata: Dict):
        if "input_t0" not in extra_metadata:
            extra_metadata["input_t0"] = time.time()

        extra_metadata[self.component_model.model_uuid] = {}
        extra_metadata[self.component_model.model_uuid]["input_t0"] = time.time()

    def request_exiting(self, extra_metadata: Dict):
        input_t0 = extra_metadata[self.component_model.model_uuid].pop("input_t0")
        extra_metadata[self.component_model.model_uuid]["input_lat"] = (
            time.time() - input_t0
        )
