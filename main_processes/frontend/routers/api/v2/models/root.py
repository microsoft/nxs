from fastapi import APIRouter, File, Security, UploadFile
from fastapi import HTTPException, status
from fastapi import Depends
from fastapi.security import APIKeyHeader

import time
from datetime import datetime
from main_processes.frontend.routers.api.v2.pipelines.root import _register_pipeline
from main_processes.frontend.utils import (
    async_download_to_file,
    download_from_direct_link,
    get_db,
    get_storage,
)
from nxs_libs.storage.nxs_blobstore import NxsAzureBlobStorage
from nxs_libs.storage.nxs_blobstore_async import NxsAsyncAzureBlobStorage

from nxs_utils.nxs_helper import *
from nxs_utils.common import *
from nxs_types.model import *

from configs import *
from main_processes.frontend.args import parse_args

args = parse_args()

router = APIRouter(prefix="/models")

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


@router.get("/public", response_model=List[NxsPipelineDescription])
async def get_public_models(
    authenticated: bool = Depends(check_api_key),
):
    results: List[NxsPipelineDescription] = []

    db = get_db(args)

    query = {"is_public": True}
    if args.db_use_shard_key:
        query[args.db_shard_key] = args.db_shard_value

    query_results = db.query(MONGODB_PIPELINES_COLLECTION_NAME, query)
    for r in query_results:
        results.append(
            NxsPipelineDescription(
                pipeline_uuid=r["pipeline_uuid"],
                name=r.get("name", "N/A"),
                accuracy=r.get("accuracy", "N/A"),
                params=r.get("params", "N/A"),
                flops=r.get("flops", "N/A"),
                input_type=r.get("input_type", "N/A"),
                description=r.get("description", "N/A"),
            )
        )

    db.close()

    return results


@router.post("/register", response_model=NxsModelRegistrationResponse)
async def submit_model(
    registering_model: NxsModelRegistrationRequest,
    authenticated: bool = Depends(check_api_key),
):
    model_uuid = generate_uuid()

    model_tmp_dir = os.path.join(args.tmp_dir, model_uuid)
    delete_and_create_dir(model_tmp_dir)

    if not registering_model.profile:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing profile.")

    has_bs1 = False
    for profile_unit in registering_model.profile:
        if profile_unit.batch_size == 1:
            has_bs1 = True
            break

    if not has_bs1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Missing profile for batch size of 1."
        )

    try:
        # print(f"Downloading preproc_fn from {registering_model.preproc_url}")
        preproc_path = ""
        if registering_model.preproc_url != "":
            preproc_dir = os.path.join(model_tmp_dir, "preproc")
            create_dir_if_needed(preproc_dir)
            preproc_path = os.path.join(preproc_dir, f"{model_uuid}.py")
            await async_download_to_file(registering_model.preproc_url, preproc_path)

        # print(f"Downloading postproc_fn from {registering_model.postproc_url}")
        postproc_path = ""
        if registering_model.postproc_url != "":
            postproc_dir = os.path.join(model_tmp_dir, "postproc")
            create_dir_if_needed(postproc_dir)
            postproc_path = os.path.join(postproc_dir, f"{model_uuid}.py")
            await async_download_to_file(registering_model.postproc_url, postproc_path)

        transform_path = ""
        if registering_model.transfrom_url != "":
            # print(f"Downloading transform_fn from {registering_model.transfrom_url}")
            transform_dir = os.path.join(model_tmp_dir, "transform")
            create_dir_if_needed(transform_dir)
            transform_path = os.path.join(transform_dir, f"{model_uuid}.py")
            await async_download_to_file(
                registering_model.transfrom_url, transform_path
            )

        # print(f"Downloading model from {registering_model.url}")
        model_path = os.path.join(model_tmp_dir, f"{model_uuid}")
        await async_download_to_file(registering_model.url, model_path)

        await _register_model(
            model_uuid,
            model_path,
            preproc_path,
            postproc_path,
            transform_path,
            registering_model,
        )

        return NxsModelRegistrationResponse(model_uuid=model_uuid)
    except Exception as e:
        raise e
    finally:
        delete_dir(model_tmp_dir)


"""
@router.post("/register-from-files")
async def infer_from_file(
    registering_model: NxsBaseModel,
    model: UploadFile = File(...),
    preprocessing: UploadFile = File(...),
    postprocessing: UploadFile = File(...),
    transforming: Optional[UploadFile] = File(...),
    authenticated: bool = Depends(check_api_key),
):
    model_uuid = generate_uuid()

    model_tmp_dir = os.path.join(args.tmp_dir, model_uuid)
    delete_and_create_dir(model_tmp_dir)

    if not registering_model.profile:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing profile.")

    has_bs1 = False
    for profile_unit in registering_model.profile:
        if profile_unit.batch_size == 1:
            has_bs1 = True
            break

    if not has_bs1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Missing profile for batch size of 1."
        )

    preproc_dir = os.path.join(model_tmp_dir, "preproc")
    create_dir_if_needed(preproc_dir)
    preproc_path = os.path.join(preproc_dir, f"{model_uuid}.py")
    with open(preproc_path, "wb") as f:
        data = await preprocessing.read()
        f.write(data)

    postproc_dir = os.path.join(model_tmp_dir, "postproc")
    create_dir_if_needed(postproc_dir)
    postproc_path = os.path.join(postproc_dir, f"{model_uuid}.py")
    with open(postproc_path, "wb") as f:
        data = await postprocessing.read()
        f.write(data)

    transform_path = ""
    if transforming:
        transform_dir = os.path.join(model_tmp_dir, "transform")
        create_dir_if_needed(transform_dir)
        transform_path = os.path.join(transform_dir, f"{model_uuid}.py")
        with open(transform_path, "wb") as f:
            data = await transforming.read()
            f.write(data)

    model_path = os.path.join(model_tmp_dir, f"{model_uuid}")
    with open(model_path, "wb") as f:
        data = await model.read()
        f.write(data)

    await _register_model(
        model_uuid,
        model_path,
        preproc_path,
        postproc_path,
        transform_path,
        registering_model,
    )

    return NxsModelRegistrationResponse(model_uuid=model_uuid)
"""


@router.post("/register-w4-model", response_model=NxsPipelineRegistrationResponse)
async def register_w4_model(
    registering_model: NxsW4ModelRegistrationRequest,
    registering_model_type: str,
    authenticated: bool = Depends(check_api_key),
):
    try:
        return await _register_w4_model(registering_model, registering_model_type)
    except Exception as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            str(e),
        )


async def _register_w4_model(
    registering_model: NxsW4ModelRegistrationRequest,
    registering_model_type: str,
) -> NxsPipelineRegistrationResponse:
    model_uuid = generate_uuid()

    model_tmp_dir = os.path.join(args.tmp_dir, model_uuid)
    delete_and_create_dir(model_tmp_dir)

    try:
        model_description_path = os.path.join(
            registering_model.blobstore_path, "model_description.json"
        )

        external_model_store = NxsAsyncAzureBlobStorage.from_sas_token(
            account_name=registering_model.blobstore_account_name,
            sas_token=registering_model.blobstore_sas_token,
            container_name=registering_model.blobstore_container_name,
        )

        desc_data = {}
        try:
            desc_data = await external_model_store.download(model_description_path)
            desc_data = json.loads(desc_data)
        except Exception as e:
            raise Exception(f"could not download model_description.json.")

        backbone = desc_data["input_model"]["backbone"].replace(
            " ", ""
        )  # use backbone to retrieve pre/trans/post processing fns

        model_type = desc_data["model_file_format"]
        if model_type != "onnx":
            raise Exception("This API only supports ONNX format.")

        model_input_sizes = desc_data["hyperparameters"]["input_resize_spec"]["sizes"]
        model_input_size = max(model_input_sizes)

        storage = get_storage(args)

        preproc_dir = os.path.join(model_tmp_dir, "preproc")
        create_dir_if_needed(preproc_dir)
        preproc_path = os.path.join(preproc_dir, f"{model_uuid}.py")
        try:
            preproc_data = storage.download(
                os.path.join(STORAGE_PREDEFINED_PREPROC_PATH, f"{backbone}.py")
            )
            with open(preproc_path, "wb") as f:
                f.write(preproc_data)
        except Exception as e:
            raise Exception(f"preprocessing function for {backbone} is not existed.")

        postproc_dir = os.path.join(model_tmp_dir, "postproc")
        create_dir_if_needed(postproc_dir)
        postproc_path = os.path.join(postproc_dir, f"{model_uuid}.py")
        try:
            postproc_data = storage.download(
                os.path.join(STORAGE_PREDEFINED_POSTPROC_PATH, f"{backbone}.py")
            )
            with open(postproc_path, "wb") as f:
                f.write(postproc_data)
        except Exception as e:
            raise Exception(f"postprocessing function for {backbone} is not existed.")

        transform_dir = os.path.join(model_tmp_dir, "transform")
        create_dir_if_needed(transform_dir)
        transform_path = os.path.join(transform_dir, f"{model_uuid}.py")
        try:
            transform_data = storage.download(
                os.path.join(STORAGE_PREDEFINED_TRANSFORM_PATH, f"{backbone}.py")
            )
            with open(transform_path, "wb") as f:
                f.write(transform_data)
        except Exception as e:
            transform_path = ""

        model_extras_info = {}
        try:
            model_extras_info_remote_path = os.path.join(
                STORAGE_PREDEFINED_EXTRAS_PATH, f"{backbone}_{model_type}.json"
            )
            extras_data = storage.download(model_extras_info_remote_path)
            model_extras_info = json.loads(extras_data)
            model_extras_info["use_gpu"] = bool(model_extras_info["use_gpu"])
            model_extras_info["batching"] = bool(model_extras_info["batching"])
            model_extras_info["cross_requests_batching"] = bool(
                model_extras_info["cross_requests_batching"]
            )
        except Exception as e:
            raise Exception(f"extra info required for {backbone} is not existed.")

        model_path = os.path.join(model_tmp_dir, f"{model_uuid}")
        try:
            await external_model_store.download_to_file(
                os.path.join(
                    registering_model.blobstore_path, "saved_model/model.onnx"
                ),
                model_path,
            )
        except Exception as e:
            raise Exception(f"Could not download model.")

        await external_model_store.close()

        base_model_inputs = []
        base_model_outputs = []

        for input in model_extras_info["inputs"]:
            input_name = input["name"]
            input_shape = input["shape"]
            input_dtype = input["dtype"]

            if -1 in input_shape[1:]:
                # need to assign shape
                if model_extras_info["memory_layout"] == "NHWC":
                    input_shape[1] = model_input_size
                    input_shape[2] = model_input_size
                else:
                    input_shape[2] = model_input_size
                    input_shape[3] = model_input_size

            base_model_inputs.append(
                ModelInput(name=input_name, shape=input_shape, dtype=input_dtype)
            )

        for output in model_extras_info["outputs"]:
            base_model_outputs.append(ModelOutput(name=output["name"]))

        base_model_desc = ModelDescription(
            inputs=base_model_inputs,
            outputs=base_model_outputs,
            class_names=desc_data["dataset"]["classnames"],
            preprocessing_name=backbone,
            postprocessing_name=backbone,
            transforming_name=backbone if transform_path != "" else "",
        )

        base_model_profile = []
        if str(model_input_size) in model_extras_info["profile"]:
            profile = model_extras_info["profile"][str(model_input_size)]
        else:
            supported_sizes = [
                int(s) for s in list(model_extras_info["profile"].keys())
            ]
            size = max(supported_sizes)
            if size < model_input_size:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Could not find profile for input size {model_input_size}.",
                )
            profile = model_extras_info["profile"][str(size)]

        for p in profile:
            base_model_profile.append(ProfileUnit(**p))

        # build model instance
        base_model = NxsBaseModel(
            user_name=registering_model.user_name,
            model_name=registering_model.model_name,
            framework=Framework.ONNX,
            model_desc=base_model_desc,
            profile=base_model_profile,
            use_gpu=model_extras_info["use_gpu"],
            batching=model_extras_info["batching"],
            cross_requests_batching=model_extras_info["cross_requests_batching"],
            is_public=False,
        )

        await _register_model(
            model_uuid,
            model_path,
            preproc_path,
            postproc_path,
            transform_path,
            base_model,
        )

        pipeline_output_type = PipelineOutputType.CLASSIFICATION
        if registering_model_type == "detector":
            pipeline_output_type = PipelineOutputType.DETECTION

        preproc_params_data = model_extras_info.get("preproc_params", {})
        postproc_params_data = model_extras_info.get("postproc_params", {})
        transform_params_data = model_extras_info.get("transform_params", {})

        preproc_params: List[PipelineExtraParamDescription] = []
        postproc_params: List[PipelineExtraParamDescription] = []
        transform_params: List[PipelineExtraParamDescription] = []

        for _params, data in zip(
            [preproc_params, postproc_params, transform_params],
            [preproc_params_data, postproc_params_data, transform_params_data],
        ):
            for k in data:
                _params.append(PipelineExtraParamDescription(param=k, desc=data[k]))

        pipeline = NxsPipelineRegistrationRequest(
            user_name=registering_model.user_name,
            pipeline_groups=[NxsColocatedModels(colocated_model_uuids=[model_uuid])],
            output_type=pipeline_output_type,
            preproc_params=preproc_params,
            postproc_params=postproc_params,
            transform_params=transform_params,
        )

        return await _register_pipeline(pipeline)
    except Exception as e:
        raise e
    finally:
        delete_dir(model_tmp_dir)


async def _register_model(
    model_uuid: str,
    model_path: str,
    preproc_path,
    postproc_path,
    transform_path,
    model: NxsBaseModel,
):
    # upload data to storage
    storage = get_storage(args)

    storage.upload(model_path, STORAGE_MODEL_PATH, True)
    if preproc_path != "":
        storage.upload(preproc_path, STORAGE_PREPROC_PATH, True)
        model.model_desc.preprocessing_name = model_uuid
    if postproc_path != "":
        storage.upload(postproc_path, STORAGE_POSTPROC_PATH, True)
        model.model_desc.postprocessing_name = model_uuid
    if transform_path != "":
        storage.upload(transform_path, STORAGE_TRANSFORM_PATH, True)
        model.model_desc.transforming_name = model_uuid

    dt_string = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    nxs_model = NxsModel(
        **(model.dict()),
        model_uuid=model_uuid,
        created_timestamp=time.time(),
        created_time=dt_string,
    )
    nxs_model.model_status = ModelStatus.VALID

    db = get_db(args)

    nxs_model_dict = nxs_model.dict()

    if args.db_use_shard_key:
        nxs_model_dict[args.db_shard_key] = args.db_shard_value

    db.insert(MONGODB_MODELS_COLLECTION_NAME, nxs_model_dict)
    db.close()
