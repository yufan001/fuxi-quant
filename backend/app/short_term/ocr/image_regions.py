from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageRegion:
    x: int
    y: int
    width: int
    height: int


def crop_region(image_path: str | Path, output_path: str | Path, region: ImageRegion) -> Path:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for OCR image cropping") from exc
    source = Path(image_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        cropped = image.crop((region.x, region.y, region.x + region.width, region.y + region.height))
        cropped.save(output)
    return output
