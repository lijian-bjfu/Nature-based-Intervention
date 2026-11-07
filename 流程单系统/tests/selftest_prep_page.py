"""准备检查页 + 标记位置说明自测。端口 18773，数据根/运行态指针都放 /tmp 新目录。"""
import os, re, sys, threading, time, urllib.request, urllib.parse
_P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_P, _P + "/app"]
from http.server import ThreadingHTTPServer
import config
import server, state as state_mod

ROOT = "/tmp/nbi_prep_selftest_20261107"
os.makedirs(ROOT + "/runtime", exist_ok=True)
os.makedirs(ROOT + "/data", exist_ok=True)
state_mod.RUNTIME_DIR = ROOT + "/runtime"
state_mod.CURRENT_RUN_POINTER = ROOT + "/runtime/current_run.json"
state_mod.default_data_root = lambda: ROOT + "/data"
server._default_data_root = lambda: ROOT + "/data"

PORT = 18773
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), server.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % PORT

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
opener = urllib.request.build_opener(NoRedirect)
def get(p):
    return urllib.request.urlopen(B + p).read().decode()
def post(p, data):
    try:
        r = opener.open(B + p, urllib.parse.urlencode(data).encode())
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")

h = get("/")
print("cards", h.count('class="prep-card"'))
print("checkboxes", len(re.findall(r'<input type="checkbox" name="checked"', h)))
print("details", h.count("<details>"))
# each details immediately follows a label line
print("details after label", len(re.findall(r'</label><details>', h)))
print("button disabled initially (script gates):", 'id="complete-btn"' in h and "btn.disabled = !allChecked" in h)
print("path lines:", re.findall(r'class="path">([^<]+)<', h))
print("prep_confirm ->", post("/prep_confirm", {}))
h2 = get("/")
print("settings page reached:", "准备检查" not in h2 and 'action="/start"' in h2)

# debug mode pages
st, loc = post("/start", {"data_root": ROOT + "/data", "mode": "debug", "participant_id": "P901"})
print("start", st, loc)
for n in (6, 7, 9, 11, 13, 15):
    pid = next(k for k, v in server.flow.PAGES.items() if v.get("number") == n)
    post("/jump", {"page_id": pid})
    page = get("/page")
    print(n, pid, re.findall(r'已在 SensorBridge 点[^<]*', page))
httpd.shutdown()
