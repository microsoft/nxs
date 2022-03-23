import os
from typing import Dict
from nxs_libs.storage import (
    NxsStorage,
    NxsStorageExceptionExistingFile,
    NxsStorageExceptionNonExistingFile,
    NxsStorageExceptionAuthenticationError,
    NxsStorageExceptionInternalError,
    NxsStorageExceptionInvalidParams,
)

from azure.core import exceptions as AzureCoreException
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import StorageErrorCode
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

# TODO: Find a good way to catch authentication error


class NxsAzureBlobStorage(NxsStorage):
    def __init__(self, blob_service_client, container_name: str) -> None:
        super().__init__()

        self._blob_service_client = blob_service_client
        self._container_name = container_name

    def upload(self, source_file_path, dest_dir_path, overwrite=True):
        if not os.path.exists(source_file_path):
            raise NxsStorageExceptionNonExistingFile

        dest_path = os.path.join(dest_dir_path, os.path.basename(source_file_path))
        try:
            blob_client = self._get_blob_client(dest_path)
            with open(source_file_path, "rb") as f:
                blob_client.upload_blob(f, overwrite=overwrite)
        except AzureCoreException.ResourceExistsError:
            raise NxsStorageExceptionExistingFile(
                "File is already existed in blobstore."
            )
        except Exception as e:
            raise NxsStorageExceptionInternalError(
                "NxsAsyncAzureBlobStorage internal error: {}".format(str(e))
            )

    def download(self, path):
        try:
            blob_client = self._get_blob_client(path)
            data = blob_client.download_blob().readall()
            return data
        except AzureCoreException.ResourceNotFoundError:
            raise NxsStorageExceptionNonExistingFile("File not found in blobstore.")
        except AzureCoreException.HttpResponseError as e:
            if "not authorized" in str(e):
                raise NxsStorageExceptionAuthenticationError(
                    "Unauthorized access to blobstore."
                )
            else:
                raise NxsStorageExceptionInternalError(
                    "NxsAsyncAzureBlobStorage internal error: {}".format(str(e))
                )
        except Exception as e:
            raise NxsStorageExceptionInternalError(
                "NxsAsyncAzureBlobStorage internal error: {}".format(str(e))
            )

    def download_to_file(self, path, dst_path):
        try:
            blob_client = self._get_blob_client(path)
            stream = blob_client.download_blob()
            with open(dst_path, "wb") as f:
                for chunk in stream.chunks():
                    f.write(chunk)
        except AzureCoreException.ResourceNotFoundError:
            raise NxsStorageExceptionNonExistingFile("File not found in blobstore.")
        except AzureCoreException.HttpResponseError as e:
            if "not authorized" in str(e):
                raise NxsStorageExceptionAuthenticationError(
                    "Unauthorized access to blobstore."
                )
            else:
                raise NxsStorageExceptionInternalError(
                    "NxsAsyncAzureBlobStorage internal error: {}".format(str(e))
                )
        except Exception as e:
            raise NxsStorageExceptionInternalError(
                "NxsAsyncAzureBlobStorage internal error: {}".format(str(e))
            )

    def delete(self, path):
        try:
            blob_client = self._get_blob_client(path)
            blob_client.delete_blob()
        except AzureCoreException.ResourceNotFoundError:
            raise NxsStorageExceptionNonExistingFile
        except Exception as e:
            raise NxsStorageExceptionInternalError(
                "NxsAsyncAzureBlobStorage internal error: {}".format(str(e))
            )

    def list_files(self, dir_path):
        if not dir_path == "" and not dir_path.endswith("/"):
            dir_path += "/"

        container_client = self._blob_service_client.get_container_client(
            self._container_name
        )
        blob_iter = container_client.list_blobs(name_starts_with=dir_path)
        files = []
        for blob in blob_iter:
            relative_path = os.path.relpath(blob.name, dir_path)
            files.append(relative_path)
        return files

    def generate_direct_url(self, path):
        pass

    def close(self):
        pass

    def _get_blob_client(self, blob_path: str):
        return self._blob_service_client.get_blob_client(
            container=self._container_name, blob=blob_path
        )

    @classmethod
    def from_connection_str(cls, connection_str: str, container_name: str):
        blob_service_client = BlobServiceClient.from_connection_string(connection_str)
        configs = {
            "blob_service_client": blob_service_client,
            "container_name": container_name,
        }
        return cls(**configs)

    @classmethod
    def from_sas_token(cls, account_name: str, sas_token: str, container_name: str):
        account_url = "https://{}.blob.core.windows.net/".format(account_name)
        blob_service_client = BlobServiceClient(
            account_url=account_url, credential=sas_token
        )
        configs = {
            "blob_service_client": blob_service_client,
            "container_name": container_name,
        }
        return cls(**configs)

    @classmethod
    def create(cls, **kwargs):
        if "connection_str" in kwargs and "container_name" in kwargs:
            return NxsAzureBlobStorage.from_connection_str(**kwargs)
        elif (
            "account_name" in kwargs
            and "sas_token" in kwargs
            and "container_name" in kwargs
        ):
            return NxsAzureBlobStorage.from_sas_token(**kwargs)

        raise NxsStorageExceptionInvalidParams
