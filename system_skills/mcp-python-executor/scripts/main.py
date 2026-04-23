import os
import sys
import json
import traceback


# ── OpenAI usage interceptor ─────────────────────────────────────────────────
# LLM-generated / user-supplied Python code frequently calls the OpenAI SDK
# (for summarization, classification, rewrites, embeddings). Those calls used
# to be invisible to the admin Dashboard because they happen INSIDE the exec()
# sandbox — no way for WorkflowExecutor to see the response.usage.
#
# Fix: patch openai.OpenAI / openai.AsyncOpenAI at the module level BEFORE
# executing user code. The patch wraps chat.completions.create(),
# responses.create(), and embeddings.create(), reads response.usage on each,
# and accumulates into module-level totals. At the end we emit a top-level
# _usage field per the Agent_skills README contract.

_USAGE_TOTAL = {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "call_count": 0,
    "models": set(),  # track which models were used (pricing varies)
}


def _accumulate_usage(usage_obj, model: str = ""):
    """Pull prompt/completion/total from an SDK usage object and add to running total."""
    try:
        if usage_obj is None:
            return
        # Support both new SDK (usage.prompt_tokens) and dict-like responses
        def _g(name):
            return getattr(usage_obj, name, None) or (
                usage_obj.get(name) if isinstance(usage_obj, dict) else 0
            ) or 0
        _USAGE_TOTAL["input_tokens"]  += _g("prompt_tokens") or _g("input_tokens")
        _USAGE_TOTAL["output_tokens"] += _g("completion_tokens") or _g("output_tokens")
        _USAGE_TOTAL["total_tokens"]  += _g("total_tokens")
        _USAGE_TOTAL["call_count"]    += 1
        if model:
            _USAGE_TOTAL["models"].add(model)
    except Exception:
        pass


def _patch_openai_sdk():
    """Install wrappers around openai.OpenAI / AsyncOpenAI.

    Strategy: wrap the class __init__ so every instance gets its
    chat.completions.create / responses.create / embeddings.create methods
    decorated. Preserves all original kwargs and return values — only adds
    a side-effect read of response.usage after the call returns.

    If `openai` isn't installed or the patching fails for any reason we
    silently skip — user code still runs, just without usage tracking.
    """
    try:
        import openai
    except ImportError:
        return

    def _wrap_create(orig_create, endpoint: str):
        def _wrapped(*args, **kwargs):
            model = kwargs.get("model", "")
            result = orig_create(*args, **kwargs)
            # Handle both streaming and non-streaming
            stream = kwargs.get("stream", False)
            if stream:
                # Wrap the iterator so we can peek at usage in the final chunk
                # (OpenAI new API returns usage in last chunk if
                # stream_options={"include_usage": True} is set).
                def _iter():
                    for chunk in result:
                        u = getattr(chunk, "usage", None)
                        if u is not None:
                            _accumulate_usage(u, model)
                        yield chunk
                return _iter()
            else:
                _accumulate_usage(getattr(result, "usage", None), model)
                return result
        return _wrapped

    def _patch_instance(client):
        """Decorate the create methods on an instantiated client."""
        try:
            if hasattr(client, "chat") and hasattr(client.chat, "completions"):
                client.chat.completions.create = _wrap_create(
                    client.chat.completions.create, "chat.completions"
                )
        except Exception:
            pass
        try:
            if hasattr(client, "responses"):
                client.responses.create = _wrap_create(
                    client.responses.create, "responses"
                )
        except Exception:
            pass
        try:
            if hasattr(client, "embeddings"):
                client.embeddings.create = _wrap_create(
                    client.embeddings.create, "embeddings"
                )
        except Exception:
            pass

    # Patch both OpenAI and AsyncOpenAI constructors so any user-code
    # instantiation gets the wrapped methods.
    for cls_name in ("OpenAI", "AsyncOpenAI"):
        try:
            cls = getattr(openai, cls_name, None)
            if cls is None:
                continue
            _orig_init = cls.__init__

            def _new_init(self, *a, __orig=_orig_init, **kw):
                __orig(self, *a, **kw)
                _patch_instance(self)

            cls.__init__ = _new_init
        except Exception:
            pass

    # Legacy openai 0.x compatibility: openai.ChatCompletion.create
    try:
        if hasattr(openai, "ChatCompletion"):
            _orig_cc = openai.ChatCompletion.create
            def _cc_wrapped(*args, **kwargs):
                model = kwargs.get("model", "")
                result = _orig_cc(*args, **kwargs)
                _accumulate_usage(getattr(result, "usage", None) or (result.get("usage") if isinstance(result, dict) else None), model)
                return result
            openai.ChatCompletion.create = _cc_wrapped
    except Exception:
        pass


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

    # Install the OpenAI usage interceptor BEFORE exec'ing user code.
    _patch_openai_sdk()

    def _build_usage_field():
        """Compose the _usage dict emitted alongside the skill result."""
        return {
            "model": ",".join(sorted(_USAGE_TOTAL["models"])) if _USAGE_TOTAL["models"] else "",
            "input_tokens":  _USAGE_TOTAL["input_tokens"],
            "output_tokens": _USAGE_TOTAL["output_tokens"],
            "total_tokens":  _USAGE_TOTAL["total_tokens"],
            "skill_total_tokens": _USAGE_TOTAL["total_tokens"],
            "llm_call_count": _USAGE_TOTAL["call_count"],
        }

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
            "message": "Code executed successfully",
            "_usage": _build_usage_field(),
        }, ensure_ascii=False))

    except Exception:
        error_msg = traceback.format_exc()
        # Preserve any partial LLM usage consumed before the crash so
        # admin analytics doesn't under-report cost on failed runs.
        print(json.dumps({
            "status": "failed",
            "error": error_msg,
            "_usage": _build_usage_field(),
        }, ensure_ascii=False))

if __name__ == "__main__":
    main()
