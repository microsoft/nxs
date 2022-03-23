import time
import numpy as np
from typing import Dict, List, Tuple
from configs import GLOBAL_QUEUE_NAMES
from nxs_libs.queue import (
    NxsQueuePusherFactory,
    NxsQueueType,
)
from nxs_types.nxs_args import NxsWorkloadManagerArgs
from nxs_libs.interface.workload_manager import NxsWorkloadManager
from nxs_libs.interface.workload_manager.simple_policy import (
    NxsSimpleWorkloadManagerPolicy,
)
from nxs_utils.nxs_helper import *

from abc import ABC, abstractmethod

if __name__ == "__main__":
    from args import parse_args

    args = parse_args()

    queue_puller = create_queue_puller_from_args(
        args, NxsQueueType.REDIS, GLOBAL_QUEUE_NAMES.WORKLOAD_MANAGER
    )

    queue_pusher = create_queue_pusher_from_args(args, NxsQueueType.REDIS)

    policy = NxsSimpleWorkloadManagerPolicy(args)

    workload_manager = NxsWorkloadManager(args, queue_puller, queue_pusher, policy)
    workload_manager.run()
