import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess

STREAM = os.getenv("STREAM", "agent-jobs")
GROUP = os.getenv("GROUP", "workers")
REDIS_HOST = os.getenv("REDIS_HOST", "redis.sba.svc.cluster.local")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")


def run_redis_cli(args):
    cmd = [
        "redis-cli",
        "--raw",
        "-h",
        REDIS_HOST,
        "-p",
        REDIS_PORT,
        "-n",
        REDIS_DB,
    ] + args
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)


def get_stream_length():
    out = run_redis_cli(["XINFO", "STREAM", STREAM])
    lines = [l.strip() for l in out.splitlines() if l.strip() != ""]
    for i in range(0, len(lines) - 1, 2):
        if lines[i] == "length":
            return float(lines[i + 1])
    return 0.0


def get_group_lag_pending():
    out = run_redis_cli(["XINFO", "GROUPS", STREAM])
    lines = [l.strip() for l in out.splitlines() if l.strip() != ""]
    lag = 0.0
    pending = 0.0

    idx = None
    for i in range(0, len(lines) - 1, 2):
        if lines[i] == "name" and lines[i + 1] == GROUP:
            idx = i
            break
    if idx is None:
        return lag, pending

    for j in range(idx, min(idx + 400, len(lines) - 1), 2):
        k = lines[j]
        v = lines[j + 1]
        if k == "lag":
            try:
                lag = float(v)
            except Exception:
                pass
        elif k == "pending":
            try:
                pending = float(v)
            except Exception:
                pass

    return lag, pending


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ["/metrics", "/"]:
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = get_stream_length()
            lag, pending = get_group_lag_pending()

            body = []
            body.append("# HELP sba_redis_stream_length Redis Streams stream length\n")
            body.append("# TYPE sba_redis_stream_length gauge\n")
            body.append(f'sba_redis_stream_length{{stream="{STREAM}"}} {length}\n')

            body.append(
                "# HELP sba_redis_stream_group_lag Redis Streams consumer group lag\n"
            )
            body.append("# TYPE sba_redis_stream_group_lag gauge\n")
            body.append(
                f'sba_redis_stream_group_lag{{stream="{STREAM}",group="{GROUP}"}} {lag}\n'
            )

            body.append(
                "# HELP sba_redis_stream_group_pending Redis Streams consumer group pending entries\n"
            )
            body.append("# TYPE sba_redis_stream_group_pending gauge\n")
            body.append(
                f'sba_redis_stream_group_pending{{stream="{STREAM}",group="{GROUP}"}} {pending}\n'
            )

            payload = "".join(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            msg = f"exporter_error {e}\n".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    srv = HTTPServer(("0.0.0.0", port), Handler)
    print(
        f"[exporter] listening :{port} stream={STREAM} group={GROUP} redis={REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )
    srv.serve_forever()
