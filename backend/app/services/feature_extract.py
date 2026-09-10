"""DINOv2 feature extraction for image similarity clustering.

Uses Meta's DINOv2 ViT-S/14 model — smallest variant, best for CPU inference.
Loads from local cache; does NOT require network access.
"""

from __future__ import annotations

import logging
import os
import sys
import torch
import torchvision.transforms as T
from PIL import Image
from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_transform = None
_device = None
_load_attempted = False


def _load_model():
    global _model, _transform, _device, _load_attempted
    if _load_attempted:
        return
    _load_attempted = True

    _device = torch.device("cpu")
    logger.info("Loading DINOv2 ViT-S/14 from local cache...")

    hub_dir = torch.hub.get_dir()
    repo_dir = os.path.join(hub_dir, "facebookresearch_dinov2_main")
    ckpt_path = os.path.join(hub_dir, "checkpoints", "dinov2_vits14_pretrain.pth")

    if not os.path.isdir(repo_dir):
        raise FileNotFoundError(
            f"DINOv2 repo not found at {repo_dir}. Run once with network to download."
        )
    if not os.path.isfile(ckpt_path):
        raise FileNotFoundError(
            f"DINOv2 checkpoint not found at {ckpt_path}. Run once with network to download."
        )

    # Add repo to sys.path so dinov2 module can be imported
    if repo_dir not in sys.path:
        sys.path.insert(0, repo_dir)

    # Build model from the cached dinov2 source
    from dinov2.models.vision_transformer import vit_small

    model = vit_small(
        patch_size=14,
        img_size=518,
        init_values=1.0,
        block_chunks=0,
    )
    state_dict = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.to(_device)
    model.eval()

    _model = model
    _transform = T.Compose([
        T.Resize((518, 518), interpolation=T.InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    logger.info("DINOv2 model loaded from cache.")


def extract_features(image_path: str) -> list[float]:
    _load_model()

    if _model is None:
        raise RuntimeError("DINOv2 model not loaded")

    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    max_dim = settings.max_image_dimension
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)

    tensor = _transform(img).unsqueeze(0).to(_device)

    with torch.no_grad():
        features = _model(tensor)

    return features.squeeze(0).cpu().tolist()


def unload_model():
    global _model, _transform, _device, _load_attempted
    _model = None
    _transform = None
    _device = None
    _load_attempted = False
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
