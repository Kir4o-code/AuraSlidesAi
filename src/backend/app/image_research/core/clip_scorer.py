# Роля на модула: Моделният scoring слой, който сравнява изображението със смисъла на prompt-а.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from pathlib import Path
from typing import Any

from PIL import Image


class ClipScorer:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32") -> None:
        # Роля в pipeline-а: обработва стъпката `init` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `model_name` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        self.model_name = model_name
        self.device = "cpu"
        self.model: Any = None
        self.processor: Any = None
        self._torch: Any = None

    def _load(self) -> None:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `load` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `CLIPModel.from_pretrained(self.model_name).to`, `CLIPProcessor.from_pretrained`, `self.model.eval`, `torch.cuda.is_available`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        # Това условие е decision point: `self.model and self.processor`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`None`) и прескачаме ненужната останала работа.
        if self.model and self.processor:
            return
        import torch
        import transformers.utils.import_utils as import_utils

        self._torch = torch
        # `self.device` пази резултата от `torch.cuda.is_available`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        import_utils._torchvision_available = False
        from transformers import CLIPModel, CLIPProcessor

        # `self.model` пази резултата от `CLIPModel.from_pretrained(self.model_name).to`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        self.model = CLIPModel.from_pretrained(self.model_name).to(self.device)
        # `self.processor` пази резултата от `CLIPProcessor.from_pretrained`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        self.processor = CLIPProcessor.from_pretrained(self.model_name)
        self.model.eval()

    def score_images(self, image_paths: list[str], text_prompt: str) -> list[float]:
        # Роля в pipeline-а: превръща качествени сигнали в числова оценка, за да могат кандидатите да се подредят.
        # Входът идва през `self` (неуточнен тип), `image_paths` (list[str]), `text_prompt` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self.score_images_against_texts`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `list[float]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        return self.score_images_against_texts(image_paths, [text_prompt])

    def score_images_against_texts(self, image_paths: list[str], text_prompts: list[str]) -> list[float]:
        # Роля в pipeline-а: превръща качествени сигнали в числова оценка, за да могат кандидатите да се подредят.
        # Входът идва през `self` (неуточнен тип), `image_paths` (list[str]), `text_prompts` (list[str]); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self._load`, `self.processor(text=prompts, images=images, return_tensors='pt', padding=True).to`, `Image.open(Path(path)).convert`, `self._torch.no_grad`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `list[float]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        # Това условие е decision point: `not image_paths`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[]`) и прескачаме ненужната останала работа.
        if not image_paths:
            return []
        # `prompts` пази резултата от `prompt.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
        prompts = [prompt for prompt in text_prompts if prompt.strip()]
        # Това условие е decision point: `not prompts`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[0.0 for _ in image_paths]`) и прескачаме ненужната останала работа.
        if not prompts:
            return [0.0 for _ in image_paths]
        self._load()
        assert self.model and self.processor
        # `images` пази резултата от `Image.open(Path(path)).convert`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
        images = [Image.open(Path(path)).convert("RGB") for path in image_paths]
        # `inputs` пази резултата от `self.processor(text=prompts, images=images, return_tensors='pt', padding=True).to`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        inputs = self.processor(
            text=prompts,
            images=images,
            return_tensors="pt",
            padding=True,
        ).to(self.device)
        assert self._torch is not None
        with self._torch.no_grad():
            # `image_features` пази резултата от `self.model.get_image_features`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            image_features = self.model.get_image_features(pixel_values=inputs["pixel_values"])
            # `text_features` пази резултата от `self.model.get_text_features`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            text_features = self.model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
            )
            # `image_features` пази резултата от `image_features.norm`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            # `text_features` пази резултата от `text_features.norm`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            # `scores` пази резултата от `(image_features @ text_features.T).max`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            scores = (image_features @ text_features.T).max(dim=1).values
        # Обхождаме `images` като `img`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for img in images:
            img.close()
        return [float(score) for score in scores.detach().cpu().tolist()]
