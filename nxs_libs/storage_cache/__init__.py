from abc import ABC, abstractmethod
from enum import Enum
import os
from typing import Dict
from collections import OrderedDict
from nxs_libs.storage import NxsStorage
from nxs_utils.common import generate_uuid, delete_and_create_dir


class NxsBaseStorageCache(ABC):
    def __init__(self, model_store: NxsStorage) -> None:
        super().__init__()
        self.model_store = model_store

    @abstractmethod
    def get_model_path(self, model_uuid: str) -> str:
        raise NotImplementedError


class NxsLocalStorageCache(NxsBaseStorageCache):
    def __init__(self, model_store: NxsStorage, max_cache_size: int = 50) -> None:
        super().__init__(model_store)
        self.max_cache_size = max_cache_size

        # create random directory to store models
        random_uuid = generate_uuid()
        store_name = f"model_store_{random_uuid}"
        self.store_dir_path = os.path.join("./tmp", store_name)
        delete_and_create_dir(self.store_dir_path)

        # create cache
        self.model_cache = OrderedDict()

    def _get_model_path(self, model_uuid):
        return os.path.join(self.store_dir_path, model_uuid)

    def get_model_path(self, model_uuid: str) -> str:
        if model_uuid in self.model_cache:
            self.model_cache.move_to_end(model_uuid)
            return self.model_cache[model_uuid]

        model_path = self._get_model_path(model_uuid)

        # FIXME: how to determine model_path_in_store
        model_path_in_store = f"models/{model_uuid}"
        data = self.model_store.download(model_path_in_store)

        with open(model_path, "wb") as f:
            f.write(data)

        self.model_cache[model_uuid] = model_path
        self.model_cache.move_to_end(model_uuid)

        if len(self.model_cache) > self.max_cache_size:
            least_used_model_uuid, least_used_model_path = self.model_cache.popitem(
                last=False
            )
            if os.path.exists(least_used_model_path):
                os.remove(least_used_model_path)

        return model_path
