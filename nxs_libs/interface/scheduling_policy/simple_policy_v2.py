import math
from typing import List, Tuple, Dict

from nxs_libs.interface.scheduling_policy import BaseSchedulingPolicy
from nxs_types import scheduling_data
from nxs_types.backend import BackendInfo
from nxs_types.model import (
    LatencyMeasurement,
    NxsCompositoryModel,
    NxsModel,
    NxsPipelineInfo,
    ProfileUnit,
)
from nxs_types.scheduling_data import *


class NxsSimpleSchedulingPerBackendPlan(DataModel):
    backend_name: str
    component_models_plan: List[NxsSchedulingPerComponentModelPlan]
    duty_cycle: float = 1.0
    extra_info: str = ""


class NxsSimpleSchedulingPerCompositoryModelPlan(DataModel):
    model_uuid: str
    session_uuid: str
    backend_plans: List[NxsSimpleSchedulingPerBackendPlan]


class NxsSimpleUnschedulingPerCompositoryModelPlan(DataModel):
    model_uuid: str
    session_uuid: str
    backend_name: str
    extra_info: str = ""


class RequiredResouce:
    def __init__(self) -> None:
        self.max_gpu_mem: float = 0
        self.min_gpu_mem: float = 0


class SimpleSchedulingPolicyv2(BaseSchedulingPolicy):
    MAX_MODELS_PER_BACKEND = 5

    def __init__(self) -> None:
        super().__init__()

        self.last_requests_dict: Dict[str, NxsSchedulingRequest] = {}
        self.last_backends_dict: Dict[str, BackendInfo] = {}

        self.scheduling_plans_dict: Dict[
            str, List[NxsSimpleSchedulingPerCompositoryModelPlan]
        ] = {}  # from session_uuid -> plans for cmodels
        self.unscheduling_plans_dict: Dict[
            str, List[NxsSimpleUnschedulingPerCompositoryModelPlan]
        ] = {}  # from session_uuid -> plans for cmodels

        self.current_requests_dict: Dict[str, NxsSchedulingRequest] = {}
        self.current_backends_dict: Dict[str, BackendInfo] = {}

        self.cmodels_dict: Dict[str, NxsCompositoryModel] = {}
        self.pipelines_dict: Dict[str, NxsPipelineInfo] = {}

    def _deploy_new_pipelines(self):
        to_add_pipeline_uuids = self._compute_pipeline_uuids_to_add()

        # print("to_add_pipeline_uuids", to_add_pipeline_uuids)

        for pipeline_uuid in to_add_pipeline_uuids:
            deployed = True
            pipeline_info = self.pipelines_dict[pipeline_uuid]
            associated_session_uuids = []
            deployment_info = []

            existing_cmodel_2_plans: Dict[
                str, NxsSimpleSchedulingPerCompositoryModelPlan
            ] = {}

            for session_uuid in self.current_requests_dict:
                if (
                    self.current_requests_dict[session_uuid].pipeline_info.pipeline_uuid
                    == pipeline_uuid
                ):
                    associated_session_uuids.append(session_uuid)

            for cmodel in pipeline_info.models:
                # search if any plans contain this cmodel
                cmodel_uuid = cmodel.main_model.model_uuid

                existed = False
                for session_uuid in self.scheduling_plans_dict:
                    other_cmodel_plans = self.scheduling_plans_dict[session_uuid]
                    for other_cmodel_plan in other_cmodel_plans:
                        if other_cmodel_plan.model_uuid == cmodel_uuid:
                            existed = True

                            if (
                                other_cmodel_plan.model_uuid
                                not in existing_cmodel_2_plans
                            ):
                                existing_cmodel_2_plans[
                                    other_cmodel_plan.model_uuid
                                ] = []

                            existing_cmodel_2_plans[
                                other_cmodel_plan.model_uuid
                            ].append(other_cmodel_plan)

                if existed:
                    continue

                # print(f"Trying to deploy cmodel {cmodel.main_model.model_uuid}")
                deployed_backend = self._deploy_cmodel(
                    cmodel.main_model.model_uuid, associated_session_uuids
                )

                if not deployed_backend:
                    deployed = False
                    break

                deployment_info.append((cmodel, deployed_backend))

            if not deployed:
                # need to undeploy deployed models
                for deployed_cmodel, deployed_backend in deployment_info:
                    self._remove_cmodel_from_backend(
                        deployed_cmodel,
                        deployed_backend,
                        generate_unscheduling_plans=False,
                    )
            else:
                # for deployed_cmodel, deployed_backend in deployment_info:
                #     print(
                #         f"Deployed cmodel {deployed_cmodel.main_model.model_uuid} onto backend {deployed_backend.backend_name}"
                #     )

                # add sessions associated with this pipeline into some old cmodels
                for session_uuid in associated_session_uuids:
                    for cmodel_uuid in existing_cmodel_2_plans:
                        cmodel_plans = existing_cmodel_2_plans[cmodel_uuid]
                        for cmodel_plan in cmodel_plans:
                            if session_uuid not in self.scheduling_plans_dict:
                                self.scheduling_plans_dict[session_uuid] = []

                            self.scheduling_plans_dict[session_uuid].append(cmodel_plan)

    def _assign_backends_to_unscheduled_sessions(self):
        for session_uuid in self.current_requests_dict:
            if session_uuid in self.scheduling_plans_dict:
                # already scheduled
                continue

            request = self.current_requests_dict[session_uuid]
            cmodels = request.pipeline_info.models
            cmodel2backendplans = {}
            cmodel2backendnames = {}

            for cmodel in cmodels:
                for other_session_uuid in self.scheduling_plans_dict:
                    if other_session_uuid == session_uuid:
                        continue

                    other_cmodel_plans = self.scheduling_plans_dict[other_session_uuid]
                    for other_cmodel_plan in other_cmodel_plans:
                        if other_cmodel_plan.model_uuid == cmodel.main_model.model_uuid:
                            if other_cmodel_plan.model_uuid not in cmodel2backendplans:
                                cmodel2backendplans[other_cmodel_plan.model_uuid] = []
                                cmodel2backendnames[other_cmodel_plan.model_uuid] = []

                            for backend_plan in other_cmodel_plan.backend_plans:
                                if (
                                    backend_plan.backend_name
                                    not in cmodel2backendnames[
                                        other_cmodel_plan.model_uuid
                                    ]
                                ):
                                    cmodel2backendnames[
                                        other_cmodel_plan.model_uuid
                                    ].append(backend_plan.backend_name)
                                    cmodel2backendplans[
                                        other_cmodel_plan.model_uuid
                                    ].append(backend_plan)

            if len(cmodels) == len(cmodel2backendplans):
                # have enough models
                self.scheduling_plans_dict[session_uuid] = []
                for cmodel_uuid in cmodel2backendplans:
                    # print(cmodel2backendplans[cmodel_uuid])
                    new_cmodel_plan = NxsSimpleSchedulingPerCompositoryModelPlan(
                        model_uuid=cmodel_uuid,
                        session_uuid=session_uuid,
                        backend_plans=cmodel2backendplans[cmodel_uuid],
                    )
                    self.scheduling_plans_dict[session_uuid].append(new_cmodel_plan)

    def _remove_cmodel_from_backend(
        self,
        cmodel: NxsCompositoryModel,
        backend: BackendInfo,
        generate_unscheduling_plans=True,
    ):

        to_remove_session_uuids = []
        found_backend = False

        # print("removing backend name: ", backend.backend_name)

        for session_uuid in self.scheduling_plans_dict:
            target_cmodel_plan: NxsSimpleSchedulingPerCompositoryModelPlan = None
            cmodel_plans = self.scheduling_plans_dict[session_uuid]
            for cmodel_plan in cmodel_plans:
                if cmodel.main_model.model_uuid == cmodel_plan.model_uuid:
                    target_cmodel_plan = cmodel_plan
                    break

            if target_cmodel_plan is None:
                continue

            new_backend_plans: List[NxsSimpleSchedulingPerBackendPlan] = []

            for backend_plan in target_cmodel_plan.backend_plans:
                if backend_plan.backend_name != backend.backend_name:
                    new_backend_plans.append(backend_plan)
                    continue
                else:
                    found_backend = True

                    if generate_unscheduling_plans:
                        if session_uuid not in self.unscheduling_plans_dict:
                            self.unscheduling_plans_dict[session_uuid] = []
                            self.unscheduling_plans_dict[session_uuid].append(
                                NxsSimpleUnschedulingPerCompositoryModelPlan(
                                    model_uuid=cmodel.main_model.model_uuid,
                                    session_uuid=session_uuid,
                                    backend_name=backend_plan.backend_name,
                                )
                            )

            target_cmodel_plan.backend_plans = new_backend_plans

            if not target_cmodel_plan.backend_plans:
                # to_remove_session_uuids.append(session_uuid)

                new_cmodel_plans: List[NxsSimpleSchedulingPerCompositoryModelPlan] = []

                for cmodel_plan in self.scheduling_plans_dict[session_uuid]:
                    if cmodel_plan.model_uuid != target_cmodel_plan.model_uuid:
                        new_backend_plans.append(cmodel_plan)

                self.scheduling_plans_dict[session_uuid] = new_cmodel_plans

                if not self.scheduling_plans_dict[session_uuid]:
                    to_remove_session_uuids.append(session_uuid)

        for session_uuid in to_remove_session_uuids:
            self.scheduling_plans_dict.pop(session_uuid, None)

        if found_backend:
            required_res = self._compute_required_resource_for_atomic_model(cmodel)
            # print(
            #     f"Returning {required_res.max_gpu_mem} MB from atomic model {cmodel.main_model.model_uuid} to backend {backend.backend_name}"
            # )
            self._return_resource_to_backend(backend, required_res)

    def _deploy_cmodel(self, cmodel_uuid: str, session_uuids: List[str]) -> BackendInfo:
        cmodel = self.cmodels_dict[cmodel_uuid]
        required_res = self._compute_required_resource_for_atomic_model(cmodel)

        # find potential backends
        potential_backends = self._find_potential_backends(cmodel, required_res)
        if not potential_backends:
            return None

        best_backend = self._find_best_backend(potential_backends, required_res)
        if not best_backend:
            return None

        self._take_resource_from_backend(best_backend, required_res)

        for session_uuid in session_uuids:
            self._add_scheduling_plan(session_uuid, cmodel, best_backend)

        return best_backend

    def _add_scheduling_plan(
        self,
        session_uuid: str,
        cmodel: NxsCompositoryModel,
        backend: BackendInfo,
    ):
        component_model_plans = []

        for component_model in cmodel.component_models:
            best_benchmark_result = self._get_best_profile(component_model)
            component_model_plans.append(
                NxsSchedulingPerComponentModelPlan(
                    model_uuid=component_model.model_uuid,
                    batch_size=best_benchmark_result.batch_size,
                )
            )

        if session_uuid not in self.scheduling_plans_dict:
            self.scheduling_plans_dict[session_uuid] = []

        target_cmodel_plan = None
        for cmodel_plan in self.scheduling_plans_dict[session_uuid]:
            if cmodel_plan.model_uuid == cmodel.main_model.model_uuid:
                target_cmodel_plan = cmodel_plan
                break

        if target_cmodel_plan is None:
            target_cmodel_plan = NxsSimpleSchedulingPerCompositoryModelPlan(
                model_uuid=cmodel.main_model.model_uuid,
                session_uuid=session_uuid,
                backend_plans=[],
            )
            self.scheduling_plans_dict[session_uuid].append(target_cmodel_plan)

        target_cmodel_plan.backend_plans.append(
            NxsSimpleSchedulingPerBackendPlan(
                backend_name=backend.backend_name,
                component_models_plan=component_model_plans,
            )
        )

    def _find_best_backend(
        self,
        potential_backends: List[BackendInfo],
        required_res: RequiredResouce,
    ):
        best_backend = None
        use_gpu = required_res.max_gpu_mem > 0

        if use_gpu:
            max_gpu_mem_available = 0
        else:
            min_num_deployed_models = self.MAX_MODELS_PER_BACKEND

        for backend in potential_backends:
            if use_gpu:
                # find gpu-backend which has lowest-gpu-mem-usage
                if backend.state.gpu_info.gpu_total_mem > max_gpu_mem_available:
                    max_gpu_mem_available = backend.state.gpu_info.gpu_total_mem
                    best_backend = backend
            else:
                # find cpu-backend which is running least number of models
                running_cmodel_uuids = []

                for session_uuid in self.scheduling_plans_dict:
                    cmodel_plans = self.scheduling_plans_dict[session_uuid]
                    for cmodel_plan in cmodel_plans:
                        for backend_plan in cmodel_plan.backend_plans:
                            if backend.backend_name == backend_plan.backend_name:
                                if cmodel_plan.model_uuid not in running_cmodel_uuids:
                                    running_cmodel_uuids.append(cmodel_plan.model_uuid)

                if len(running_cmodel_uuids) < min_num_deployed_models:
                    min_num_deployed_models = len(running_cmodel_uuids)
                    best_backend = backend

        return best_backend

    def _find_potential_backends(
        self, cmodel: NxsCompositoryModel, required_res: RequiredResouce
    ) -> List[BackendInfo]:
        use_gpu = required_res.max_gpu_mem > 0
        potential_backends = []

        cmodel_uuid = cmodel.main_model.model_uuid

        for backend_name in self.current_backends_dict:
            is_deployed = False

            for session_uuid in self.scheduling_plans_dict:
                cmodel_plans = self.scheduling_plans_dict[session_uuid]

                for cmodel_plan in cmodel_plans:
                    if cmodel_plan.model_uuid != cmodel_uuid:
                        continue

                    for backend_plan in cmodel_plan.backend_plans:
                        if backend_plan.backend_name == backend_name:
                            is_deployed = True
                            break

                    if is_deployed:
                        break

            if is_deployed:
                continue

            backend = self.current_backends_dict[backend_name]
            has_gpu = backend.state.gpu_info != None

            if has_gpu != use_gpu:
                continue

            if not use_gpu:
                # TODO: if we need to limit how many models each cpu-backend should run - we should do it here
                potential_backends.append(backend)
            else:
                if backend.state.gpu_info.gpu_total_mem > required_res.max_gpu_mem:
                    potential_backends.append(backend)

        return potential_backends

    def _remove_expired_backends(self):
        expired_backend_names: List[str] = []

        for backend_name in self.last_backends_dict:
            if backend_name not in self.current_backends_dict:
                expired_backend_names.append(backend_name)

        # print("expired_backend_names", expired_backend_names)

        # if not expired_backend_names:
        #    return

        to_remove_session_uuids = []
        for session_uuid in self.scheduling_plans_dict:
            cmodel_plans = self.scheduling_plans_dict[session_uuid]

            new_cmodel_plans = []
            for cmodel_plan in cmodel_plans:
                cmodel_uuid = cmodel_plan.model_uuid

                new_backend_plans = []
                for backend_plan in cmodel_plan.backend_plans:
                    if backend_plan.backend_name not in expired_backend_names:
                        new_backend_plans.append(backend_plan)
                        continue

                    if session_uuid not in self.unscheduling_plans_dict:
                        self.unscheduling_plans_dict[session_uuid] = []

                    self.unscheduling_plans_dict[session_uuid].append(
                        NxsSimpleUnschedulingPerCompositoryModelPlan(
                            model_uuid=cmodel_uuid,
                            session_uuid=session_uuid,
                            backend_name=backend_name,
                        )
                    )

                cmodel_plan.backend_plans = new_backend_plans
                if cmodel_plan.backend_plans:
                    new_cmodel_plans.append(cmodel_plan)

            self.scheduling_plans_dict[session_uuid] = new_cmodel_plans
            if not self.scheduling_plans_dict[session_uuid]:
                to_remove_session_uuids.append(session_uuid)

        for session_uuid in to_remove_session_uuids:
            self.scheduling_plans_dict.pop(session_uuid)

    def _remove_unused_sessions(self):
        to_remove_session_uuids = self._compute_unused_session_uuids()

        # print("to_remove_session_uuids", to_remove_session_uuids)

        for session_uuid in to_remove_session_uuids:
            self._remove_session(session_uuid)

    def _remove_session(self, session_uuid: str, generate_unscheduling_plans=True):
        if session_uuid not in self.unscheduling_plans_dict:
            self.unscheduling_plans_dict[session_uuid] = []

        cmodel_plans = self.scheduling_plans_dict[session_uuid]
        to_remove = []
        for cmodel_plan in cmodel_plans:
            cmodel_uuid = cmodel_plan.model_uuid

            for backend_plan in cmodel_plan.backend_plans:
                backend_name = backend_plan.backend_name

                if generate_unscheduling_plans:
                    self.unscheduling_plans_dict[session_uuid].append(
                        NxsSimpleUnschedulingPerCompositoryModelPlan(
                            model_uuid=cmodel_uuid,
                            session_uuid=session_uuid,
                            backend_name=backend_name,
                        )
                    )

                # check if any session running on this backend-end or not
                has_other_sessions_running = False
                for other_session_uuid in self.scheduling_plans_dict:
                    if other_session_uuid == session_uuid:
                        continue

                    other_cmodel_plans = self.scheduling_plans_dict[other_session_uuid]
                    for other_cmodel_plan in other_cmodel_plans:
                        for other_backend_plan in other_cmodel_plan.backend_plans:
                            if other_backend_plan.backend_name == backend_name:
                                has_other_sessions_running = True
                                break

                        if has_other_sessions_running:
                            break

                    if has_other_sessions_running:
                        break

                if not has_other_sessions_running:
                    # has to remove cmodel from backend to retrieve back resources
                    to_remove.append(
                        (
                            self.cmodels_dict[cmodel_uuid],
                            self.current_backends_dict[backend_name],
                        )
                    )

        for cmodel, backend in to_remove:
            self._remove_cmodel_from_backend(cmodel, backend, False)

        self.scheduling_plans_dict.pop(session_uuid, None)

    def _compute_unused_session_uuids(self):
        unused_session_uuids = []

        for session_uuid in list(self.scheduling_plans_dict.keys()):
            if session_uuid not in self.current_requests_dict:
                unused_session_uuids.append(session_uuid)

        return unused_session_uuids

    def _remove_unused_pipelines(self):
        to_remove_pipeline_uuids = self._compute_pipeline_uuids_to_remove()
        # print("to_remove_pipeline_uuids", to_remove_pipeline_uuids)

        last_cmodel_ref_count_dict = self._compute_last_requesting_cmodel_ref_count()
        # print("last_cmodel_ref_count_dict", last_cmodel_ref_count_dict)

        to_add_pipeline_uuids = self._compute_pipeline_uuids_to_add()
        # print("to_add_pipeline_uuids", to_add_pipeline_uuids)

        # add all new pipeline's cmodels into last_cmodel_ref_count_dict to prevent undeploy unnecessary models
        for session_uuid in self.current_requests_dict:
            request = self.current_requests_dict[session_uuid]
            pipeline_uuid = request.pipeline_info.pipeline_uuid
            if pipeline_uuid in to_add_pipeline_uuids:
                for cmodel in request.pipeline_info.models:
                    cmodel_uuid = cmodel.main_model.model_uuid
                    if cmodel_uuid not in last_cmodel_ref_count_dict:
                        last_cmodel_ref_count_dict[cmodel_uuid] = 0
                    last_cmodel_ref_count_dict[cmodel_uuid] += 1

        to_remove_cmodel_uuids = []
        for session_uuid in self.last_requests_dict:
            if session_uuid not in self.scheduling_plans_dict:
                continue

            request = self.last_requests_dict[session_uuid]
            pipeline_uuid = request.pipeline_info.pipeline_uuid

            if pipeline_uuid in to_remove_pipeline_uuids:
                for cmodel in request.pipeline_info.models:
                    cmodel_uuid = cmodel.main_model.model_uuid
                    last_cmodel_ref_count_dict[cmodel_uuid] -= 1
                    if last_cmodel_ref_count_dict[cmodel_uuid] == 0:
                        if cmodel_uuid not in to_remove_cmodel_uuids:
                            to_remove_cmodel_uuids.append(cmodel_uuid)
                            # print(f"Add cmodel {cmodel_uuid} to remove list...")

        # return cmodel's resources back to backend
        cmodel_uuid_2_session_uuids: Dict[str, List[str]] = {}
        for session_uuid in self.scheduling_plans_dict:
            cmodel_plans = self.scheduling_plans_dict[session_uuid]
            for cmodel_plan in cmodel_plans:
                cmodel_uuid = cmodel_plan.model_uuid
                if cmodel_uuid in to_remove_cmodel_uuids:
                    if cmodel_uuid not in cmodel_uuid_2_session_uuids:
                        cmodel_uuid_2_session_uuids[cmodel_uuid] = []
                    if session_uuid not in cmodel_uuid_2_session_uuids[cmodel_uuid]:
                        cmodel_uuid_2_session_uuids[cmodel_uuid].append(session_uuid)

        # print("cmodel_uuid_2_session_uuids", cmodel_uuid_2_session_uuids)

        unscheduling_plans: List[NxsSimpleUnschedulingPerCompositoryModelPlan] = []
        for cmodel_uuid in cmodel_uuid_2_session_uuids:
            backend_names = []
            session_uuids = cmodel_uuid_2_session_uuids[cmodel_uuid]

            for session_uuid in session_uuids:
                cmodel_plans = self.scheduling_plans_dict[session_uuid]
                for cmodel_plan in cmodel_plans:
                    if cmodel_plan.model_uuid != cmodel_uuid:
                        continue

                    for backend_plan in cmodel_plan.backend_plans:
                        if backend_plan.backend_name not in backend_names:
                            backend_names.append(backend_plan.backend_name)

                        # unscheduling_plans.append(NxsSimpleUnschedulingPerCompositoryModelPlan(
                        #     model_uuid = cmodel_uuid,
                        #     session_uuid = session_uuid,
                        #     backend_name = backend_plan.backend_name
                        # ))

            for backend_name in backend_names:
                self._remove_cmodel_from_backend(
                    self.cmodels_dict[cmodel_uuid],
                    self.current_backends_dict[backend_name],
                )

        # print("unscheduling_plans", unscheduling_plans)

        for unscheduling_plan in unscheduling_plans:
            session_uuid = unscheduling_plan.session_uuid
            if session_uuid not in self.unscheduling_plans_dict:
                self.unscheduling_plans_dict[session_uuid] = []
            self.unscheduling_plans_dict[session_uuid].append(unscheduling_plan)

        for session_uuid in list(self.last_requests_dict.keys()):
            request = self.last_requests_dict[session_uuid]
            pipeline_uuid = request.pipeline_info.pipeline_uuid
            if pipeline_uuid in to_remove_pipeline_uuids:
                self.last_requests_dict.pop(pipeline_uuid, None)

    def _scale_sessions(self):
        # compute fps per model
        requesting_cmodeluuid2fps = {}
        scheduled_cmodeluuid2fps = {}
        cmodeluuid2fps = {}
        cmodeluuid2sessionuuids: Dict[str, List[str]] = {}

        for session_uuid in self.current_requests_dict:
            request = self.current_requests_dict[session_uuid]
            cmodels = request.pipeline_info.models
            for cmodel in cmodels:
                cmodel_uuid = cmodel.main_model.model_uuid

                if cmodel_uuid not in requesting_cmodeluuid2fps:
                    requesting_cmodeluuid2fps[cmodel_uuid] = 0

                requesting_cmodeluuid2fps[cmodel_uuid] += request.requested_fps

        counted_scheduled_cmodel_on_backends = []
        for session_uuid in self.scheduling_plans_dict:
            cmodel_plans = self.scheduling_plans_dict[session_uuid]
            for cmodel_plan in cmodel_plans:
                cmodel_uuid = cmodel_plan.model_uuid
                cmodel = self.cmodels_dict[cmodel_uuid]

                fps = 999999999999
                for component_model in cmodel.component_models:
                    best_profile = self._get_best_profile(component_model)
                    fps = min(fps, best_profile.fps)

                if cmodel_uuid not in cmodeluuid2sessionuuids:
                    cmodeluuid2sessionuuids[cmodel_uuid] = []

                if session_uuid not in cmodeluuid2sessionuuids[cmodel_uuid]:
                    cmodeluuid2sessionuuids[cmodel_uuid].append(session_uuid)

                if cmodel_uuid not in cmodeluuid2fps:
                    cmodeluuid2fps[cmodel_uuid] = fps

                if cmodel_uuid not in scheduled_cmodeluuid2fps:
                    scheduled_cmodeluuid2fps[cmodel_uuid] = 0

                for backend_plan in cmodel_plan.backend_plans:
                    key = f"{cmodel_uuid}_{backend_plan.backend_name}"
                    if key not in counted_scheduled_cmodel_on_backends:
                        counted_scheduled_cmodel_on_backends.append(key)
                        scheduled_cmodeluuid2fps[cmodel_uuid] += fps

        for cmodel_uuid in requesting_cmodeluuid2fps:
            if cmodel_uuid not in scheduled_cmodeluuid2fps:
                # skip if this model was not scheduled
                continue

            session_uuids = cmodeluuid2sessionuuids[cmodel_uuid]

            num_requesting_backends = math.ceil(
                requesting_cmodeluuid2fps[cmodel_uuid] / cmodeluuid2fps[cmodel_uuid]
            )
            num_scheduled_backends = math.ceil(
                scheduled_cmodeluuid2fps[cmodel_uuid] / cmodeluuid2fps[cmodel_uuid]
            )

            if num_scheduled_backends > num_requesting_backends:
                # print(
                #     f"SCALING DOWN - requesting {requesting_cmodeluuid2fps[cmodel_uuid]} - serving {scheduled_cmodeluuid2fps[cmodel_uuid]} fps"
                # )
                # need to scale down
                delta = num_scheduled_backends - num_requesting_backends
                for _ in range(delta):
                    backend_names = []
                    backends = []

                    for session_uuid in list(self.scheduling_plans_dict.keys()):
                        cmodel_plans = self.scheduling_plans_dict[session_uuid]
                        for cmodel_plan in cmodel_plans:
                            if cmodel_plan.model_uuid != cmodel_uuid:
                                continue

                            for backend_plan in cmodel_plan.backend_plans:
                                if backend_plan.backend_name not in backend_names:
                                    backend_names.append(backend_plan.backend_name)
                                    backends.append(
                                        self.current_backends_dict[
                                            backend_plan.backend_name
                                        ]
                                    )

                    # randomly remove backend
                    if not backends:
                        break

                    # print("to remove", backends[0])
                    self._remove_cmodel_from_backend(
                        self.cmodels_dict[cmodel_uuid], backends[0]
                    )

            elif num_requesting_backends > num_scheduled_backends:
                # need to scale up
                # print(
                #     f"SCALING UP - requesting {requesting_cmodeluuid2fps[cmodel_uuid]} - serving {scheduled_cmodeluuid2fps[cmodel_uuid]} fps"
                # )
                delta = num_requesting_backends - num_scheduled_backends
                for _ in range(delta):
                    backend = self._deploy_cmodel(cmodel_uuid, session_uuids)
                    if not backend:
                        break

    def schedule(
        self,
        requests: List[NxsSchedulingRequest],
        backends: List[BackendInfo],
    ) -> NxsSchedulingPlan:
        # print("requests", requests)

        # fix similar session_uuid across models
        for request in requests:
            request.session_uuid = (
                f"{request.pipeline_info.pipeline_uuid}_{request.session_uuid}"
            )

        # reset states - we only keep scheduling plans
        self.unscheduling_plans_dict: Dict[
            str, List[NxsSimpleUnschedulingPerCompositoryModelPlan]
        ] = {}

        self.cmodels_dict: Dict[str, NxsCompositoryModel] = {}
        self.pipelines_dict: Dict[str, NxsPipelineInfo] = {}

        all_requests: List[NxsSchedulingRequest] = []
        all_requests.extend(self.last_requests_dict.values())
        all_requests.extend(requests)
        for request in all_requests:
            if request.pipeline_info.pipeline_uuid not in self.pipelines_dict:
                self.pipelines_dict[
                    request.pipeline_info.pipeline_uuid
                ] = request.pipeline_info

            for cmodel in request.pipeline_info.models:
                if cmodel.main_model.model_uuid not in self.cmodels_dict:
                    self.cmodels_dict[cmodel.main_model.model_uuid] = cmodel

        self.current_requests_dict: Dict[str, NxsSchedulingRequest] = {}
        self.current_backends_dict: Dict[str, BackendInfo] = {}

        for request in requests:
            self.current_requests_dict[request.session_uuid] = request

        for backend in backends:
            self.current_backends_dict[backend.backend_name] = backend

        # print('_remove_expired_backends', self.scheduling_plans_dict)
        self._remove_expired_backends()

        # print('_remove_unused_sessions', self.scheduling_plans_dict)
        self._remove_unused_sessions()

        # print('_remove_unused_pipelines', self.scheduling_plans_dict)
        self._remove_unused_pipelines()

        # print('_deploy_new_pipelines', self.scheduling_plans_dict)
        self._deploy_new_pipelines()

        # print('_assign_backends_to_unscheduled_sessions', self.scheduling_plans_dict)
        self._assign_backends_to_unscheduled_sessions()

        self._scale_sessions()

        # print("final_scheduling", self.scheduling_plans_dict)
        # print("final_unscheduling", self.unscheduling_plans_dict)

        scheduling_plans: List[NxsSimpleSchedulingPerCompositoryModelPlan] = []
        unscheduling_plans: List[NxsSimpleUnschedulingPerCompositoryModelPlan] = []

        for session_uuid in self.scheduling_plans_dict:
            plans = self.scheduling_plans_dict[session_uuid]
            scheduling_plans.extend(plans)

        for session_uuid in self.unscheduling_plans_dict:
            plans = self.unscheduling_plans_dict[session_uuid]
            unscheduling_plans.extend(plans)

        self.last_backends_dict = self.current_backends_dict
        self.last_requests_dict = self.current_requests_dict

        # print("unscheduling_plans", unscheduling_plans)
        # print("final_scheduling", scheduling_plans)
        # print("final_unscheduling", unscheduling_plans)
        # print("")

        # convert planv1 to planv2
        backend_scheduling_data: Dict[str, NxsSchedulingPerBackendPlan] = {}
        for plan in scheduling_plans:
            session_uuid = plan.session_uuid.split("_")[-1]
            cmodel_uuid = plan.model_uuid

            for backend_plan in plan.backend_plans:
                backend_name = backend_plan.backend_name
                if backend_name not in backend_scheduling_data:
                    backend_scheduling_data[backend_name] = NxsSchedulingPerBackendPlan(
                        backend_name=backend_name,
                        compository_model_plans=[],
                        duty_cyles=[],
                    )

                cmodel_plan_v2: NxsSchedulingPerCompositorymodelPlan = None
                for _cmodel_plan_v2 in backend_scheduling_data[
                    backend_name
                ].compository_model_plans:
                    if _cmodel_plan_v2.model_uuid == cmodel_uuid:
                        cmodel_plan_v2 = _cmodel_plan_v2

                if not cmodel_plan_v2:
                    cmodel_plan_v2 = NxsSchedulingPerCompositorymodelPlan(
                        model_uuid=cmodel_uuid,
                        session_uuid_list=[],
                        component_model_plans=backend_plan.component_models_plan,
                    )
                    backend_scheduling_data[
                        backend_name
                    ].compository_model_plans.append(cmodel_plan_v2)

                cmodel_plan_v2.session_uuid_list.append(session_uuid)
                backend_scheduling_data[backend_name].duty_cyles.append(1.0)

        # print("backend_scheduling_data", backend_scheduling_data)
        # print("")

        backend_unscheduling_data: Dict[str, NxsUnschedulingPerBackendPlan] = {}
        for plan in unscheduling_plans:
            # print(plan)
            session_uuid = plan.session_uuid.split("_")[-1]

            if plan.backend_name not in backend_unscheduling_data:
                backend_unscheduling_data[
                    plan.backend_name
                ] = NxsUnschedulingPerBackendPlan(
                    backend_name=plan.backend_name, compository_model_plans=[]
                )

            cmodel_plan: NxsUnschedulingPerCompositoryPlan = None
            for _cmodel_plan in backend_unscheduling_data[
                plan.backend_name
            ].compository_model_plans:
                if _cmodel_plan.model_uuid == plan.model_uuid:
                    cmodel_plan = _cmodel_plan
                    break

            if not cmodel_plan:
                cmodel_plan = NxsUnschedulingPerCompositoryPlan(
                    model_uuid=plan.model_uuid, session_uuid_list=[]
                )
                backend_unscheduling_data[
                    plan.backend_name
                ].compository_model_plans.append(cmodel_plan)

            cmodel_plan.session_uuid_list.append(session_uuid)

        # print("backend_unscheduling_data", backend_unscheduling_data)
        # print("")

        return NxsSchedulingPlan(
            scheduling=[
                backend_scheduling_data[backend_name]
                for backend_name in backend_scheduling_data
            ],
            unscheduling=[
                backend_unscheduling_data[backend_name]
                for backend_name in backend_unscheduling_data
            ],
        )

    def get_states(self) -> Dict:
        return {}

    def set_states(self, states):
        pass

    ####### Internal functions #######

    def _compute_pipeline_uuids_to_add(self) -> List[str]:
        to_add_pipeline_uuids = []
        deployed_cmodel_ref_count_dict = self._compute_deployed_cmodel_ref_count()

        for session_uuid in self.current_requests_dict:
            request = self.current_requests_dict[session_uuid]
            is_pipeline_deployed = True

            for cmodel in request.pipeline_info.models:
                cmodel_uuid = cmodel.main_model.model_uuid
                if cmodel_uuid not in deployed_cmodel_ref_count_dict:
                    is_pipeline_deployed = False
                    break

            if (
                not is_pipeline_deployed
                and request.pipeline_info.pipeline_uuid not in to_add_pipeline_uuids
            ):
                to_add_pipeline_uuids.append(request.pipeline_info.pipeline_uuid)

        return to_add_pipeline_uuids

    def _compute_pipeline_uuids_to_remove(self) -> List[str]:
        to_remove_pipeline_uuids = []

        current_pipeline_uuids = []
        for session_uuid in self.current_requests_dict:
            current_request = self.current_requests_dict[session_uuid]
            pipeline_uuid = current_request.pipeline_info.pipeline_uuid
            if pipeline_uuid not in current_pipeline_uuids:
                current_pipeline_uuids.append(pipeline_uuid)

        for session_uuid in self.last_requests_dict:
            last_request = self.last_requests_dict[session_uuid]
            pipeline_uuid = last_request.pipeline_info.pipeline_uuid
            if pipeline_uuid not in current_pipeline_uuids:
                if pipeline_uuid not in to_remove_pipeline_uuids:
                    to_remove_pipeline_uuids.append(pipeline_uuid)

        return to_remove_pipeline_uuids

    def _compute_deployed_cmodel_ref_count(self) -> Dict[str, int]:
        ref_count_dict: Dict[str, int] = {}

        for session_name in self.scheduling_plans_dict:
            cmodel_plans = self.scheduling_plans_dict[session_name]
            for cmodel_plan in cmodel_plans:
                if cmodel_plan.backend_plans:
                    if cmodel_plan.model_uuid not in ref_count_dict:
                        ref_count_dict[cmodel_plan.model_uuid] = 0

                    ref_count_dict[cmodel_plan.model_uuid] += len(
                        cmodel_plan.backend_plans
                    )

        return ref_count_dict

    def _compute_last_requesting_cmodel_ref_count(self) -> Dict[str, int]:
        ref_count_dict: Dict[str, int] = {}

        for session_uuid in self.last_requests_dict:
            request = self.last_requests_dict[session_uuid]
            for cmodel in request.pipeline_info.models:
                cmodel_uuid = cmodel.main_model.model_uuid

                if cmodel_uuid not in ref_count_dict:
                    ref_count_dict[cmodel_uuid] = 0

                ref_count_dict[cmodel_uuid] += 1

        return ref_count_dict

    def _take_resource_from_backend(
        self, backend: BackendInfo, required_res: RequiredResouce
    ):
        if required_res.max_gpu_mem > 0:
            backend.state.gpu_info.gpu_total_mem -= required_res.max_gpu_mem

    def _return_resource_to_backend(
        self, backend: BackendInfo, required_res: RequiredResouce
    ):
        if required_res.max_gpu_mem > 0:
            # backend.gpu_info_extended.static_gpu_avaible_mem += required_res.max_gpu_mem
            backend.state.gpu_info.gpu_total_mem += required_res.max_gpu_mem

    def _compute_required_resource_for_atomic_model(
        self, cmodel: NxsCompositoryModel
    ) -> RequiredResouce:
        required_res = RequiredResouce()

        for component_model in cmodel.component_models:
            required_res.max_gpu_mem += (
                self._compute_required_resource_for_component_model(
                    component_model
                ).max_gpu_mem
            )

        return required_res

    def _compute_required_resource_for_component_model(
        self, component_model: NxsModel
    ) -> RequiredResouce:
        best_profile = self._get_best_profile(component_model)

        required_res = RequiredResouce()
        required_res.max_gpu_mem = best_profile.gpu_mem_usage

        return required_res

    def _get_best_profile(self, component_model: NxsModel) -> ProfileUnit:
        best_profile_unit = None

        fps = 0
        for profile_unit in component_model.profile:
            if profile_unit.fps > fps:
                fps = profile_unit.fps
                best_profile_unit = profile_unit

        return best_profile_unit

    def update_backend_runtime_stats(self, backend_name: str, backend_states: Dict):
        pass
