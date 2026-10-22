"""Torch device choice: CUDA when available, else CPU (slow, but runs without an NVIDIA GPU)."""
from __future__ import annotations

import torch


def device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def half_dtype() -> torch.dtype:
    """float16 on CUDA; float32 on CPU, where many half-precision kernels are missing or slow."""
    return torch.float16 if device() == "cuda" else torch.float32
