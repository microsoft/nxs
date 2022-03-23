from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict


class NxsStorageType(str, Enum):
    AzureBlobstorage = "azure_blob_storage"
    AsyncAzureBlobstorage = "async_azure_blob_storage"
    LocalStorage = "local_storage"


class NxsStorageExceptionInvalidParams(Exception):
    pass


class NxsStorageExceptionExistingFile(Exception):
    pass


class NxsStorageExceptionNonExistingFile(Exception):
    pass


class NxsStorageExceptionInternalError(Exception):
    pass


class NxsStorageExceptionAuthenticationError(Exception):
    pass


class NxsStorageExceptionInvalidStorageType(Exception):
    pass


class NxsStorage(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def upload(self, source_file_path, dest_dir_path, overwrite=True):
        raise NotImplementedError

    @abstractmethod
    def download(self, path):
        raise NotImplementedError

    @abstractmethod
    def download_to_file(self, path, dst_path):
        raise NotImplementedError

    @abstractmethod
    def delete(self, path):
        raise NotImplementedError

    @abstractmethod
    def list_files(self, dir_path):
        raise NotImplementedError

    @abstractmethod
    def generate_direct_url(self, path):
        raise NotImplementedError

    @abstractmethod
    def close(self):
        raise NotImplementedError


class NxsStorageFactory:
    @staticmethod
    def create_storage(type: NxsStorageType, **kwargs):
        if type == NxsStorageType.AzureBlobstorage:
            from nxs_libs.storage.nxs_blobstore import NxsAzureBlobStorage

            return NxsAzureBlobStorage.create(**kwargs)
        elif type == NxsStorageType.AsyncAzureBlobstorage:
            from nxs_libs.storage.nxs_blobstore_async import NxsAsyncAzureBlobStorage

            return NxsAsyncAzureBlobStorage.create(**kwargs)
        elif type == NxsStorageType.LocalStorage:
            from nxs_libs.storage.nxs_localstore import NxsLocalStorage

            return NxsLocalStorage(**kwargs)

        raise NxsStorageExceptionInvalidStorageType
