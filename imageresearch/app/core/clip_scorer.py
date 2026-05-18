from pathlib import Path
from typing import Any

import torch
from PIL import Image


class ClipScorer:
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: Any = None
        self.processor: Any = None

    def _load(self) -> None:
        if self.model and self.processor:
            return
        import transformers.utils.import_utils as import_utils

        import_utils._torchvision_available = False
        from transformers import CLIPModel, CLIPProcessor

        self.model = CLIPModel.from_pretrained(self.model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(self.model_name)
        self.model.eval()

    def score_images(self, image_paths: list[str], text_prompt: str) -> list[float]:
        return self.score_images_against_texts(image_paths, [text_prompt])

    def score_images_against_texts(self, image_paths: list[str], text_prompts: list[str]) -> list[float]:
        if not image_paths:
            return []
        prompts = [prompt for prompt in text_prompts if prompt.strip()]
        if not prompts:
            return [0.0 for _ in image_paths]
        self._load()
        assert self.model and self.processor
        images = [Image.open(Path(path)).convert("RGB") for path in image_paths]
        inputs = self.processor(
            text=prompts,
            images=images,
            return_tensors="pt",
            padding=True,
        ).to(self.device)
        with torch.no_grad():
            image_features = self.model.get_image_features(pixel_values=inputs["pixel_values"])
            text_features = self.model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
            )
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            scores = (image_features @ text_features.T).max(dim=1).values
        for img in images:
            img.close()
        return [float(score) for score in scores.detach().cpu().tolist()]
