"""VoxMetrica shared library — gallery, seal, capabilities, identify."""

from .paths import get_data_root, load_config
from .gallery import Gallery
from .capabilities import load_capabilities, save_capabilities, check_resource
from .seal import Seal, SealError
from .identify import identify_audio, embed_file
from .control_plane import ControlPlane
from .audit import AuditLog
from .claims import ClaimStore

__all__ = [
    "get_data_root",
    "load_config",
    "Gallery",
    "load_capabilities",
    "save_capabilities",
    "check_resource",
    "Seal",
    "SealError",
    "identify_audio",
    "embed_file",
    "ControlPlane",
    "AuditLog",
    "ClaimStore",
]
