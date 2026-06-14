from __future__ import annotations

import argparse
import json
import threading
from typing import Any
from urllib.request import urlopen

from ccld_complaints.hosted_app.app import create_server, format_host


def _read_url(url: str) -> tuple[int, bytes]:
    with urlopen(url, timeout=5) as response:
        return response.status, response.read()


def run_scaffold_smoke_check(host: str = "127.0.0.1", port: int = 0) -> dict[str, object]:
    with create_server(host, port) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        bound_host, bound_port = server.server_address[:2]
        base_url = f"http://{format_host(bound_host)}:{bound_port}"
        try:
            health_status, health_body = _read_url(f"{base_url}/health")
            root_status, root_body = _read_url(f"{base_url}/")
            records_status, records_body = _read_url(f"{base_url}/source-records")
            facilities_status, facilities_body = _read_url(f"{base_url}/facilities")
        finally:
            server.shutdown()
            thread.join(timeout=5)

    payload = json.loads(health_body.decode("utf-8"))
    if health_status != 200 or payload.get("status") != "ok":
        raise RuntimeError("Hosted scaffold health check did not return ok.")
    if root_status != 200 or b"not a functioning reviewer workflow yet" not in root_body:
        raise RuntimeError("Hosted scaffold app shell did not return the placeholder notice.")
    if (
        records_status != 200
        or b"Fixture/sample source record list" not in records_body
        or b"Sample source traceability summary" not in records_body
    ):
        raise RuntimeError("Hosted scaffold source-record shell did not return the sample list.")
    if (
        facilities_status != 200
        or b"Read-only facility master sample view" not in facilities_body
        or b"Committed tiny public-source facility fixture rows" not in facilities_body
    ):
        raise RuntimeError("Hosted scaffold facility sample shell did not return the fixture list.")
    return payload if isinstance(payload, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the hosted scaffold smoke check.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)

    payload: dict[str, Any] = run_scaffold_smoke_check(args.host, args.port)
    print(f"Hosted scaffold smoke check passed: {json.dumps(payload, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())