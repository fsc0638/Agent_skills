"""
transcribe — Executable skill for audio transcription via Gemini API.
Reads JSON from stdin, outputs JSON to stdout.

Input:  {"file_path": "/path/to/audio.mp3"}
Output: {"status": "success", "transcript": "...", "file_path": "...", "message": "..."}
"""

import os
import sys
import json
import base64

# Force UTF-8 I/O on Windows to handle non-ASCII file paths and transcripts
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
import mimetypes
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-2.5-flash"
MODEL = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
INLINE_SIZE_LIMIT = 15 * 1024 * 1024  # 15 MB raw (~20 MB as base64)

MIME_MAP = {
    ".mp3":  "audio/mpeg",
    ".wav":  "audio/wav",
    ".m4a":  "audio/mp4",
    ".aac":  "audio/aac",
    ".flac": "audio/flac",
    ".ogg":  "audio/ogg",
    ".opus": "audio/ogg",
    ".webm": "audio/webm",
}

PROMPT = (
    "Please transcribe this audio accurately. "
    "If there are multiple speakers, distinguish them where possible. "
    "Return only the transcript text, preserving the original language."
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def error(message: str, **kwargs):
    print(json.dumps({"status": "error", "message": message, **kwargs}, ensure_ascii=False))
    sys.exit(0)


def transcribe_inline(client, file_path: Path, mime_type: str) -> str:
    from google.genai import types
    data = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Content(parts=[
                types.Part(inline_data=types.Blob(mime_type=mime_type, data=data)),
                types.Part(text=PROMPT),
            ])
        ],
    )
    return response.text


def transcribe_via_file_api(client, file_path: Path, mime_type: str) -> str:
    from google.genai import types
    import uuid
    # Pass file object (not path string) to avoid ASCII encoding issues with non-ASCII paths on Windows
    ascii_display_name = f"audio_{uuid.uuid4().hex[:12]}{file_path.suffix}"
    with open(file_path, "rb") as f:
        uploaded = client.files.upload(
            file=f,
            config=types.UploadFileConfig(mime_type=mime_type, display_name=ascii_display_name),
        )
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Content(parts=[
                    types.Part(file_data=types.FileData(file_uri=uploaded.uri, mime_type=mime_type)),
                    types.Part(text=PROMPT),
                ])
            ],
        )
        return response.text
    finally:
        # Best-effort cleanup — files auto-expire after 48h anyway
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 1. Read parameters from stdin (executor sets PYTHONIOENCODING=utf-8 + encoding='utf-8')
    try:
        raw = sys.stdin.read()
        args = json.loads(raw) if raw.strip() else {}
    except Exception:
        args = {}

    file_path_str = args.get("file_path", "").strip()
    if not file_path_str:
        error("未提供音訊檔案路徑 (file_path)")

    file_path = Path(file_path_str).resolve()
    if not file_path.exists():
        error(f"找不到檔案：{file_path}")

    # 2. Detect MIME type
    ext = file_path.suffix.lower()
    mime_type = MIME_MAP.get(ext)
    if not mime_type:
        supported = ", ".join(MIME_MAP.keys())
        error(f"不支援的檔案格式：{ext}，支援格式：{supported}")

    # 3. Check API key
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        error("GEMINI_API_KEY 環境變數未設定")

    # 4. Transcribe
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        file_size = file_path.stat().st_size

        if file_size <= INLINE_SIZE_LIMIT:
            transcript = transcribe_inline(client, file_path, mime_type)
        else:
            transcript = transcribe_via_file_api(client, file_path, mime_type)

        if not transcript:
            error("Gemini API 回傳空白逐字稿")

        print(json.dumps({
            "status": "success",
            "transcript": transcript,
            "file_path": str(file_path),
            "message": f"逐字稿已完成（{file_path.name}）",
        }, ensure_ascii=False))

    except ImportError:
        error("缺少 google-genai 套件，請執行：pip install google-genai")
    except Exception as e:
        error(f"逐字稿執行失敗：{str(e)}")


if __name__ == "__main__":
    main()
