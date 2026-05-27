from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.schemas.presentation import Presentation

class BaseExporter(ABC):
    """
    Abstract base class for exporters.
    Native exporters should consume LayoutedPresentationDocument + ThemeDefinition.
    Legacy screenshot exporters may accept their historical input for fallback use.
    """
    
    @abstractmethod
    def export_pptx(self, presentation: Any, theme: Any, asset_id: str) -> str:
        """Export to PowerPoint (.pptx). Returns the filename."""
        pass

    @abstractmethod
    def export_pdf(self, presentation: Any, theme: Any, asset_id: str) -> str:
        """Export to PDF (.pdf). Returns the filename."""
        pass
