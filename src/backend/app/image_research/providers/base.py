from abc import ABC, abstractmethod

from app.image_research.schemas import ImageCandidate


class BaseImageProvider(ABC):
    @abstractmethod
    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        raise NotImplementedError
