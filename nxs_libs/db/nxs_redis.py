import pickle
from nxs_libs.db import *
from nxs_utils.nxs_helper import init_redis_client


class NxsSimpleRedisDB(NxsDb):
    def __init__(
        self, address: str, port: int, password: str, is_using_ssl: bool, **kwargs
    ):
        super().__init__()

        self.address = address
        self.port = port
        self.password = password
        self.is_using_ssl = is_using_ssl

        self.client = init_redis_client(
            self.address, self.port, self.password, self.is_using_ssl
        )

    def query(
        self,
        collection_name: str,
        query: Dict,
        query_config: NxsDbQueryConfig,
        extra_params: Dict = {},
    ) -> List:
        data = self.client.get(collection_name)
        if not isinstance(data, type(None)):
            decoded_data = pickle.loads(data)
            if isinstance(decoded_data, List):
                return decoded_data

            return [decoded_data]

        return []

    def insert(self, collection_name: str, data: Dict, extra_params: Dict = {}) -> None:
        self.client.set(collection_name, pickle.dumps(data))

    def update(
        self,
        collection_name: str,
        query: Dict,
        new_data: Dict,
        insert_if_not_existed: bool = False,
        extra_params: Dict = {},
    ) -> None:
        self.client.set(collection_name, pickle.dumps(new_data))

    def delete(
        self, collection_name: str, query: Dict, extra_params: Dict = {}
    ) -> None:
        self.client.delete(collection_name)

    def close(self) -> None:
        pass
