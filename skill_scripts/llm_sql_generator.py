import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any
import uuid
from urllib import error, request


JsonDict = dict[str, Any]


def _strip_markdown_fence(text: str) -> str:
    value = str(text or "").strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if len(lines) < 3:
        return value
    if lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return value


def build_llm_prompt(user_prompt: str, context_slice: JsonDict) -> str:
    return (
        "You are a SQL generation engine for Workflow ERP. "
        "Output JSON only with keys: sql, used_tables, assumptions, confidence. "
        "Rules: SQL Server 2000 compatible, single statement, SELECT only, no CTE/window/offset/fetch/except/intersect. "
        f"User prompt: {user_prompt}\n"
        f"Context: {json.dumps(context_slice, ensure_ascii=False)}"
    )


def parse_llm_response(raw_text: str) -> JsonDict:
    payload = json.loads(_strip_markdown_fence(raw_text))
    sql = str(payload.get("sql", "")).strip()
    used_tables = [str(x).strip() for x in payload.get("used_tables", []) if str(x).strip()]
    assumptions = [str(x).strip() for x in payload.get("assumptions", []) if str(x).strip()]

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    if confidence < 0.0:
        confidence = 0.0
    if confidence > 1.0:
        confidence = 1.0

    return {
        "sql": sql,
        "used_tables": used_tables,
        "assumptions": assumptions,
        "confidence": confidence,
    }


def _call_openai_compatible(model: str, prompt_text: str, timeout_sec: float) -> str:
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not base_url or not api_key:
        raise RuntimeError("LLM_PROVIDER_NOT_CONFIGURED")

    endpoint = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": 0,
    }
    req = request.Request(
        endpoint,
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return str(payload["choices"][0]["message"]["content"])
    except error.HTTPError as exc:
        raise RuntimeError(f"LLM_HTTP_ERROR:{exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError("LLM_NETWORK_ERROR") from exc
    except TimeoutError as exc:
        raise RuntimeError("LLM_TIMEOUT") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("LLM_BAD_RESPONSE") from exc


def _call_opencode_local(model: str, prompt_text: str, timeout_sec: float) -> str:
    command = ["opencode", "run", "--format", "json"]
    model_name = str(model or "").strip()
    if model_name and model_name.lower() not in {"none", "default", "auto"}:
        command.extend(["--model", model_name])
    command.append(prompt_text)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("OPENCODE_CLI_NOT_INSTALLED") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("LLM_TIMEOUT") from exc

    if result.returncode != 0:
        raise RuntimeError("LLM_PROVIDER_ERROR")

    last_text = ""
    for line in str(result.stdout or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(event.get("type", "")).strip().lower() != "text":
            continue
        part = event.get("part", {})
        if not isinstance(part, dict):
            continue
        text = str(part.get("text", "")).strip()
        if text:
            last_text = text

    if not last_text:
        raise RuntimeError("LLM_BAD_RESPONSE")
    return last_text


def _call_codex_oauth_local(model: str, prompt_text: str, timeout_sec: float) -> str:
    temp_parent = Path(os.getenv("WFERP_LLM_TEMP_DIR", ".wferp-llm-temp"))
    temp_parent.mkdir(parents=True, exist_ok=True)
    temp_dir_path = temp_parent / f"codex-{uuid.uuid4().hex}"
    temp_dir_path.mkdir(parents=True, exist_ok=False)
    try:
        prompt_path = os.path.join(temp_dir_path, "prompt.txt")
        output_path = os.path.join(temp_dir_path, "last-message.txt")
        with open(prompt_path, "w", encoding="utf-8") as handle:
            handle.write(prompt_text)
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--ignore-rules",
            "--output-last-message",
            output_path,
        ]
        model_name = str(model or "").strip()
        if model_name and model_name.lower() not in {"none", "default", "auto"}:
            command.extend(["--model", model_name])
        command.append(
            "Read the complete prompt from this UTF-8 file and follow it exactly: "
            f"PROMPT_FILE={os.path.abspath(prompt_path)}"
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_sec,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("CODEX_CLI_NOT_INSTALLED") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("LLM_TIMEOUT") from exc

        if result.returncode != 0:
            raise RuntimeError("LLM_PROVIDER_ERROR")

        try:
            last_message = open(output_path, encoding="utf-8").read().strip()
        except OSError as exc:
            raise RuntimeError("LLM_BAD_RESPONSE") from exc

        if not last_message:
            fallback = str(result.stdout or "").strip()
            if fallback:
                return fallback
            raise RuntimeError("LLM_BAD_RESPONSE")
        return last_message
    finally:
        shutil.rmtree(temp_dir_path, ignore_errors=True)


def call_llm(provider: str, model: str, prompt_text: str, timeout_sec: float = 30.0) -> str:
    provider_name = str(provider or "none").strip().lower()

    if provider_name in {"none", "", "disabled"}:
        raise RuntimeError("LLM_PROVIDER_NOT_CONFIGURED")

    if provider_name == "mock":
        return os.getenv(
            "LLM_MOCK_RESPONSE",
            json.dumps(
                {
                    "sql": "SELECT TOP 50 * FROM [DSCSYS].[dbo].[ADMMC]",
                    "used_tables": ["ADMMC"],
                    "assumptions": ["mock provider fallback"],
                    "confidence": 0.4,
                },
                ensure_ascii=False,
            ),
        )

    if provider_name in {"openai-compatible", "openai_compatible", "openai"}:
        return _call_openai_compatible(model=model, prompt_text=prompt_text, timeout_sec=timeout_sec)

    if provider_name in {"opencode", "open-code", "local-opencode", "native"}:
        return _call_opencode_local(model=model, prompt_text=prompt_text, timeout_sec=timeout_sec)

    if provider_name in {"codex", "codex-oauth", "codex_oauth", "local-codex"}:
        return _call_codex_oauth_local(model=model, prompt_text=prompt_text, timeout_sec=timeout_sec)

    raise RuntimeError("LLM_PROVIDER_UNSUPPORTED")
