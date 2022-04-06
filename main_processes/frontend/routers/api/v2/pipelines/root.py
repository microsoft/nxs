from typing import Union
from fastapi import APIRouter, File, Security, UploadFile
from fastapi import HTTPException, status
from fastapi import Depends
from fastapi.security import APIKeyHeader

from configs import *
from main_processes.frontend.args import parse_args
from main_processes.frontend.utils import download_from_direct_link, get_db, get_storage
from nxs_libs.object.pipeline_runtime import NxsPipelineRuntime
from nxs_libs.storage.nxs_blobstore import NxsAzureBlobStorage
from nxs_types.message import NxsMsgPinWorkload, NxsMsgUnpinWorkload
from nxs_utils.nxs_helper import *
from nxs_utils.common import *
from nxs_types.model import *

args = parse_args()

router = APIRouter(prefix="/pipelines")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

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


@router.post("/register", response_model=NxsPipelineRegistrationResponse)
async def register_pipeline(
    pipeline: NxsPipelineRegistrationRequest,
    authenticated: bool = Depends(check_api_key),
):
    try:
        return await _register_pipeline(pipeline)
    except Exception as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            str(e),
        )


@router.post("/pin")
async def submit_pin_pipeline_request(
    pipeline_uuid: str,
    session_uuid: str = "global",
    fps: int = 1,
    authenticated: bool = Depends(check_api_key),
):
    if fps <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "fps has to be positive.")

    pipeline = _get_pipeline_info(pipeline_uuid)
    if pipeline is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid pipeline_uuid.")

    msg = NxsMsgPinWorkload(
        pipeline_uuid=pipeline_uuid, session_uuid=session_uuid, fps=fps
    )
    queue_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)
    queue_pusher.push(GLOBAL_QUEUE_NAMES.WORKLOAD_MANAGER, msg)

    return {}


@router.post("/unpin")
async def submit_unpin_pipeline_request(
    pipeline_uuid: str,
    session_uuid: str = "global",
    authenticated: bool = Depends(check_api_key),
):
    pipeline = _get_pipeline_info(pipeline_uuid)
    if pipeline is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid pipeline_uuid.")

    msg = NxsMsgUnpinWorkload(pipeline_uuid=pipeline_uuid, session_uuid=session_uuid)
    queue_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)
    queue_pusher.push(GLOBAL_QUEUE_NAMES.WORKLOAD_MANAGER, msg)

    return {}


async def _register_pipeline(pipeline: NxsPipelineRegistrationRequest):
    model_uuids = []
    for independent_models in pipeline.pipeline_groups:
        for model_uuid in independent_models.colocated_model_uuids:
            model_uuids.append(model_uuid)

    db = get_db(args)

    for model_uuid in model_uuids:
        query_results = db.query(
            MONGODB_MODELS_COLLECTION_NAME,
            {"model_uuid": model_uuid},
        )
        if not query_results:
            raise Exception(f"Invalid model {model_uuid}.")

    for independent_models in pipeline.pipeline_groups:
        if len(independent_models.colocated_model_uuids) > 1:
            # we need to modify the first model to include the remaining model uuids
            sub_model_uuids = []
            for idx in range(1, len(independent_models.colocated_model_uuids)):
                sub_model_uuids.append(independent_models.colocated_model_uuids[idx])

            query = {
                "model_uuid": independent_models.colocated_model_uuids[0],
            }
            if args.db_use_shard_key:
                query[args.db_shard_key] = args.db_shard_value

            db.update(
                MONGODB_MODELS_COLLECTION_NAME,
                query,
                {
                    "model_type": "composite",
                    "collocated_model_uuids": sub_model_uuids,
                },
            )

    pipeline_uuid = generate_uuid()
    if (
        pipeline.predefined_pipeline_uuid is not None
        and pipeline.predefined_pipeline_uuid != ""
    ):
        pipeline_uuid = pipeline.predefined_pipeline_uuid

        query = {"pipeline_uuid": pipeline_uuid}
        if args.db_use_shard_key:
            query[args.db_shard_key] = args.db_shard_value

        query_results = db.query(MONGODB_PIPELINES_COLLECTION_NAME, query)
        if len(query_results) > 0:
            # pipeline_uuid existed
            raise Exception(f"Pipeline {pipeline_uuid} is already existed.")

    pipeline_models_uuid = []
    for independent_models in pipeline.pipeline_groups:
        pipeline_models_uuid.append(independent_models.colocated_model_uuids[0])

    data = {
        "pipeline_uuid": pipeline_uuid,
        "pipeline": pipeline_models_uuid,
        "is_collocated": False,
        "user_name": pipeline.user_name,
        "is_public": pipeline.is_public,
        "name": pipeline.name,
        "accuracy": pipeline.accuracy,
        "params": pipeline.params,
        "flops": pipeline.flops,
        "input_type": pipeline.input_type,
        "description": pipeline.description,
        "output_type": pipeline.output_type,
        "preproc_params": [params.dict() for params in pipeline.preproc_params],
        "postproc_params": [params.dict() for params in pipeline.postproc_params],
        "transform_params": [params.dict() for params in pipeline.transform_params],
    }

    if args.db_use_shard_key:
        data[args.db_shard_key] = args.db_shard_value

    db.insert(
        MONGODB_PIPELINES_COLLECTION_NAME,
        data,
    )
    db.close()

    return NxsPipelineRegistrationResponse(pipeline_uuid=pipeline_uuid)


def _get_pipeline_info(pipeline_uuid) -> Union[NxsPipelineInfo, None]:
    db = get_db(args)
    pipeline = NxsPipelineRuntime.get_from_db(pipeline_uuid, db)
    db.close()

    if pipeline is not None:
        return pipeline.get_pipeline_info()

    return None
