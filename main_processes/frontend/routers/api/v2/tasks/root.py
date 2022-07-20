import asyncio
import copy
import pickle
import time
from datetime import datetime
from re import T
from threading import Thread
from typing import Union

import fastapi
from configs import *
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Security,
    UploadFile,
    status,
)
from fastapi.security import APIKeyHeader
from main_processes.frontend.args import parse_args
from main_processes.frontend.utils import (
    async_download_to_memory,
    download_from_direct_link,
    download_to_memory,
    get_db,
    get_storage,
)
from nxs_libs.interface.frontend.simple_interface import (
    SimpleFrontendTaskSummaryProcessor,
)
from nxs_libs.object.pipeline_runtime import NxsPipelineRuntime
from nxs_libs.storage.nxs_blobstore import NxsAzureBlobStorage
from nxs_libs.storage.nxs_blobstore_async import NxsAsyncAzureBlobStorage
from nxs_types.backend import NxsBackendType
from nxs_types.frontend import (
    BasicResponse,
    FrontendModelPipelineWorkloadReport,
    FrontendWorkloadReport,
    TaskSummary,
)
from nxs_types.infer import (
    NxsInferBatchImageInputFromAzureBlobstore,
    NxsInferBatchImageInputFromUrl,
    NxsInferExtraParams,
    NxsInferImageInputFromAzureBlobstore,
    NxsInferImageInputFromUrl,
    NxsInferInput,
    NxsInferInputType,
    NxsInferRequest,
    NxsInferStatus,
    NxsInferTextInput,
    NxsTensorsInferRequest,
)
from nxs_types.infer_result import (
    NxsInferResult,
    NxsInferResultType,
    NxsInferResultWithMetadata,
)
from nxs_types.log import (
    NxsBackendCmodelThroughputLog,
    NxsBackendDeploymentsLog,
    NxsBackendThroughputLog,
    NxsSchedulerLog,
)
from nxs_types.message import (
    NxsMsgPinWorkload,
    NxsMsgReportInputWorkloads,
    NxsMsgUnpinWorkload,
)
from nxs_types.model import *
from nxs_utils.common import *
from nxs_utils.logging import NxsLogLevel, setup_logger, write_log
from nxs_utils.nxs_helper import *

# setup global variables
args = parse_args()
router = APIRouter(prefix="/tasks")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

setup_logger()

task_summary_processor = SimpleFrontendTaskSummaryProcessor()

pipeline_cache: Dict[str, NxsPipelineInfo] = {}
tasks_data = []
tasks_summary_data = []
session_params = {}

task_result_dict = {}
task_result_t0_dict = {}

shared_queue_pusher: NxsQueuePusher = None
redis_kv_server: NxsSimpleKeyValueDb = None

backend_infos: List[NxsBackendThroughputLog] = []
backend_infos_t0 = 0

scheduler_info: NxsSchedulerLog = None
scheduler_info_t0 = 0

# FIXME: find a better way to do x-api-key check
async def check_api_key(api_key_header: str = Security(api_key_header)):
    if args.api_key == "":
        return True

    if api_key_header != args.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="wrong api key",
        )

    return True


def task_monitor_thread():
    global tasks_data, tasks_summary_data, task_summary_processor
    task_dict: Dict[str, FrontendModelPipelineWorkloadReport] = {}
    task_ts_dict = {}
    task_ts0_dict = {}
    task_fps_dict = {}

    queue_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)

    t0 = time.time()
    while True:
        to_trigger_wl_manager = False

        for _ in range(len(tasks_data)):
            pipeline_uuid, session_uuid = tasks_data.pop(0)
            key = f"{pipeline_uuid}_{session_uuid}"

            if key not in task_dict:
                task_dict[key] = FrontendModelPipelineWorkloadReport(
                    pipeline_uuid=pipeline_uuid,
                    session_uuid=session_uuid,
                    fps=0,
                )
                task_ts0_dict[key] = time.time()
                task_fps_dict[key] = 0
                to_trigger_wl_manager = True

            task_fps_dict[key] += 1
            task_ts_dict[key] = time.time()

        if to_trigger_wl_manager or time.time() - t0 > args.workload_report_period_secs:
            keys_to_clean = []
            cur_ts = time.time()
            for key in task_ts0_dict:
                if cur_ts - task_ts0_dict[key] > args.model_caching_timeout_secs:
                    keys_to_clean.append(key)

            for key in keys_to_clean:
                task_dict.pop(key)
                task_ts_dict.pop(key)
                task_ts0_dict.pop(key)
                task_fps_dict.pop(key)

            workload_reports = []

            for key in task_dict:
                wl = task_dict[key]
                if task_fps_dict[key] > 0:
                    # wl.fps = task_fps_dict[key] / max(1, (time.time() - task_ts0_dict[key]))
                    wl.fps = task_fps_dict[key]
                    workload_reports.append(task_dict[key])

            if workload_reports:
                metadata = task_summary_processor.process_summaries(tasks_summary_data)
                tasks_summary_data.clear()

                msg = NxsMsgReportInputWorkloads(
                    data=FrontendWorkloadReport(
                        frontend_name=args.frontend_name,
                        workload_reports=workload_reports,
                        metadata=json.dumps(metadata),
                    )
                )

                queue_pusher.push(GLOBAL_QUEUE_NAMES.WORKLOAD_MANAGER, msg)

                # print("SENT", msg)

            # reset all fps
            for key in task_fps_dict:
                task_fps_dict[key] = 0

            t0 = time.time()

        time.sleep(0.01)


def task_result_recv_thread():
    global args, task_result_dict, task_result_t0_dict

    queue_puller = create_queue_puller_from_args(
        args, NxsQueueType.REDIS, args.frontend_name
    )

    cleanup_t0 = time.time()
    expiration_secs = 60

    while True:
        msgs = queue_puller.pull()

        for msg in msgs:
            msg: NxsInferResult = msg
            task_result_dict[msg.task_uuid] = msg
            task_result_t0_dict[msg.task_uuid] = time.time()

            # print("RECV", msg)

        if time.time() - cleanup_t0 > 60:
            # clean up some unused data
            cur_ts = time.time()
            to_remove_task_uuids = []
            for task_uuid in task_result_t0_dict:
                if cur_ts - task_result_t0_dict[task_uuid] > 3 * expiration_secs:
                    to_remove_task_uuids.append(task_uuid)

            for task_uuid in to_remove_task_uuids:
                task_result_t0_dict.pop(task_uuid, None)
                task_result_dict.pop(task_uuid, None)

        time.sleep(0.002)


def setup():
    global shared_queue_pusher, redis_kv_server

    task_monitor_thr = Thread(target=task_monitor_thread, args=())
    task_monitor_thr.start()

    task_recv_thr = Thread(target=task_result_recv_thread, args=())
    task_recv_thr.start()

    shared_queue_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)
    redis_kv_server = create_simple_key_value_db_from_args(
        args, NxsSimpleKeyValueDbType.REDIS
    )


if shared_queue_pusher is None:
    setup()


@router.post("/sessions/create")
async def create_session(
    extra_params_json_str: str = "{}",
    authenticated: bool = Depends(check_api_key),
):
    global redis_kv_server

    try:
        extra_params = json.loads(extra_params_json_str)
    except:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "extra_params_json_str has to be json string.",
        )

    session_uuid = generate_uuid()

    key = f"{session_uuid}_params"
    redis_kv_server.set_value(key, extra_params)

    # store data into redis server

    return {"session_uuid": session_uuid}


@router.post("/sessions/delete")
async def delete_session(
    session_uuid: str, authenticated: bool = Depends(check_api_key)
):
    key = f"{session_uuid}_params"
    redis_kv_server.delete_key(key)
    return {}


@router.post("/images/infer-from-file", response_model=NxsInferResult)
async def submit_image_task(
    pipeline_uuid: str,
    session_uuid: str = "global",
    file: UploadFile = File(...),
    extra_params_json_str: str = '{"preproc": {}, "postproc": {}, "transform": {}}',
    infer_timeout: float = 10,
    authenticated: bool = Depends(check_api_key),
):
    image_bin = await file.read()

    extra_params = {}
    try:
        extra_params = json.loads(extra_params_json_str)
    except Exception as e:
        write_log(
            "/v2/images/infer-from-file",
            "Exception: {}".format(str(e)),
            NxsLogLevel.INFO,
        )

    extra_params = NxsInferExtraParams(**extra_params)

    try:
        res = await _infer_single(
            image_bin, pipeline_uuid, session_uuid, extra_params, infer_timeout
        )
    except Exception as e:
        write_log(
            "/v2/images/infer-from-file",
            "Exception: {}".format(str(e)),
            NxsLogLevel.INFO,
        )
        return NxsInferResult(
            type=NxsInferResultType.CUSTOM,
            status=NxsInferStatus.FAILED,
            task_uuid="",
            error_msgs=[str(e)],
        )

    return res


@router.post("/images/infer-from-url", response_model=NxsInferResult)
async def submit_image_task_from_url(
    infer_info: NxsInferImageInputFromUrl,
    authenticated: bool = Depends(check_api_key),
):
    return await process_image_task_from_url(
        infer_info.pipeline_uuid,
        infer_info.session_uuid,
        infer_info.url,
        infer_info.extra_params,
        infer_info.infer_timeout,
    )


@router.post("/images/batch-infer-from-url", response_model=List[NxsInferResult])
async def submit_batch_image_task_from_url(
    infer_info: NxsInferBatchImageInputFromUrl,
    authenticated: bool = Depends(check_api_key),
):
    tasks = []
    for url in infer_info.urls:
        tasks.append(
            process_image_task_from_url(
                infer_info.pipeline_uuid,
                infer_info.session_uuid,
                url,
                infer_info.extra_params,
                infer_info.infer_timeout,
            )
        )

    return await asyncio.gather(*tasks)


async def process_image_task_from_url(
    pipeline_uuid: str,
    session_uuid: str,
    url: str,
    extra_params: NxsInferExtraParams = NxsInferExtraParams(),
    infer_timeout: float = 10,
) -> NxsInferResult:
    try:
        image_bin = await async_download_to_memory(url)
        return await _infer_single(
            image_bin, pipeline_uuid, session_uuid, extra_params, infer_timeout
        )
    except Exception as e:
        write_log(
            "process_image_task_from_url",
            "Exception: {}".format(str(e)),
            NxsLogLevel.INFO,
        )
        return NxsInferResult(
            type=NxsInferResultType.CUSTOM,
            status=NxsInferStatus.FAILED,
            task_uuid="",
            error_msgs=[str(e)],
        )


@router.post("/images/infer-from-blobstore", response_model=NxsInferResult)
async def submit_image_task_from_azure_blobstore(
    infer_info: NxsInferImageInputFromAzureBlobstore,
    authenticated: bool = Depends(check_api_key),
):
    external_model_store = NxsAsyncAzureBlobStorage.from_sas_token(
        account_name=infer_info.blobstore_account_name,
        sas_token=infer_info.blobstore_sas_token,
        container_name=infer_info.blobstore_container_name,
    )
    res = await process_image_task_from_azure_blobstore(
        infer_info.pipeline_uuid,
        infer_info.session_uuid,
        infer_info.blobstore_path,
        external_model_store,
        infer_info.extra_params,
        infer_info.infer_timeout,
    )

    await external_model_store.close()

    return res


@router.post("/images/batch-infer-from-blobstore", response_model=List[NxsInferResult])
async def submit_batch_image_task_from_azure_blobstore(
    infer_info: NxsInferBatchImageInputFromAzureBlobstore,
    authenticated: bool = Depends(check_api_key),
):
    external_model_store = NxsAsyncAzureBlobStorage.from_sas_token(
        account_name=infer_info.blobstore_account_name,
        sas_token=infer_info.blobstore_sas_token,
        container_name=infer_info.blobstore_container_name,
    )

    tasks = []
    for blobstore_path in infer_info.blobstore_paths:
        tasks.append(
            process_image_task_from_azure_blobstore(
                infer_info.pipeline_uuid,
                infer_info.session_uuid,
                blobstore_path,
                external_model_store,
                infer_info.extra_params,
                infer_info.infer_timeout,
            )
        )

    results = await asyncio.gather(*tasks)

    await external_model_store.close()

    return results


async def process_image_task_from_azure_blobstore(
    pipeline_uuid: str,
    session_uuid: str,
    blobstore_path: str,
    external_model_store: NxsAsyncAzureBlobStorage,
    extra_params: NxsInferExtraParams = NxsInferExtraParams(),
    infer_timeout: float = 10,
) -> NxsInferResult:
    try:
        image_bin = await external_model_store.download(blobstore_path)
        return await _infer_single(
            image_bin, pipeline_uuid, session_uuid, extra_params, infer_timeout
        )
    except Exception as e:
        write_log(
            "process_image_task_from_azure_blobstore",
            "Exception: {}".format(str(e)),
            NxsLogLevel.INFO,
        )
        return NxsInferResult(
            type=NxsInferResultType.CUSTOM,
            status=NxsInferStatus.FAILED,
            task_uuid="",
            error_msgs=[str(e)],
        )


@router.post("/texts/infer", response_model=NxsInferResult)
async def submit_text_task(
    infer_info: NxsInferTextInput,
    authenticated: bool = Depends(check_api_key),
):
    session_uuid: str = "global"
    if infer_info.session_uuid is not None:
        session_uuid = infer_info.session_uuid

    try:
        res = await _infer_single(
            infer_info.text,
            infer_info.pipeline_uuid,
            session_uuid,
            infer_info.extra_params,
            infer_info.infer_timeout,
        )
    except Exception as e:
        write_log(
            "/v2/texts/infer",
            "Exception: {}".format(str(e)),
            NxsLogLevel.INFO,
        )
        return NxsInferResult(
            type=NxsInferResultType.CUSTOM,
            status=NxsInferStatus.FAILED,
            task_uuid="",
            error_msgs=[str(e)],
        )

    return res


@router.post("/tensors/infer", response_model=NxsInferResult)
async def submit_task_tensors(
    request: Request,
    authenticated: bool = Depends(check_api_key),
):
    data: bytes = await request.body()
    infer_request = pickle.loads(data)

    if isinstance(infer_request, Dict):
        try:
            infer_request = NxsTensorsInferRequest(**infer_request)
        except Exception as e:
            # raise HTTPException(
            #     status.HTTP_400_BAD_REQUEST,
            #     "request should be a pickled bytes of NxsTensorsInferRequest instance or a pickled bytes of NxsTensorsInferRequest dict.",
            # )

            write_log(
                "/v2/tensors/infer",
                "Exception: {}".format(str(e)),
                NxsLogLevel.INFO,
            )

            return NxsInferResult(
                type=NxsInferResultType.CUSTOM,
                status=NxsInferStatus.FAILED,
                task_uuid="",
                error_msgs=[
                    "request should be a pickled bytes of NxsTensorsInferRequest instance or a pickled bytes of NxsTensorsInferRequest dict."
                ],
            )

    if not isinstance(infer_request, NxsTensorsInferRequest):
        # raise HTTPException(
        #     status.HTTP_400_BAD_REQUEST,
        #     "request should be a pickled bytes of NxsTensorsInferRequest instance or a pickled bytes of NxsTensorsInferRequest dict.",
        # )

        error_msg = "request should be a pickled bytes of NxsTensorsInferRequest instance or a pickled bytes of NxsTensorsInferRequest dict."

        write_log(
            "/v2/tensors/infer",
            "Exception: {}".format(error_msg),
            NxsLogLevel.INFO,
        )

        return NxsInferResult(
            type=NxsInferResultType.CUSTOM,
            status=NxsInferStatus.FAILED,
            task_uuid="",
            error_msgs=[error_msg],
        )
    else:
        infer_request: NxsTensorsInferRequest = infer_request

    try:
        res = await _infer_tensors(infer_request)
    except Exception as e:
        write_log(
            "/v2/tensors/infer",
            "Exception: {}".format(str(e)),
            NxsLogLevel.INFO,
        )

        return NxsInferResult(
            type=NxsInferResultType.CUSTOM,
            status=NxsInferStatus.FAILED,
            task_uuid="",
            error_msgs=[str(e)],
        )

    return res


if args.enable_benchmark_api:

    @router.post("/benchmarks/redis")
    async def submit_benchmark_redis_task(
        file: UploadFile = File(...),
        authenticated: bool = Depends(check_api_key),
    ):
        global shared_queue_pusher
        image_bin = await file.read()

        # send this to redis
        task_uuid = generate_uuid()
        infer_result = NxsInferResultWithMetadata(
            type=NxsInferResultType.CUSTOM,
            status=NxsInferStatus.COMPLETED,
            task_uuid=task_uuid,
            metadata=image_bin,
        )
        shared_queue_pusher.push(args.frontend_name, infer_result)

        # wait for result
        result = {}
        while True:
            if task_uuid not in task_result_dict:
                # time.sleep(0.01)
                await asyncio.sleep(0.0025)
                continue

            result = task_result_dict.pop(task_uuid)
            break

        return {"status": "COMPLETED"}


if args.enable_scaling:

    """
    def get_num_deployment_replicas(deployment_name: str) -> int:
        num_replicas = 0
        deployment_items = []

        try:
            from kubernetes import client, config

            config.load_kube_config()

            api_instance = client.AppsV1Api()
            deployment = api_instance.list_namespaced_deployment(namespace="nxs")
            deployment_items = deployment.items
        except Exception as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Internal error. Please try again later.",
            )

        for item in deployment_items:
            if "name" not in item.metadata.labels:
                continue

            if item.metadata.labels["name"] == deployment_name:
                num_replicas = item.spec.replicas

        return num_replicas
    """

    def get_deployment_replicas_info(deployment_name: str) -> Tuple[int, int]:
        num_replicas = 0
        num_ready_replicas = 0

        deployment_items = []

        try:
            from kubernetes import client, config

            config.load_kube_config()

            api_instance = client.AppsV1Api()
            deployment = api_instance.list_namespaced_deployment(namespace="nxs")
            deployment_items = deployment.items
        except Exception as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Internal error. Please try again later.",
            )

        for item in deployment_items:
            if "name" not in item.metadata.labels:
                continue

            if item.metadata.labels["name"] == deployment_name:
                try:
                    num_replicas = item.spec.replicas
                    num_ready_replicas = item.status.ready_replicas
                except:
                    pass

        if num_replicas is None:
            num_replicas = 0
        if num_ready_replicas is None:
            num_ready_replicas = 0

        return num_replicas, num_ready_replicas

    @router.post("/backends/scale/gpu", response_model=BasicResponse)
    async def scale_backends(
        num_backends: int,
        force_scaling: bool = False,
        authenticated: bool = Depends(check_api_key),
    ):
        if num_backends < 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "num_backends must be at least 0",
            )

        (
            num_requested_gpu_backends,
            num_available_gpu_backends,
        ) = get_deployment_replicas_info("nxs-backend-gpu")

        if (
            num_requested_gpu_backends != num_available_gpu_backends
            and not force_scaling
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Scaling is in process, please retry later after a few minutes.",
            )

        deployment_items = []

        try:
            from kubernetes import client, config

            config.load_kube_config()

            api_instance = client.AppsV1Api()
            deployment = api_instance.list_namespaced_deployment(namespace="nxs")
            deployment_items = deployment.items
        except Exception as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Internal error. Please try again later.",
            )

        found_gpu_backend_deployment = False
        for item in deployment_items:
            if "name" not in item.metadata.labels:
                continue

            if item.metadata.labels["name"] == "nxs-backend-gpu":
                item.spec.replicas = num_backends

                try:
                    api_response = api_instance.patch_namespaced_deployment(
                        "nxs-backend-gpu", "nxs", item
                    )

                    found_gpu_backend_deployment = True
                except Exception as e:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        "Internal error. Please try again later.",
                    )

        if not found_gpu_backend_deployment:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Could not find nxs-backend-gpu deployment.",
            )

        return BasicResponse(is_successful=True)


def get_backend_logs() -> List[NxsBackendThroughputLog]:
    global redis_kv_server

    logs = redis_kv_server.get_value(GLOBAL_QUEUE_NAMES.BACKEND_MONITOR_LOGS)
    if logs is None:
        logs = []

    return logs


@router.get("/monitoring/backends", response_model=List[NxsBackendThroughputLog])
async def get_monitoring_backend_reports(
    authenticated: bool = Depends(check_api_key),
):
    global redis_kv_server, backend_infos, backend_infos_t0

    logs = get_backend_logs()

    backend_infos_t0 = time.time()
    backend_infos = logs

    return logs


if args.enable_scaling:

    @router.get(
        "/monitoring/backend_deployments", response_model=NxsBackendDeploymentsLog
    )
    async def get_backend_deployments(
        authenticated: bool = Depends(check_api_key),
    ):
        num_requested_cpu_backends = 0
        num_requested_gpu_backends = 0
        num_available_cpu_backends = 0
        num_available_gpu_backends = 0

        # backend_infos = get_backend_logs()
        # for backend_info in backend_infos:
        #     if backend_info.backend_type == NxsBackendType.CPU:
        #         num_available_cpu_backends += 1
        #     elif backend_info.backend_type == NxsBackendType.GPU:
        #         num_available_gpu_backends += 1

        # num_requested_cpu_backends = get_num_deployment_replicas("nxs-backend-cpu")
        # num_requested_gpu_backends = get_num_deployment_replicas("nxs-backend-gpu")

        (
            num_requested_cpu_backends,
            num_available_cpu_backends,
        ) = get_deployment_replicas_info("nxs-backend-cpu")
        (
            num_requested_gpu_backends,
            num_available_gpu_backends,
        ) = get_deployment_replicas_info("nxs-backend-gpu")

        return NxsBackendDeploymentsLog(
            num_requested_cpu_backends=num_requested_cpu_backends,
            num_available_cpu_backends=num_available_cpu_backends,
            num_requested_gpu_backends=num_requested_gpu_backends,
            num_available_gpu_backends=num_available_gpu_backends,
        )


def get_scheduler_log() -> NxsSchedulerLog:
    global redis_kv_server

    scheduler_log: NxsSchedulerLog = redis_kv_server.get_value(
        GLOBAL_QUEUE_NAMES.SCHEDULER_LOGS
    )

    if scheduler_log is None:
        scheduler_log = NxsSchedulerLog()

    return scheduler_log


@router.get("/monitoring/scheduler", response_model=NxsSchedulerLog)
async def get_monitoring_scheduler_report(
    authenticated: bool = Depends(check_api_key),
):
    global scheduler_info, scheduler_info_t0

    scheduler_info = get_scheduler_log()
    scheduler_info_t0 = time.time()

    return scheduler_info


async def _infer_single(
    data: Union[bytes, str],
    pipeline_uuid: str,
    session_uuid: str,
    users_extra_params: NxsInferExtraParams = NxsInferExtraParams(),
    infer_timeout: float = 10,
) -> NxsInferResult:
    global tasks_data, shared_queue_pusher, task_result_dict, tasks_summary_data
    global task_summary_processor, session_params, redis_kv_server
    global backend_infos_t0, backend_infos
    global scheduler_info, scheduler_info_t0

    entry_t0 = time.time()

    if entry_t0 - backend_infos_t0 > 15:
        backend_infos = get_backend_logs()
        backend_infos_t0 = time.time()

    if not backend_infos:
        raise Exception("No backend is available.")

    to_wait = True
    if not args.wait_for_models:
        if entry_t0 - scheduler_info_t0 > 15:
            scheduler_info = get_scheduler_log()
            scheduler_info_t0 = time.time()

        cmodel_uuids: List[str] = []
        for request in scheduler_info.scheduling_requests:
            if request.pipeline_uuid == pipeline_uuid:
                cmodel_uuids.extend(request.cmodel_uuid_list)

        if not cmodel_uuids:
            # models are not scheduled yet
            to_wait = False

        for cmodel_uuid in cmodel_uuids:
            found_cmodel = False
            for plan in scheduler_info.scheduling_plans:
                for cmodel_uuid_on_backend in plan.cmodel_uuid_list:
                    if cmodel_uuid_on_backend == cmodel_uuid:
                        found_cmodel = True
                        break

                if found_cmodel:
                    break

            if not found_cmodel:
                to_wait = False
                break

    task_uuid = generate_uuid()

    task_summary = TaskSummary(
        pipeline_uuid=pipeline_uuid,
        session_uuid=session_uuid,
        task_uuid=task_uuid,
        start_ts=entry_t0,
    )

    task_summary_processor.pre_task_processing(task_summary)

    pipeline = _get_pipeline_info(pipeline_uuid)

    if pipeline is None:
        raise Exception("invalid pipeline uuid")

    # num_inputs = len(pipeline.models[0].component_models[0].model_desc.inputs)
    # if num_inputs > 1:
    #     raise Exception("This api only works with single input models.")

    # num_shape_dims = len(
    #     pipeline.models[0].component_models[0].model_desc.inputs[0].shape
    # )
    # if num_shape_dims != 4:
    #     raise HTTPException(
    #         status.HTTP_400_BAD_REQUEST,
    #         "This api only works on input with 4 dims.",
    #     )

    tasks_data.append((pipeline_uuid, session_uuid))

    if not to_wait:
        raise Exception("Model is not ready to serve. Please try again later.")

    pipeline_uuids = copy.deepcopy(pipeline.pipeline)
    pipeline_uuids.append(args.frontend_name)

    model_input = pipeline.models[0].component_models[0].model_desc.inputs[0]
    model_input_type = NxsInferInputType.ENCODED_IMAGE
    if isinstance(data, str):
        model_input_type = NxsInferInputType.PICKLED_DATA
        data = pickle.dumps(data)

    next_topic = pipeline_uuids.pop(0)

    _extra_params = _get_session_params(session_uuid)
    infer_task = NxsInferRequest(
        task_uuid=task_uuid,
        session_uuid=session_uuid,
        exec_pipelines=pipeline_uuids,
        inputs=[
            NxsInferInput(
                name=model_input.name,
                type=model_input_type,
                data=data,
            )
        ],
        extra_preproc_params=json.dumps(users_extra_params.preproc),
        extra_transform_params=json.dumps(users_extra_params.transform),
        extra_postproc_params=json.dumps(users_extra_params.postproc),
        extra_params=json.dumps(_extra_params),
    )

    # shared_queue_pusher.push(next_topic, infer_task)
    shared_queue_pusher.push_to_session(next_topic, session_uuid, infer_task)

    # wait for result
    result = {}
    while True:
        if time.time() - entry_t0 > infer_timeout:
            raise Exception("Request timeout")

        if task_uuid not in task_result_dict:
            # time.sleep(0.01)
            await asyncio.sleep(0.0025)
            continue

        result = task_result_dict.pop(task_uuid)
        break

    task_summary.end_ts = time.time()
    task_summary.e2e_latency = task_summary.end_ts - entry_t0

    if isinstance(result, NxsInferResult):
        result.e2e_latency = task_summary.e2e_latency

    task_summary_processor.post_task_processing(task_summary)
    tasks_summary_data.append(task_summary)

    return NxsInferResult(**(result.dict()))


async def _infer_tensors(infer_request: NxsTensorsInferRequest):
    global tasks_data, shared_queue_pusher, task_result_dict
    global tasks_summary_data, task_summary_processor, session_params, redis_kv_server
    global backend_infos_t0, backend_infos

    entry_t0 = time.time()

    if entry_t0 - backend_infos_t0 > 15:
        backend_infos = get_backend_logs()
        backend_infos_t0 = time.time()

    if not backend_infos:
        raise Exception("No backend is available. Please bring up some backends.")

    task_uuid = generate_uuid()
    task_summary = TaskSummary(
        pipeline_uuid=infer_request.pipeline_uuid,
        session_uuid=infer_request.session_uuid,
        task_uuid=task_uuid,
        start_ts=entry_t0,
    )

    task_summary_processor.pre_task_processing(task_summary)
    pipeline = _get_pipeline_info(infer_request.pipeline_uuid)

    if pipeline is None:
        raise Exception("invalid pipeline uuid")

    tasks_data.append((infer_request.pipeline_uuid, infer_request.session_uuid))

    pipeline_uuids = copy.deepcopy(pipeline.pipeline)
    pipeline_uuids.append(args.frontend_name)

    next_topic = pipeline_uuids.pop(0)

    extra_params = _get_session_params(infer_request.session_uuid)
    infer_task = NxsInferRequest(
        task_uuid=task_uuid,
        session_uuid=infer_request.session_uuid,
        exec_pipelines=pipeline_uuids,
        inputs=infer_request.inputs,
        extra_preproc_params=infer_request.extra_preproc_params,
        extra_transform_params=infer_request.extra_transform_params,
        extra_postproc_params=infer_request.extra_postproc_params,
        extra_params=json.dumps(extra_params),
    )

    # shared_queue_pusher.push(next_topic, infer_task)
    shared_queue_pusher.push_to_session(
        next_topic, infer_request.session_uuid, infer_task
    )

    # wait for result
    result = {}
    while True:
        if time.time() - entry_t0 > infer_request.infer_timeout:
            raise Exception("Request timeout")

        if task_uuid not in task_result_dict:
            # time.sleep(0.01)
            await asyncio.sleep(0.0025)
            continue

        result = task_result_dict.pop(task_uuid)
        break

    task_summary.end_ts = time.time()
    task_summary.e2e_latency = task_summary.end_ts - entry_t0

    if isinstance(result, NxsInferResult):
        result.e2e_latency = task_summary.e2e_latency

    task_summary_processor.post_task_processing(task_summary)
    tasks_summary_data.append(task_summary)

    return NxsInferResult(**(result.dict()))


def _get_pipeline_info(pipeline_uuid) -> Union[NxsPipelineInfo, None]:
    global pipeline_cache

    if pipeline_uuid in pipeline_cache:
        return pipeline_cache[pipeline_uuid]

    db = get_db(args)
    pipeline = NxsPipelineRuntime.get_from_db(pipeline_uuid, db)
    db.close()

    if pipeline is not None:
        pipeline_cache[pipeline_uuid] = pipeline.get_pipeline_info()
        return pipeline_cache[pipeline_uuid]

    return None


def _get_session_params(session_uuid) -> Dict:
    global session_params, redis_kv_server

    extra_params = {}
    if session_uuid not in session_params:
        extra_params = redis_kv_server.get_value(session_uuid)
        if extra_params is None:
            extra_params = {}
        else:
            session_params[session_uuid] = extra_params

    return extra_params
