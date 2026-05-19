import json
import sys
from urllib import request


BASE_URL = "http://127.0.0.1:8000"


def get(path):
    with request.urlopen(BASE_URL + path, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    health = get("/api/health")
    assert health["status"] == "ok", health

    payload = post("/api/query", {"question": "What papers are indexed?", "top_k": 3})
    assert "answer" in payload, payload
    assert "sources" in payload, payload
    print("docRAG smoke test passed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        raise
