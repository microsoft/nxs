import asyncio
from aiofile import async_open
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
from azure.storage.blob import StorageErrorCode
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob.aio import ContainerClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from nxs_types import message

# TODO: Find a good way to catch authentication error


class NxsAsyncAzureBlobStorage(NxsStorage):
    def __init__(self, blob_service_client, container_name: str) -> None:
        super().__init__()

        self._blob_service_client = blob_service_client
        self._container_name = container_name
        # self._container_client = self._blob_service_client.get_container_client(
        #     container_name
        # )
        self.sem = asyncio.BoundedSemaphore(32)

    def _get_blob_client(self, blob_path: str):
        return self._blob_service_client.get_blob_client(
            container=self._container_name, blob=blob_path
        )

    def upload(self, source_file_path, dest_dir_path, overwrite=True):
        raise NotImplementedError

    async def download(self, path):
        try:
            async with self._blob_service_client.get_container_client(
                self._container_name
            ) as container_client:
                async with self.sem, container_client.get_blob_client(path) as blob:
                    stream = await blob.download_blob()
                    data = await stream.readall()
                    return data
        except AzureCoreException.ResourceNotFoundError as e:
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

    async def download_to_file(self, path, dst_path):
        try:
            async with self._blob_service_client.get_container_client(
                self._container_name
            ) as container_client:
                async with self.sem, container_client.get_blob_client(path) as blob:
                    async with async_open(dst_path, "wb") as f:
                        stream = await blob.download_blob()
                        async for chunk in stream.chunks():
                            await f.write(chunk)

        except AzureCoreException.ResourceNotFoundError as e:
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
        raise NotImplementedError

    def list_files(self, dir_path):
        raise NotImplementedError

    def generate_direct_url(self, path):
        pass

    # async def _close(self):
    #     await self._blob_service_client.close()

    # def close(self):
    #     loop = None
    #     try:
    #         loop = asyncio.get_running_loop()
    #     except RuntimeError:  # 'RuntimeError: There is no current event loop...'
    #         loop = None

    #     if loop and loop.is_running():
    #         # Async event loop already running. Adding coroutine to the event loop.
    #         tsk = loop.create_task(self._close())
    #     else:
    #         # Starting new event loop
    #         asyncio.run(self._close())

    async def close(self):
        await self._blob_service_client.close()

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
