"""
mcp-image-generator — Executable skill for AI image generation.
Calls OpenAI gpt-image-1 API, decodes base64 response, saves PNG to workspace/downloads/.
"""

import os
import sys
import json
import uuid
import base64
import traceback
from pathlib import Path


def main():
    prompt = os.getenv("SKILL_PARAM_PROMPT", "")
    size = os.getenv("SKILL_PARAM_SIZE", "1024x1024")
    quality = os.getenv("SKILL_PARAM_QUALITY", "medium")

    if not prompt:
        print(json.dumps({
            "status": "error",
            "message": "未提供圖片描述 (prompt)"
        }, ensure_ascii=False))
        return

    # Validate size
    valid_sizes = ["1024x1024", "1536x1024", "1024x1536"]
    if size not in valid_sizes:
        size = "1024x1024"

    # Validate quality
    valid_qualities = ["low", "medium", "high"]
    if quality not in valid_qualities:
        quality = "medium"

    # Resolve output directory (must match server's /images/ route: PROJECT_ROOT/workspace/downloads/)
    try:
        skills_home = os.getenv("SKILLS_HOME", "")
        if skills_home:
            # SKILLS_HOME = PROJECT_ROOT/Agent_skills/system_skills → .parent.parent = PROJECT_ROOT
            project_root = Path(skills_home).resolve().parent.parent
        else:
            # __file__ = .../Agent_skills/system_skills/mcp-image-generator/scripts/main.py
            project_root = Path(__file__).resolve().parents[4]
        downloads_dir = project_root / "workspace" / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        downloads_dir = Path.cwd()

    # Resolve BASE_URL for constructing the image URL
    base_url = os.environ.get("BASE_URL", "http://localhost:8500").rstrip("/")

    # Call OpenAI gpt-image-1
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            print(json.dumps({
                "status": "error",
                "message": "OPENAI_API_KEY 未設定"
            }, ensure_ascii=False))
            return

        client = OpenAI(api_key=api_key)

        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )

        # gpt-image-1 returns base64 data
        image_data = response.data[0]
        b64_json = getattr(image_data, "b64_json", None)
        image_url_remote = getattr(image_data, "url", None)

        filename = f"img_{uuid.uuid4().hex[:12]}.png"
        output_path = downloads_dir / filename

        if b64_json:
            # Decode base64 → save as PNG
            img_bytes = base64.b64decode(b64_json)
            output_path.write_bytes(img_bytes)
        elif image_url_remote:
            # Fallback: download from URL
            import urllib.request
            urllib.request.urlretrieve(image_url_remote, str(output_path))
        else:
            print(json.dumps({
                "status": "error",
                "message": "API 回傳無圖片資料"
            }, ensure_ascii=False))
            return

        local_url = f"{base_url}/images/{filename}"

        # _usage contract — see Agent_skills/README.md. gpt-image-1 bills by
        # image+size+quality, not tokens, so prompt/completion counts are
        # always 0. Attach model + the image metadata so cost attribution
        # downstream can compute price from size/quality if needed.
        print(json.dumps({
            "status": "success",
            "image_url": local_url,
            "filename": filename,
            "file_path": str(output_path),
            "prompt_used": prompt,
            "size": size,
            "quality": quality,
            "message": f"圖片已生成：{filename}",
            "_usage": {
                "model": "gpt-image-1",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "skill_total_tokens": 0,
                "image_count": 1,
                "image_size": size,
                "image_quality": quality,
            },
        }, ensure_ascii=False))

    except Exception as e:
        error_msg = str(e)
        # Even on failure, keep the _usage shape consistent so the admin
        # pipeline's summary loop doesn't need special-case handling for
        # errored image-gen rows.
        _err_usage = {
            "model": "gpt-image-1",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "skill_total_tokens": 0,
            "image_count": 0,
        }
        # Handle content policy violations gracefully
        if "content_policy" in error_msg.lower() or "safety" in error_msg.lower():
            print(json.dumps({
                "status": "error",
                "message": "圖片內容不符合安全政策，請修改描述後重試。",
                "detail": error_msg,
                "_usage": _err_usage,
            }, ensure_ascii=False))
        else:
            print(json.dumps({
                "status": "error",
                "message": f"圖片生成失敗：{error_msg}",
                "detail": traceback.format_exc(),
                "_usage": _err_usage,
            }, ensure_ascii=False))


if __name__ == "__main__":
    main()
