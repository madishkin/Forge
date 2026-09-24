import http.client
import time
import urllib.error
import urllib.request


def wait_for_health(
    domain: str,
    port: int = 80,
    path: str = "/",
    timeout: float = 15.0,
    interval: float = 0.5,
    host: str = "127.0.0.1",
) -> bool:
    if not path.startswith("/"):
        path = f"/{path}"
    url = f"http://{host}:{port}{path}"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url, headers={"Host": domain}, method="GET")
            remaining = max(0.1, deadline - time.monotonic())
            req_timeout = min(interval, remaining)
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                code = resp.status
                if 200 <= code < 400:
                    return True
        except urllib.error.HTTPError as exc:
            if 200 <= exc.code < 400:
                return True
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
            pass

        time.sleep(interval)

    return False
