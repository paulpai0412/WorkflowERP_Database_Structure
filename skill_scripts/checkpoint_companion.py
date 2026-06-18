from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from typing import Any, Iterator
from urllib.parse import urlparse

from skill_scripts.report_harness import ReportHarness, ReportHarnessError
from skill_scripts.report_harness_state import append_audit_event, write_confirmation


@dataclass
class RunningCheckpointServer:
    httpd: ThreadingHTTPServer
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

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                parts = [part for part in parsed.path.split("/") if part]
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
                    content_length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
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

        httpd = ThreadingHTTPServer((host, port), Handler)
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
