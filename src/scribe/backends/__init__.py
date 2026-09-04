"""Backend registry.

Backends are looked up by name so the CLI and API never import a specific engine.
Adding one means writing a Backend subclass and adding a line to _REGISTRY.
"""

from __future__ import annotations

from scribe.backends.base import Backend, BackendUnavailable
from scribe.backends.faster_whisper import FasterWhisperBackend
from scribe.backends.mlx_whisper import MLXWhisperBackend

_REGISTRY: dict[str, type[Backend]] = {
    FasterWhisperBackend.name: FasterWhisperBackend,
    MLXWhisperBackend.name: MLXWhisperBackend,
}

DEFAULT_BACKEND = FasterWhisperBackend.name


def available_backends() -> list[str]:
    """Names of backends whose dependencies are installed and hardware is present."""
    return [name for name, cls in _REGISTRY.items() if cls.available()]


def backend_names() -> list[str]:
    """Every registered backend name, installed or not."""
    return list(_REGISTRY)


def get_backend(name: str, model: str = "base", **options) -> Backend:
    """Instantiate a backend by name."""
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"unknown backend {name!r}. Available: {', '.join(_REGISTRY)}"
        ) from None
    return cls(model=model, **options)


__all__ = [
    "Backend",
    "BackendUnavailable",
    "DEFAULT_BACKEND",
    "available_backends",
    "backend_names",
    "get_backend",
]
