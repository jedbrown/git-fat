from abc import ABC, abstractmethod
from typing import List
import os


class SyncBackend(ABC):
    @abstractmethod
    def upload(self, local_filename: str, remote_filename=None) -> None:
        pass

    @abstractmethod
    def list(self) -> List[str]:
        pass

    @abstractmethod
    def download(self, remote_filename: str, local_filename: os.PathLike) -> None:
        pass

    @abstractmethod
    def delete(self, filename: str) -> None:
        pass
