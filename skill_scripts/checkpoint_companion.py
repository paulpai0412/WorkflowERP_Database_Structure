from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from typing import Any, Iterator
from urllib.parse import urlparse

from skill_scripts.report_harness import ReportHarness, ReportHarnessError
from skill_scripts.report_harness_state import (
    CHECKPOINT_DEFINITIONS,
    append_audit_event,
    load_run_state,
    write_confirmation,
)


MAX_REQUEST_BYTES = 65536


class CheckpointHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


@dataclass
class RunningCheckpointServer:
    httpd: CheckpointHTTPServer
    thread: Thread
    base_url: str


class CheckpointCompanionServer:
    @staticmethod
    @contextmanager
    def serve(
        run_dir: str | Path,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> Iterator[RunningCheckpointServer]:
        run_path = Path(run_dir)

        class Handler(BaseHTTPRequestHandler):
            def _json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _html(self, status: int, body: str) -> None:
                content = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def _path_parts(self) -> list[str]:
                return [part for part in urlparse(self.path).path.split("/") if part]

            def _read_json(self) -> dict[str, Any] | None:
                try:
                    content_length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self._json(400, {"status": "bad_request"})
                    return None

                if content_length > MAX_REQUEST_BYTES:
                    self._json(413, {"status": "request_too_large"})
                    return None

                try:
                    raw_body = self.rfile.read(content_length)
                    payload = json.loads(raw_body.decode("utf-8"))
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    self._json(400, {"status": "bad_request"})
                    return None
                if not isinstance(payload, dict):
                    self._json(400, {"status": "bad_request"})
                    return None
                return payload

            def do_GET(self) -> None:
                parts = self._path_parts()
                if len(parts) != 4 or parts[:1] != ["runs"] or parts[2] != "checkpoints" or parts[3] != "current":
                    self._json(404, {"status": "not_found"})
                    return

                run_id = parts[1]
                if run_path.name != run_id:
                    self._json(409, {"status": "wrong_run"})
                    return

                state = load_run_state(run_path)
                checkpoints = state.get("checkpoints", [])
                if not checkpoints:
                    self._json(404, {"status": "no_checkpoint"})
                    return

                checkpoint = checkpoints[-1]["checkpoint"]
                definition = CHECKPOINT_DEFINITIONS[checkpoint]
                confirm_url = f"/api/runs/{escape(run_id)}/checkpoints/{escape(checkpoint)}/confirm"
                actions = "\n".join(
                    f"<li><button type=\"button\" data-action=\"{escape(action)}\">{escape(action)}</button></li>"
                    for action in definition["actions"]
                )
                self._html(
                    200,
                    "\n".join(
                        [
                            "<!doctype html>",
                            "<html lang=\"zh-Hant\">",
                            "<head><meta charset=\"utf-8\"><title>Checkpoint Companion</title></head>",
                            "<body>",
                            f"<main data-confirm-url=\"{confirm_url}\">",
                            f"<h1>{escape(definition['title'])}</h1>",
                            f"<p><code>{confirm_url}</code></p>",
                            f"<ul>{actions}</ul>",
                            "</main>",
                            "</body>",
                            "</html>",
                        ]
                    ),
                )

            def do_POST(self) -> None:
                parts = self._path_parts()
                if (
                    len(parts) != 6
                    or parts[:2] != ["api", "runs"]
                    or parts[3] != "checkpoints"
                    or parts[5] != "confirm"
                ):
                    self._json(404, {"status": "not_found"})
                    return

                run_id = parts[2]
                checkpoint = parts[4]
                if run_path.name != run_id:
                    self._json(409, {"status": "wrong_run"})
                    return

                try:
                    payload = self._read_json()
                    if payload is None:
                        return
                    action = payload["action"]
                    if payload.get("checkpointId", checkpoint) != checkpoint:
                        self._json(409, {"status": "wrong_checkpoint"})
                        return

                    harness = ReportHarness(run_path)
                    harness.confirm(checkpoint, action)
                    confirmation = write_confirmation(run_path, checkpoint, payload)
                    append_audit_event(
                        run_path,
                        "checkpoint_confirmed",
                        {"checkpoint": checkpoint, "action": action},
                    )
                except (KeyError, json.JSONDecodeError):
                    self._json(400, {"status": "bad_request"})
                    return
                except (ReportHarnessError, ValueError) as error:
                    self._json(400, {"status": "rejected", "error": str(error)})
                    return

                self._json(200, {"status": "confirmed", "confirmation": confirmation})

            def log_message(self, format: str, *args: object) -> None:
                return

        httpd = CheckpointHTTPServer((host, port), Handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        running = RunningCheckpointServer(
            httpd=httpd,
            thread=thread,
            base_url=f"http://{host}:{httpd.server_address[1]}",
        )
        try:
            yield running
        finally:
            httpd.shutdown()
            thread.join(timeout=5)
            httpd.server_close()
