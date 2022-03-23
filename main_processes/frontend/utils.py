import requests
import fastapi
import aiohttp
from aiofile import async_open
from nxs_libs.db import NxsDb
from nxs_libs.storage import NxsStorage
from nxs_types.nxs_args import NxsApiArgs
from nxs_utils.nxs_helper import (
    create_db_from_args,
    create_storage_from_args,
)


def get_db(args: NxsApiArgs) -> NxsDb:
    return create_db_from_args(args, args.db_type)


def get_storage(args: NxsApiArgs) -> NxsStorage:
    return create_storage_from_args(args, args.storage_type)


async def async_download_to_memory(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 200
                data = await resp.read()
                return data
    except:
        raise Exception(f"Could not download from {url}")


async def async_download_to_file(url: str, output_path: str, chunk_size: int = 131072):
    try:
        async with async_open(output_path, "wb") as f:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=None) as r:
                    while True:
                        chunk = await r.content.read(chunk_size)
                        if not chunk:
                            break
                        await f.write(chunk)
    except Exception as e:
        raise Exception(f"Could not download from {url}.")


def download_to_memory(url: str):
    try:
        r = requests.get(url, allow_redirects=True)
        assert r.status_code == 200
        return r.content
    except:
        raise fastapi.HTTPException(
            fastapi.status.HTTP_400_BAD_REQUEST, f"Could not download from {url}"
        )


def download_from_direct_link(url: str, output_path: str):
    try:
        data = download_to_memory(url)
        open(output_path, "wb").write(data)
    except:
        raise fastapi.HTTPException(
            fastapi.status.HTTP_400_BAD_REQUEST, f"Could not download from {url}"
        )
