import pymongo
import copy
from typing import Dict, List, Tuple
from nxs_libs.db import *


class NxsMongoDb(NxsDb):
    def __init__(self, uri: str, db_name: str, **kwargs):
        super().__init__()

        self._uri = uri
        self._db_name = db_name

        self._client = pymongo.MongoClient(
            self._uri, serverSelectionTimeoutMS=30000, waitQueueTimeoutMS=100
        )
        self._db = self._client[self._db_name]

    def query(
        self,
        collection_name: str,
        query: Dict,
        query_config: NxsDbQueryConfig = NxsDbQueryConfig(),
        extra_params: Dict = {},
    ) -> List:
        collection = self._db[collection_name]

        fields = None
        if query_config.projection_list:
            fields = {"_id": 0}
            for field_name in query_config.projection_list:
                fields[field_name] = 1

        responses_cursor = collection.find(query, fields)

        if query_config.sort_list:
            mongodb_sort_list = []
            for sort_tuple in query_config.sort_list:
                name, sort_type = sort_tuple
                sort_type = (
                    pymongo.ASCENDING
                    if sort_type == NxsDbSortType.ASCENDING
                    else pymongo.DESCENDING
                )
                mongodb_sort_list.append((name, sort_type))
            responses_cursor = responses_cursor.sort(mongodb_sort_list)

        if query_config.skip > 0:
            responses_cursor = responses_cursor.skip(query_config.skip)

        if query_config.limit is not None and query_config.limit > 0:
            responses_cursor = responses_cursor.limit(query_config.limit)

        results = []
        for r in responses_cursor:
            results.append(r)

        return results

    def insert(self, collection_name: str, data: Dict, extra_params: Dict = {}) -> None:
        data = copy.deepcopy(data)

        collection = self._db[collection_name]
        try:
            collection.insert_one(data)
        except Exception as e:
            if "document does not contain shard key" in str(e):
                raise NxsDbExceptionMissingShardKey

    def update(
        self,
        collection_name: str,
        query: Dict,
        new_data: Dict,
        insert_if_not_existed: bool = False,
        extra_params: Dict = {},
    ) -> None:
        collection = self._db[collection_name]
        try:
            collection.update_many(
                query, {"$set": new_data}, upsert=insert_if_not_existed
            )
        except Exception as e:
            if "document does not contain shard key" in str(e):
                raise NxsDbExceptionMissingShardKey

    def delete(
        self, collection_name: str, query: Dict, extra_params: Dict = {}
    ) -> None:
        collection = self._db[collection_name]
        collection.delete_many(query)

    def close(self) -> None:
        try:
            self._client.close()
        except:
            pass
