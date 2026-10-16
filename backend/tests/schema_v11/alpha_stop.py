"""Stop only the matching owned local alpha through its protected local transport."""

import argparse
import http.client
import json
from pathlib import Path
from typing import Any

from tests.schema_v11.alpha_files import AlphaFiles, _read


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alpha-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8474)
    args = parser.parse_args()
    scope = AlphaFiles(args.alpha_root)  # Metadata admission only; no DB open or creation.
    expected = _read(scope.path / "controller.lock")
    origin = f"http://127.0.0.1:{args.port}"
    connection = http.client.HTTPConnection("127.0.0.1", args.port, timeout=60)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("alpha admission refused")
        html = response.read(131072).decode()
        token = html.split('name="preview-token" content="', 1)[1].split('"', 1)[0]

        def request(operation: str) -> dict[str, Any]:
            connection.request(
                "GET" if operation == "state" else "POST",
                "/" + operation,
                body=None if operation == "state" else b"",
                headers={}
                if operation == "state"
                else {"Origin": origin, "X-Preview-Token": token},
            )
            reply = connection.getresponse()
            if reply.status != 200:
                raise ValueError("alpha command refused")
            value = json.loads(reply.read(131072))
            if type(value) is not dict:
                raise ValueError("alpha response refused")
            if value.get("session") != scope.metadata["session"] or value.get(
                "controller_pid"
            ) != expected.get("pid"):
                raise ValueError("different alpha controller; not stopping it")
            return value

        request("state")  # Verify the live controller before sending any mutation.
        before = request("pause")
        stopped = request("shutdown")
        if before["digest"] != stopped["digest"]:
            raise ValueError("unexpected shutdown state")
        print(
            f"Stopped alpha controller {stopped['controller_pid']}; "
            f"revision {stopped['revision']} retained, digest {stopped['digest']}"
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
