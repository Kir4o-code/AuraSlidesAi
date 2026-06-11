# Роля на модула: Общият export договор за PPTX и PDF.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from abc import ABC, abstractmethod
from typing import Any


class BaseExporter(ABC):
    # Роля на класа: Този абстрактен клас задава договор за сменяеми реализации; orchestration кодът работи с интерфейса, а не с конкретния provider.
    # Абстрактните методи принуждават всяка реализация да предложи еднакъв публичен вход и изход.
    """
    Abstract base class for exporters.
    Native exporters should consume LayoutedPresentationDocument + ThemeDefinition.
    Legacy screenshot exporters may accept their historical input for fallback use.
    """

    @abstractmethod
    def export_pptx(self, presentation: Any, theme: Any, asset_id: str) -> str:
        # Роля в pipeline-а: превръща готовия layout в краен файл за клиента.
        # Входът идва през `self` (неуточнен тип), `presentation` (Any), `theme` (Any), `asset_id` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `str`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        """Export to PowerPoint (.pptx). Returns the filename."""
        raise NotImplementedError

    @abstractmethod
    def export_pdf(self, presentation: Any, theme: Any, asset_id: str) -> str:
        # Роля в pipeline-а: превръща готовия layout в краен файл за клиента.
        # Входът идва през `self` (неуточнен тип), `presentation` (Any), `theme` (Any), `asset_id` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `str`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        """Export to PDF (.pdf). Returns the filename."""
        raise NotImplementedError
