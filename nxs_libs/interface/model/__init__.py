from abc import ABC, abstractmethod
from typing import Dict, List

from nxs_types.model import NxsModel


class NxsBaseCustomModel(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def init(self, component_model: NxsModel):
        raise NotImplementedError

    @abstractmethod
    def infer(self, batches, preprocs, postprocs, metadatas):
        raise NotImplementedError

    @abstractmethod
    def cleanup(self):
        raise NotImplementedError
