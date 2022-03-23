import os
from typing import Dict
import shutil
from nxs_libs.storage import (
    NxsStorage,
    NxsStorageExceptionExistingFile,
    NxsStorageExceptionNonExistingFile,
    NxsStorageExceptionAuthenticationError,
    NxsStorageExceptionInternalError,
    NxsStorageExceptionInvalidParams,
)
from nxs_utils.common import create_dir_if_needed


class NxsLocalStorage(NxsStorage):
    def __init__(self, local_store_dir_path="./tmp/local") -> None:
        super().__init__()
        self.local_store_dir_path = local_store_dir_path
        create_dir_if_needed(local_store_dir_path)

    def upload(self, source_file_path, dest_dir_path, overwrite=True):
        if not overwrite and os.path.exists(dest_dir_path):
            raise NxsStorageExceptionExistingFile

        real_dest_dir_path = os.path.join(self.local_store_dir_path, dest_dir_path)
        shutil.copy(source_file_path, real_dest_dir_path)

    def download(self, path):
        data = None
        with open(os.path.join(self.local_store_dir_path, path), "rb") as f:
            data = f.read()

        return data

    def download_to_file(self, path, dst_path):
        shutil.copy(path, dst_path)

    def delete(self, path):
        real_dest_dir_path = os.path.join(self.local_store_dir_path, path)
        if os.path.exists(real_dest_dir_path) and os.path.isfile(real_dest_dir_path):
            os.remove(real_dest_dir_path)

    def list_files(self, dir_path):
        real_dir_path = os.path.join(self.local_store_dir_path, dir_path)
        if not os.path.exists(real_dir_path) and os.path.isdir(real_dir_path):
            return []

        return os.listdir(real_dir_path)

    def generate_direct_url(self, path):
        return ""

    def close(self):
        pass
