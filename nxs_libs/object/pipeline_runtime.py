import time
from typing import List
from nxs_libs.db import NxsDb
from nxs_libs.simple_key_value_db import NxsSimpleKeyValueDb
from nxs_types.model import (
    NxsPipelineInfo,
    NxsPipelineRuntimeInfo,
    NxsPipeline,
    NxsModel,
    ModelType,
    NxsCompositoryModel,
)
from configs import *


class NxsPipelineRuntime:
    def __init__(self, rt_pipeline: NxsPipelineRuntimeInfo) -> None:
        self.pipeline = rt_pipeline

    def get_pipeline_info(self):
        # return a clone
        return NxsPipelineInfo(**(self.pipeline.dict()))

    def get_runtime_info(self):
        # return a clone
        return NxsPipelineRuntimeInfo(**(self.pipeline.dict()))

    @staticmethod
    def get_topic_name(pipeline_uuid):
        return "pipeline_" + pipeline_uuid

    @staticmethod
    def get_ts_topic_name(pipeline_uuid):
        return NxsPipelineRuntime.get_topic_name(pipeline_uuid) + "_ts"

    @classmethod
    def get_from_state_db(cls, pipeline_uuid: str, db: NxsSimpleKeyValueDb):
        pipeline: NxsPipelineRuntimeInfo = db.get_value(
            NxsPipelineRuntime.get_topic_name(pipeline_uuid)
        )

        if pipeline:
            last_alive_ts = db.get_value(
                NxsPipelineRuntime.get_ts_topic_name(pipeline_uuid)
            )
            if last_alive_ts:
                pipeline.last_alive_ts = last_alive_ts

            return cls(pipeline)

        return None

    @classmethod
    def get_from_db(cls, pipeline_uuid: str, db: NxsDb):
        query_results = db.query(
            MONGODB_PIPELINES_COLLECTION_NAME, {"pipeline_uuid": pipeline_uuid}
        )

        if not query_results:
            return None

        pipeline = NxsPipeline(**(query_results[0]))

        models = []
        for model_uuid in pipeline.pipeline:
            model_info = db.query(
                MONGODB_MODELS_COLLECTION_NAME, {"model_uuid": model_uuid}
            )[0]
            main_model = NxsModel(**model_info)
            component_models = []

            if main_model.model_type == ModelType.COMPOSITE:
                component_models.append(main_model)

                for collocated_model_uuid in main_model.collocated_model_uuids:
                    model_info = db.query(
                        MONGODB_MODELS_COLLECTION_NAME,
                        {"model_uuid": collocated_model_uuid},
                    )[0]
                    model = NxsModel(**model_info)
                    component_models.append(model)
            else:
                component_models.append(main_model)

            models.append(
                NxsCompositoryModel(
                    main_model=main_model, component_models=component_models
                )
            )

        rt_pipeline = NxsPipelineRuntimeInfo(
            **(pipeline.dict()), models=models, last_alive_ts=time.time()
        )

        return cls(rt_pipeline)
