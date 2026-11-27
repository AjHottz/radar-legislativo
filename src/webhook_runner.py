"""Endpoint HTTP leve (stdlib) para acionamento do pipeline via n8n Docker/Cloud."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PipelineWebhookHandler(BaseHTTPRequestHandler):
    """Recebe POST /run-pipeline para disparar o fluxo Python em segundo plano ou sincrono."""

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Healthcheck simples para monitoramento do n8n."""
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "radar-legislativo-runner"})
            return
        self._send_json(404, {"error": "Endpoint nao encontrado"})

    def do_POST(self) -> None:
        """Dispara execucao do pipeline via CLI oficial."""
        if self.path != "/run-pipeline":
            self._send_json(404, {"error": "Endpoint nao encontrado"})
            return

        content_len = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            body = json.loads(raw_body or "{}")
        except ValueError:
            self._send_json(400, {"error": "JSON invalido"})
            return

        step = str(body.get("step", "all"))
        if step not in ("all", "extract", "transform", "load", "ai"):
            self._send_json(400, {"error": f"Step invalido: {step}"})
            return

        days = int(body.get("days", 2))
        limit = int(body.get("limit", 20))
        skip_ai = bool(body.get("skip_ai", False))
        run_date = body.get("run_date")

        cmd = [
            sys.executable
            , "-m"
            , "src.main"
            , "--step"
            , step
            , "--days"
            , str(days)
            , "--limit"
            , str(limit)
        ]
        if run_date:
            cmd.extend(["--run-date", str(run_date)])
        if skip_ai:
            cmd.append("--skip-ai")

        proc = subprocess.run(
            cmd
            , cwd=str(PROJECT_ROOT)
            , capture_output=True
            , text=True
            , timeout=600
        )
        status = 200 if proc.returncode == 0 else 500
        self._send_json(
            status
            , {
                "returncode": proc.returncode
                , "stdout": proc.stdout[-4000:]
                , "stderr": proc.stderr[-2000:]
            }
        )


def main() -> int:
    """Inicia servidor HTTP local na porta configurada (padrao 8085)."""
    host = os.getenv("RUNNER_HOST", "127.0.0.1")
    port = int(os.getenv("RUNNER_PORT", "8085"))
    server = HTTPServer((host, port), PipelineWebhookHandler)
    print(f"[OK] Runner HTTP ativo em http://{host}:{port} (POST /run-pipeline | GET /health)")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
