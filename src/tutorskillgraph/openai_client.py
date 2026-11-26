"""Send a prepared request to the official Responses endpoint."""

import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

MODEL = "gpt-6-luna"


def complete(body, label):
    request = Request("https://api.openai.com/v1/responses", data=body,
                      headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
                               "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=120) as response:
                raw = json.load(response)
            break
        except HTTPError as exc:
            error = json.loads(exc.read()).get("error", {})
            if exc.code == 429 and error.get("code") != "insufficient_quota" and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f"{label}: HTTP {exc.code}; {error.get('type')} / {error.get('code')}") from None
    if raw["status"] != "completed":
        raise RuntimeError(f"{label}: {raw['status']} ({raw.get('incomplete_details')})")
    reply = "".join(c["text"] for item in raw["output"] if item["type"] == "message"
                    for c in item["content"] if c["type"] == "output_text")
    if not reply.strip():
        raise RuntimeError(f"{label}: completed without an output message")
    return raw, reply
