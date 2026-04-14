import os
import sys
import json
import traceback

def main():
    # The UMA ExecutionEngine injects parameters as SKILL_PARAM_NAME
    code = os.getenv("SKILL_PARAM_CODE", "")

    if not code:
        print(json.dumps({"status": "error", "message": "No code provided"}, ensure_ascii=False))
        return

    # Safety net: set CWD to workspace/downloads so that any file output
    # with a relative path (e.g. pdf.output('report.pdf')) lands in the
    # directory served by the /downloads/ endpoint.
    # This prevents 404 errors when LLM-generated code forgets the full path.
    try:
        from pathlib import Path
        # Navigate from skills home → project root → workspace/downloads
        # SKILLS_HOME = PROJECT_ROOT/Agent_skills/system_skills → .parent.parent = PROJECT_ROOT
        skills_home = os.getenv("SKILLS_HOME", "")
        if skills_home:
            downloads_dir = Path(skills_home).resolve().parent.parent / "workspace" / "downloads"
        else:
            downloads_dir = Path(__file__).resolve().parents[4] / "workspace" / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(str(downloads_dir))
    except Exception:
        pass  # Non-fatal: if CWD change fails, code may still use absolute paths

    try:
        # Capture stdout
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            exec(code)
        
        output = f.getvalue()
        
        print(json.dumps({
            "status": "success",
            "output": output.strip(),
            "message": "Code executed successfully"
        }, ensure_ascii=False))

    except Exception:
        error_msg = traceback.format_exc()
        print(json.dumps({
            "status": "failed",
            "error": error_msg
        }, ensure_ascii=False))

if __name__ == "__main__":
    main()
