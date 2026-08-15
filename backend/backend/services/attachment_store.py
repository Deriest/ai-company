"""Attachment binary storage.

Attachments arrive from the renderer as base64 data URLs (``data:image/png;base64,...``)
in the chat request payload. The attachment METADATA (file_name, mime_type, ...) lives in
the ``attachments`` table; the BINARY is persisted as a single file at
``DATA_DIR/attachments/<attachment_id>`` so it survives full backups — backup.py zips the
entire DATA_DIR, and ``attachments/`` is not on the exclude list.

NOTE: only attachments created after this storage layer was introduced have a binary on
disk. Pre-existing attachment rows have no file (the source binaries were never retained),
so ``read_attachment`` returns ``None`` for them and the serve endpoint 404s.
"""
import base64
import logging
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)

# Attachment ids are uuid4 hex strings (see generate_uuid in backend.models.conversation).
# Reject anything that could escape the attachments dir (path traversal) — defense in
# depth on top of the middleware path-parameter checks.
_ALLOWED_ID_CHARS = set("0123456789abcdefABCDEF-")


def _validate_attachment_id(attachment_id: str) -> None:
    if not attachment_id or not isinstance(attachment_id, str):
        raise ValueError("attachment_id must be a non-empty string")
    if any(c not in _ALLOWED_ID_CHARS for c in attachment_id):
        raise ValueError(f"invalid attachment_id: {attachment_id!r}")
    if ".." in attachment_id:
        raise ValueError(f"invalid attachment_id: {attachment_id!r}")


def attachment_path(attachment_id: str) -> Path:
    """Return the on-disk path for an attachment's binary (no I/O performed)."""
    _validate_attachment_id(attachment_id)
    return Path(settings.DATA_DIR) / "attachments" / attachment_id


def save_attachment(attachment_id: str, data: bytes) -> Path:
    """Persist ``data`` to ``DATA_DIR/attachments/<attachment_id>`` (mkdir -p)."""
    path = attachment_path(attachment_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def read_attachment(attachment_id: str) -> bytes | None:
    """Read the attachment binary if present, else ``None``."""
    path = attachment_path(attachment_id)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as e:
        logger.warning(f"Could not read attachment {attachment_id}: {e}")
        return None


def delete_attachment(attachment_id: str) -> None:
    """Remove the attachment file if present (no-op when missing)."""
    path = attachment_path(attachment_id)
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        logger.warning(f"Could not delete attachment file {path}: {e}")


def decode_data_url(data_url: str) -> bytes | None:
    """Decode a ``data:<mime>;base64,<payload>`` URL into raw bytes.

    Returns ``None`` when the value is empty / not a data URL / not valid base64
    so callers can skip persisting gracefully instead of crashing the request.
    """
    if not data_url or "," not in data_url:
        return None
    try:
        return base64.b64decode(data_url.split(",", 1)[1], validate=False)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid base64 data_url (len={len(data_url)}): {e}")
        return None


def derive_file_type(mime_type: str = "", file_name: str = "") -> str:
    """Map a mime_type/file_name to the coarse file_type bucket used by the
    ``attachments`` table (images, pdf, markdown, json, text, code, binary)."""
    mime = (mime_type or "").lower()
    name = (file_name or "").lower()
    if mime.startswith("image/"):
        return "images"
    if mime == "application/pdf" or name.endswith(".pdf"):
        return "pdf"
    if mime == "text/markdown" or name.endswith(".md"):
        return "markdown"
    if mime == "application/json" or name.endswith((".json", ".jsonl")):
        return "json"
    # Known code extensions take precedence over the generic text/ bucket so a
    # .py/.ts file with mime "text/x-python" is reported as code, not text.
    if name.endswith((
        ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs",
        ".c", ".cpp", ".h", ".css", ".html", ".sh", ".yaml", ".yml",
    )):
        return "code"
    if mime.startswith("text/") or name.endswith((".txt", ".csv")):
        return "text"
    return "binary"
