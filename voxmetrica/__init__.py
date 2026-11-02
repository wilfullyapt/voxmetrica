"""VoxMetrica shared library — gallery, seal, capabilities, identify."""

from .audit import AuditLog
from .capabilities import check_resource, load_capabilities, save_capabilities
from .claims import ClaimStore, build_claim_v1
from .control_plane import ControlPlane
from .enroll_flow import self_enroll, slugify_speaker_id
from .gallery import Gallery
from .identify import embed_file, identify_audio, identify_embedding
from .paths import ensure_layout, get_data_root, load_config, package_root
from .score import cosine, decide_outcome, rank_scores
from .seal import Seal, SealError

__version__ = "0.2.0"

__all__ = [
    "get_data_root",
    "load_config",
    "ensure_layout",
    "package_root",
    "Gallery",
    "load_capabilities",
    "save_capabilities",
    "check_resource",
    "Seal",
    "SealError",
    "identify_audio",
    "identify_embedding",
    "embed_file",
    "ControlPlane",
    "AuditLog",
    "ClaimStore",
    "build_claim_v1",
    "decide_outcome",
    "rank_scores",
    "cosine",
    "self_enroll",
    "slugify_speaker_id",
    "__version__",
]
