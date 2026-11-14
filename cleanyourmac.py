#!/usr/bin/env python3
"""
CleanYourMac-AI — Free RAM, Audit Bloat & Run 0-GPU Offline AI (MIT)
Zero external Python dependencies (stdlib only). Works on macOS & Linux.
"""
import argparse
import http.server
import json
import os
import platform
import shutil
import socketserver
import subprocess
import urllib.request

PORT = 8787


def get_system_stats():
    sys_name = platform.system()
    total_mb, free_mb = 8192, 2048
    hogs = []
    try:
        if sys_name == "Darwin":
            mem_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip())
            total_mb = mem_bytes // (1024 * 1024)
            vm = subprocess.check_output(["vm_stat"]).decode()
            free_pages = 0
            for line in vm.splitlines():
                if "Pages free:" in line or "Pages inactive:" in line:
                    val = int(line.split(":")[1].strip().rstrip("."))
                    free_pages += val
            free_mb = (free_pages * 16384) // (1024 * 1024)
            ps_out = subprocess.check_output(["ps", "-Ao", "pid,rss,comm", "-r"]).decode(errors="ignore")
            for line in ps_out.splitlines()[1:9]:
                parts = line.strip().split(None, 2)
                if len(parts) == 3:
                    hogs.append({
                        "pid": parts[0],
                        "mb": round(int(parts[1]) / 1024.0, 1),
                        "name": os.path.basename(parts[2])[:36],
                    })
        else:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total_mb = int(line.split()[1]) // 1024
                    elif line.startswith("MemAvailable:"):
                        free_mb = int(line.split()[1]) // 1024
            ps_out = subprocess.check_output(["ps", "-eo", "pid,rss,comm", "--sort=-rss"]).decode(errors="ignore")
            for line in ps_out.splitlines()[1:9]:
                parts = line.strip().split(None, 2)
                if len(parts) == 3:
                    hogs.append({
                        "pid": parts[0],
                        "mb": round(int(parts[1]) / 1024.0, 1),
                        "name": parts[2][:36],
                    })
    except Exception:
        pass

    reclaimable = []
    home = os.path.expanduser("~")
    candidates = [
        ("User Caches", os.path.join(home, "Library/Caches") if sys_name == "Darwin" else os.path.join(home, ".cache")),
        ("npm Cache", os.path.join(home, ".npm/_cacache")),
        ("pip Cache", os.path.join(home, "Library/Caches/pip") if sys_name == "Darwin" else os.path.join(home, ".cache/pip")),
    ]
    total_cache_mb = 0.0
    for label, path in candidates:
        if os.path.isdir(path):
            sz = 0
            try:
                for root, _, files in os.walk(path):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        try:
                            sz += os.path.getsize(fp)
                        except OSError:
                            pass
                    if sz > 2 * 1024 * 1024 * 1024:
                        break
            except Exception:
                pass
            mb = round(sz / (1024.0 * 1024.0), 1)
            total_cache_mb += mb
            reclaimable.append({"label": label, "path": path, "mb": mb})

    myca_bin = shutil.which("myca-modchip") or os.path.join(home, ".local/bin/myca-modchip")
    has_myca = os.path.isfile(myca_bin)
    model_path = os.path.join(home, ".myca/models/smollm2-135m-ghr.myca")
    has_model = os.path.isfile(model_path)

    return {
        "os": f"{sys_name} {platform.machine()}",
        "total_mb": total_mb,
        "free_mb": free_mb,
        "used_mb": max(0, total_mb - free_mb),
        "reclaimable_mb": round(total_cache_mb, 1),
        "caches": reclaimable,
        "hogs": hogs,
        "has_myca": has_myca,
        "has_model": has_model,
        "model_path": model_path,
    }


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CleanYourMac-AI — Free RAM + 0-GPU Offline AI</title>
<style>
  body{margin:0;background:#0B0C10;color:#EAE6DF;font-family:system-ui,-apple-system,sans-serif}
  .wrap{max-width:980px;margin:0 auto;padding:28px 20px}
  .top{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #222530;padding-bottom:16px;margin-bottom:24px}
  .badge{background:#C8A86B22;color:#C8A86B;border:1px solid #C8A86B55;padding:4px 12px;border-radius:99px;font-size:12px;font-weight:600}
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px}
  .card{background:#13161E;border:1px solid #232734;border-radius:14px;padding:18px}
  .num{font-size:28px;font-weight:700;color:#5AE39B;margin-top:6px}
  .sub{color:#8A92A6;font-size:13px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{text-align:left;padding:9px 8px;border-bottom:1px solid #1E222E}
  th{color:#8A92A6;font-weight:600}
  .btn{background:#C8A86B;color:#0B0C10;border:0;padding:10px 16px;border-radius:10px;font-weight:700;cursor:pointer}
  .btn:hover{filter:brightness(1.08)}
  .row{display:grid;grid-template-columns:1.1fr 0.9fr;gap:16px}
  input{width:100%;box-sizing:border-box;background:#0F1117;border:1px solid #282D3B;color:#EAE6DF;padding:11px 12px;border-radius:10px;margin:8px 0}
  pre{background:#0F1117;border:1px solid #232734;border-radius:10px;padding:12px;white-space:pre-wrap;font-size:13px;min-height:80px;color:#5AE39B}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div><h2 style="margin:0">CleanYourMac-AI</h2><div class="sub">Reclaim RAM &amp; Bloat &rarr; Run 0-GPU Offline AI via MYCA-Modchip</div></div>
    <span class="badge" id="osBadge">Scanning...</span>
  </div>
  <div class="grid">
    <div class="card"><div class="sub">Free / Available RAM</div><div class="num" id="freeRam">--</div></div>
    <div class="card"><div class="sub">Reclaimable Caches</div><div class="num" style="color:#C8A86B" id="cacheMb">--</div></div>
    <div class="card"><div class="sub">Offline AI Engine (0 GPU)</div><div class="num" style="font-size:20px" id="aiState">--</div></div>
  </div>
  <div class="row">
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <b>Top Memory Hogs</b>
        <button class="btn" onclick="refreshStats()">Rescan</button>
      </div>
      <table><thead><tr><th>Process</th><th>PID</th><th>RAM</th></tr></thead><tbody id="hogs"></tbody></table>
    </div>
    <div class="card">
      <b>Local 0-GPU AI Assistant</b>
      <div class="sub" style="margin-top:4px">Runs on freed RAM with zero cloud calls.</div>
      <input id="prompt" value="How can I keep my laptop fast and private?" />
      <button class="btn" onclick="askAI()">Ask Offline AI</button>
      <pre id="aiOut">Ready.</pre>
    </div>
  </div>
</div>
<script>
async function refreshStats(){
  const r=await fetch('/api/stats');const d=await r.json();
  document.getElementById('osBadge').textContent=d.os+' ('+d.total_mb+' MB RAM)';
  document.getElementById('freeRam').textContent=d.free_mb+' MB';
  document.getElementById('cacheMb').textContent=d.reclaimable_mb+' MB';
  document.getElementById('aiState').textContent=(d.has_myca&&d.has_model)?'MYCA Ready (69 MB)':'Install myca-modchip';
  document.getElementById('hogs').innerHTML=d.hogs.map(h=>`<tr><td>${h.name}</td><td>${h.pid}</td><td>${h.mb} MB</td></tr>`).join('');
}
async function askAI(){
  const out=document.getElementById('aiOut');out.textContent='Running on CPU (0 GPU)...';
  const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:document.getElementById('prompt').value})});
  const d=await r.json();out.textContent=d.output;
}
refreshStats();
</script>
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, ctype, body):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/":
            self._send(200, "text/html; charset=utf-8", HTML_PAGE)
        elif self.path == "/api/stats":
            self._send(200, "application/json", json.dumps(get_system_stats()))
        else:
            self._send(404, "application/json", '{"error":"not found"}')

    def do_POST(self):
        if self.path == "/api/ask":
            n = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(n).decode() or "{}")
            prompt = payload.get("prompt", "Hello")
            st = get_system_stats()
            home = os.path.expanduser("~")
            myca = shutil.which("myca-modchip") or os.path.join(home, ".local/bin/myca-modchip")
            if os.path.isfile(myca) and os.path.isfile(st["model_path"]):
                out = subprocess.check_output(
                    [myca, "run", st["model_path"], "-p", prompt, "-n", "48"],
                    stderr=subprocess.STDOUT,
                    timeout=30,
                ).decode(errors="ignore")
            else:
                out = "Install MYCA-Modchip first:\n  curl -fsSL https://raw.githubusercontent.com/brienteth/myca-ghr-modchip/main/install.sh | sh\n  myca-modchip pull smollm2-135m"
            self._send(200, "application/json", json.dumps({"output": out}))
        else:
            self._send(404, "application/json", '{"error":"not found"}')


def main():
    ap = argparse.ArgumentParser(description="CleanYourMac-AI")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--scan", action="store_true", help="Print JSON scan and exit")
    args = ap.parse_args()
    if args.scan:
        print(json.dumps(get_system_stats(), indent=2))
        return
    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"CleanYourMac-AI running at http://127.0.0.1:{args.port}/")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
