import json
from types import SimpleNamespace

from skill_scripts.llm_sql_generator import build_llm_prompt, call_llm, parse_llm_response


def test_parse_llm_response_extracts_sql_and_tables():
    payload = '{"sql":"SELECT TOP 10 * FROM [VPIC1].[dbo].[ACTMK]","used_tables":["ACTMK"],"assumptions":["year filter"],"confidence":0.82}'
    out = parse_llm_response(payload)
    assert out["sql"].startswith("SELECT")
    assert out["used_tables"] == ["ACTMK"]
    assert out["assumptions"] == ["year filter"]
    assert 0.0 <= out["confidence"] <= 1.0


def test_build_llm_prompt_contains_user_prompt_and_context():
    prompt = build_llm_prompt("查詢預算明細", {"tables": [{"TableID": "ACTMK"}]})
    assert "查詢預算明細" in prompt
    assert "ACTMK" in prompt


def test_call_llm_mock_provider(monkeypatch):
    mock = {
        "sql": "SELECT TOP 5 * FROM [VPIC1].[dbo].[ACTMK]",
        "used_tables": ["ACTMK"],
        "assumptions": [],
        "confidence": 0.9,
    }
    monkeypatch.setenv("LLM_MOCK_RESPONSE", json.dumps(mock, ensure_ascii=False))
    raw = call_llm(provider="mock", model="unused", prompt_text="anything", timeout_sec=1.0)
    parsed = parse_llm_response(raw)
    assert parsed["sql"].startswith("SELECT TOP 5")


def test_call_llm_none_provider_raises():
    try:
        call_llm(provider="none", model="unused", prompt_text="x")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == "LLM_PROVIDER_NOT_CONFIGURED"


def test_parse_llm_response_accepts_markdown_fence():
    fenced = """```json
{"sql":"SELECT TOP 1 * FROM [VPIC1].[dbo].[ACTMK]","used_tables":["ACTMK"],"assumptions":[],"confidence":0.8}
```"""
    parsed = parse_llm_response(fenced)
    assert parsed["sql"].startswith("SELECT TOP 1")
    assert parsed["used_tables"] == ["ACTMK"]


def test_call_llm_opencode_provider_reads_text_event(monkeypatch):
    stdout = "\n".join(
        [
            json.dumps({"type": "step_start"}),
            json.dumps(
                {
                    "type": "text",
                    "part": {
                        "text": '{"sql":"SELECT TOP 3 * FROM [VPIC1].[dbo].[ACTMK]","used_tables":["ACTMK"],"assumptions":[],"confidence":0.77}'
                    },
                }
            ),
            json.dumps({"type": "step_finish"}),
        ]
    )

    def _fake_run(command, capture_output, text, check, timeout):
        assert command[:3] == ["opencode", "run", "--format"]
        assert command[3] == "json"
        return SimpleNamespace(returncode=0, stdout=stdout)

    monkeypatch.setattr("skill_scripts.llm_sql_generator.subprocess.run", _fake_run)

    raw = call_llm(provider="opencode", model="none", prompt_text="anything", timeout_sec=1.0)
    parsed = parse_llm_response(raw)
    assert parsed["sql"].startswith("SELECT TOP 3")


def test_call_llm_codex_provider_uses_codex_exec_oauth_path(monkeypatch):
    payload = {
        "sql": "SELECT TOP 7 * FROM [VPIC1].[dbo].[ACTMK]",
        "used_tables": ["ACTMK"],
        "assumptions": ["codex oauth provider"],
        "confidence": 0.88,
    }

    def _fake_run(command, capture_output, text, check, timeout):
        assert command[:2] == ["codex", "exec"]
        assert "--ephemeral" in command
        assert "--sandbox" in command
        assert "read-only" in command
        assert "--output-last-message" in command
        assert "opencode" not in command
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("skill_scripts.llm_sql_generator.subprocess.run", _fake_run)

    raw = call_llm(provider="codex", model="none", prompt_text="anything", timeout_sec=1.0)
    parsed = parse_llm_response(raw)
    assert parsed["sql"].startswith("SELECT TOP 7")
    assert parsed["used_tables"] == ["ACTMK"]
