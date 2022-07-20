import json
from multiprocessing.connection import wait
from typing import List, Optional

import fastapi
from configs import MONGODB_PIPELINES_COLLECTION_NAME
from fastapi import APIRouter, Depends, File, HTTPException, Security, UploadFile
from fastapi.security import APIKeyHeader
from main_processes.frontend.args import parse_args
from main_processes.frontend.routers.api.v2.models.root import _register_w4_model
from main_processes.frontend.routers.api.v2.tasks.root import _infer_single
from main_processes.frontend.utils import get_db
from nxs_types.infer import NxsInferStatus
from nxs_types.infer_result import NxsInferResult, NxsInferResultType
from nxs_types.model import DataModel, NxsW4ModelRegistrationRequest
from nxs_utils.logging import NxsLogLevel, setup_logger, write_log

args = parse_args()
router = APIRouter(prefix="/v1")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

setup_logger()


class ModelRegistrationRequestv1(DataModel):
    model_owner: str
    model_framework: str = "onnx"
    model_name: str
    pixie_store_sas_token: str
    pixie_store_account_name: str
    pixie_store_container_name: str
    pixie_model_dir_path: str
    model_classes: Optional[List[str]] = []


# FIXME: find a better way to do x-api-key check
async def check_api_key(api_key_header: str = Security(api_key_header)):
    if args.api_key == "":
        return True

    if api_key_header != args.api_key:
        raise HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail="wrong api key",
        )

    return True


def register_root_apis(router: APIRouter):
    @router.post(
        "/register_classifier_v2",
        deprecated=True,
    )
    async def register_classifier_v2(
        registering_model: ModelRegistrationRequestv1,
        authenticated: bool = Depends(check_api_key),
    ):
        res = await _register_w4_model_from_v1(registering_model, "classifier")
        return res

    @router.post("/register_detector_v1", deprecated=True)
    async def register_detector_v1(
        registering_model: ModelRegistrationRequestv1,
        authenticated: bool = Depends(check_api_key),
    ):
        res = await _register_w4_model_from_v1(registering_model, "detector")
        return res


@router.get("/model_status", deprecated=True)
async def check_model_status(
    model_uuid: str,
    authenticated: bool = Depends(check_api_key),
):
    model_status = 2

    db = get_db(args)
    query = {"pipeline_uuid": model_uuid}
    if args.db_use_shard_key:
        query[args.db_shard_key] = args.db_shard_value

    query_results = db.query(MONGODB_PIPELINES_COLLECTION_NAME, query)
    if len(query_results) > 0:
        model_status = 1

    return {"model_status": model_status}


@router.post("/fromfile", deprecated=True)
async def infer_from_file(
    datas: UploadFile = File(...),
    file: UploadFile = File(...),
    authenticated: bool = Depends(check_api_key),
):

    json_data = await datas.read()
    json_data = json.loads(json_data)
    binaray_data = await file.read()

    pipeline_uuid = json_data["model_uuid"]

    try:
        res: NxsInferResult = await _infer_single(binaray_data, pipeline_uuid, "global")
        # reconstruct v1 result
        return _reconstruct_v1_result(res)
    except Exception as e:
        write_log("/v1/fromfile", "Exception: {}".format(str(e)), NxsLogLevel.INFO)
        return {"error": str(e)}


async def _register_w4_model_from_v1(
    registering_model: ModelRegistrationRequestv1, registering_model_type: str
):
    w4_registering_model = NxsW4ModelRegistrationRequest(
        user_name=registering_model.model_owner,
        model_name=registering_model.model_name,
        blobstore_account_name=registering_model.pixie_store_account_name,
        blobstore_container_name=registering_model.pixie_store_container_name,
        blobstore_sas_token=registering_model.pixie_store_sas_token,
        blobstore_path=registering_model.pixie_model_dir_path,
    )
    try:
        res = await _register_w4_model(w4_registering_model, registering_model_type)
        return {"model_uuid": res.pipeline_uuid}
    except Exception as e:
        raise HTTPException(
            fastapi.status.HTTP_400_BAD_REQUEST,
            str(e),
        )


def _reconstruct_v1_result(infer_result: NxsInferResult):
    if infer_result.status == NxsInferStatus.FAILED:
        res = {"task_status": 1, "data": {}, "error": str(infer_result.error_msgs)}
        return res

    if infer_result.type == NxsInferResultType.DETECTION:
        return _reconstruct_v1_detector_result(infer_result)
    elif infer_result.type == NxsInferResultType.CLASSIFICATION:
        return _reconstruct_v1_classification_result(infer_result)
    elif infer_result.type == NxsInferResultType.OCR:
        return _reconstruct_v1_ocr_result(infer_result)

    return infer_result


def _reconstruct_v1_detector_result(infer_result: NxsInferResult):
    res = {}
    data = {}
    data["task_status"] = 0
    data["outputs"] = {}
    data["outputs"]["detections"] = []

    for det in infer_result.detections:
        data["outputs"]["detections"].append(
            {
                "class_name": det.class_name,
                "class_id": det.class_id,
                "score": det.score,
                "bbox": {
                    "left": det.bbox.left,
                    "right": det.bbox.right,
                    "top": det.bbox.top,
                    "bottom": det.bbox.bottom,
                },
                "rel_bbox": {
                    "rel_left": det.rel_bbox.left,
                    "rel_right": det.rel_bbox.right,
                    "rel_top": det.rel_bbox.top,
                    "ref_bottom": det.rel_bbox.bottom,
                },
            }
        )

    res["data"] = data

    return res


def _reconstruct_v1_ocr_result(infer_result: NxsInferResult):
    res = {}
    data = {}
    data["task_status"] = 0
    data["outputs"] = {}
    data["outputs"]["detections"] = []

    for det in infer_result.ocr:
        data["outputs"]["detections"].append(
            {
                "text": det.text,
                "text_probability": det.score,
                "box": [
                    [int(det.line_bbox[0].x), int(det.line_bbox[0].y)],
                    [int(det.line_bbox[1].x), int(det.line_bbox[1].y)],
                    [int(det.line_bbox[2].x), int(det.line_bbox[2].y)],
                    [int(det.line_bbox[3].x), int(det.line_bbox[3].y)],
                ],
                "rel_box": [
                    [det.line_rbbox[0].x, det.line_rbbox[0].y],
                    [det.line_rbbox[1].x, det.line_rbbox[1].y],
                    [det.line_rbbox[2].x, det.line_rbbox[2].y],
                    [det.line_rbbox[3].x, det.line_rbbox[3].y],
                ],
            }
        )

    res["data"] = data

    return res


def _reconstruct_v1_classification_result(infer_result: NxsInferResult):
    res = {}
    data = {}
    data["task_status"] = 0
    data["outputs"] = {}

    data["outputs"]["probabilities"] = infer_result.classification.probabilities
    data["outputs"]["best_score"] = infer_result.classification.best_score
    data["outputs"]["predicted_class"] = infer_result.classification.predicted_class_id
    data["outputs"][
        "predicted_class_name"
    ] = infer_result.classification.predicted_class_name

    res["data"] = data
    return res
