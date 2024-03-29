# Database info
MONGODB_DB_NAME = "NXS"
MONGODB_MODELS_COLLECTION_NAME = "Models"
MONGODB_PIPELINES_COLLECTION_NAME = "Pipelines"
MONGODB_W4_MODEL_PROFILES_COLLECTION_NAME = "W4Profiles"
MONGODB_STATS_COLLECTION_NAME = "Stats"

# Storage info
STORAGE_MODEL_PATH = "models"
STORAGE_PREPROC_PATH = "preprocessing"
STORAGE_POSTPROC_PATH = "postprocessing"
STORAGE_TRANSFORM_PATH = "transforming"
STORAGE_PREDEFINED_PREPROC_PATH = "w4preprocessing"
STORAGE_PREDEFINED_POSTPROC_PATH = "w4postprocessing"
STORAGE_PREDEFINED_TRANSFORM_PATH = "w4transforming"
STORAGE_PREDEFINED_EXTRAS_PATH = "w4extras"

# QUEUE INFO
class GLOBAL_QUEUE_NAMES:
    SCHEDULER = "nxs_scheduler"
    SCHEDULER_LOGS = "nxs_scheduler_logs"
    WORKLOAD_MANAGER = "nxs_workload_manager"
    BACKEND_LOGS = "nxs_backend_logs"
    BACKEND_MONITOR_LOGS = "nxs_backend_monitor_logs"


class NXS_CONFIG:
    LOG_LEVEL = "NXS_LOG_LEVEL"


class NXS_BACKEND_CONFIG:
    ORIGINAL_REQUEST = "ORIGINAL_REQUEST"
    USER_METADATA = "USER_METADATA"
    FORWARD_INPUTS = "FORWARD_INPUTS"


class BACKEND_INTERNAL_CONFIG:
    TASK_SKIP_COMPUTE = "task_skip_compute"
    TASK_SKIP_COMPUTE_RESULT = "task_skip_compute_result"
    TASK_STATUS = "task_status"
    TASK_ERROR_MSGS = "task_errror_msgs"
