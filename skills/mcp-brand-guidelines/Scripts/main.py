import os
import sys
import json
from pathlib import Path

def main():
    """
    Brand Guidelines Tool: Returns the R&D CIS color and design standard.
    When called, it reads and returns the full CIS standard reference.
    """
    skill_dir = Path(os.getenv("CURRENT_SKILL_DIR", "."))
    cis_ref_path = skill_dir / "References" / "cis_standard.md"

    if cis_ref_path.exists():
        with open(cis_ref_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(json.dumps({
            "status": "success",
            "guideline_source": "R&D CIS Standard v1.0",
            "content": content
        }, ensure_ascii=False))
    else:
        # Fallback: return the core color values directly
        print(json.dumps({
            "status": "success",
            "guideline_source": "R&D CIS Standard (inline fallback)",
            "content": (
                "# 研發組 CIS Design Standard\n\n"
                "## Core Brand Colors\n"
                "- **Brand Blue**: #003366 (Hover: #002244) - Headers, Nav, Primary elements\n"
                "- **Brand Orange**: #FF6600 (Hover: #E65C00) - CTA Buttons, Alerts, Key actions\n\n"
                "## Background Colors\n"
                "- Primary BG: #FFFFFF\n"
                "- Section BG: #F9FAFB\n"
                "- Border: #E5E7EB\n\n"
                "## Typography\n"
                "- Font: 'Inter', 'PingFang TC', -apple-system, sans-serif\n"
                "- Main Text: #111827\n"
                "- Sub Text: #4B5563\n"
            )
        }, ensure_ascii=False))

if __name__ == "__main__":
    main()
