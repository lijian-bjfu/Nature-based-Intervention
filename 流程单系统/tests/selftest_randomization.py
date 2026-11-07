"""分层区组随机分组 · 集成自测。端口 18774；数据根必须是从未用过的 /tmp 新目录（已存在则拒绝运行）。
用法：python3 tests/selftest_randomization.py [目录后缀]    （默认后缀 run1）"""
import os, re, sys, threading, time, json, urllib.request, urllib.parse, urllib.error
_P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_P, _P + "/app"]
from http.server import ThreadingHTTPServer
import config, flow, judging, questionnaire, scales
import server, state as state_mod, randomization as rz

ROOT = "/tmp/nbi_rand_selftest_20261107_" + (sys.argv[1] if len(sys.argv) > 1 else "run1")
if os.path.exists(ROOT):
    sys.exit("目录已存在，请换一个后缀：" + ROOT)
os.makedirs(ROOT + "/runtime"); os.makedirs(ROOT + "/data/formal"); os.makedirs(ROOT + "/data/pilot_and_test/test")
state_mod.RUNTIME_DIR = ROOT + "/runtime"
state_mod.CURRENT_RUN_POINTER = ROOT + "/runtime/current_run.json"
state_mod.default_data_root = lambda: ROOT + "/data"
server._default_data_root = lambda: ROOT + "/data"
DR = ROOT + "/data"
PORT = 18774
B = "http://127.0.0.1:%d" % PORT
SEQ = rz.build_sequences()
FAILS = []

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FAILS.append(msg)

httpd = None
def start_server():
    global httpd
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
def stop_server():
    httpd.shutdown(); httpd.server_close()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
opener = urllib.request.build_opener(NoRedirect)
def get(p): return urllib.request.urlopen(B + p).read().decode()
def post(p, data):
    body = urllib.parse.urlencode(data, doseq=True).encode()
    try:
        r = opener.open(B + p, body); return r.status
    except urllib.error.HTTPError as e:
        return e.code

def start(pid, mode):
    check(post("/start", {"data_root": DR, "mode": mode, "participant_id": pid}) == 303, "start %s/%s" % (mode, pid))
def edit(pid, mode, **kw):
    st = state_mod.load_state(DR, pid, mode); st.update(kw); state_mod.save_state(st)
def goto(pid, mode, page):
    st = state_mod.load_state(DR, pid, mode); st["current_page"] = page; st["history"].append(page); state_mod.save_state(st)
def load(pid, mode="experiment"): return state_mod.load_state(DR, pid, mode)

def t0_form(page, high):
    form = {}
    sc = scales.STAI_T; lo = sc["value_start"]; top = len(sc["options"]) - 1
    for b in page["blocks"]:
        t = b["type"]
        if t == "multi": form[b["key"]] = ["0"]
        elif t == "slider": form[b["key"]] = "50"
        elif t == "basic_info": form["A_age"] = "20"; form["A_gender"] = "0"
        elif t == "numeric":
            for k, _ in b["items"]: form[k] = str(b["scale_min"])
        else:
            for k, _ in b["items"]:
                m = re.match(r"T0_stait_(\d+)$", k)
                if m:
                    rev = int(m.group(1)) in sc["reverse"]
                    form[k] = str(0 if (rev == high) else top)  # high: 非反向题选最大、反向题选最小
                else: form[k] = "0"
    return form

def do_t0(pid, mode, high):
    goto(pid, mode, "q_t0")
    for page in questionnaire.QUESTIONNAIRES["T0"]["pages"]:
        f = t0_form(page, high); f["direction"] = "next"
        post("/qanswer", f)
    st = load(pid, mode)
    check(st["questionnaires"]["T0"]["submitted"], "%s T0 已提交" % pid)
    total = judging.stait_total_score(st["questionnaires"]["T0"]["answers"])
    check((total >= config.STAI_T_CUTOFF) == high, "%s STAI-T=%s 层符合预期(%s)" % (pid, total, "高" if high else "低"))
    return st

def expect(pid, stratum, position):
    st = load(pid); r = st.get("randomization")
    ok = bool(r) and r["stratum"] == stratum and r["position"] == position and r["condition"] == SEQ[stratum][position - 1]
    check(ok, "%s randomization=%s (期望 %s 层第 %d 位 → %s)" % (pid, r and (r["stratum"], r["position"], r["condition"]), stratum, position, SEQ[stratum][position - 1]))
    return st

def reveal(pid, stratum, position):
    goto(pid, "experiment", "reveal_group")
    h = get("/page")
    check("揭晓组别" in h and "高焦虑" in h + "低焦虑", "%s 第12页可见揭晓按钮和所在层" % pid)
    check("第 %d 位" % position not in h and "区组" not in h.replace("每层每 4 人", "") and "<table" not in h, "%s 第12页不含层内位置/区组/序列表" % pid)
    check("分层区组随机（按 STAI-T 分层，每层每 4 人 2:2），组别已在 T0 提交时锁定。" not in h, "%s 揭晓前不显示分组依据句" % pid)
    post("/group_random", {})
    st = load(pid); cond = SEQ[stratum][position - 1]
    check(st["group"] == cond and st["group_code"] == ("1" if cond == "实验组" else "2") and st["group_method"] == "stratified_block",
          "%s 揭晓后 group=%s code=%s method=%s" % (pid, st["group"], st["group_code"], st["group_method"]))
    h2 = get("/page")
    check("分层区组随机（按 STAI-T 分层，每层每 4 人 2:2），组别已在 T0 提交时锁定。" in h2 and "第 %d 位" % position not in h2 and "<table" not in h2,
          "%s 揭晓后页面含分组依据句且不含位置" % pid)
    post("/group_random", {})
    check(load(pid)["group"] == cond, "%s 重复点击揭晓不改变组别" % pid)

def finish(): post("/finish", {})

start_server()
# ---- 1. P001-P004 ----
for pid, high, stratum, pos in [("P001", True, "high", 1), ("P002", False, "low", 1), ("P003", True, "high", 2), ("P004", False, "low", 2)]:
    start(pid, "experiment"); do_t0(pid, "experiment", high); expect(pid, stratum, pos); reveal(pid, stratum, pos); finish()
    check(os.path.isdir(DR + "/formal/raw/psycho/sub-" + pid), "%s 正常结束后文件夹改回 sub-%s" % (pid, pid))
log = open(DR + "/formal/raw/session_notes/sub-P001/log.csv", encoding="utf-8-sig").read().splitlines()
hdr, row = log[0].split(","), log[1].split(",")
check(row[hdr.index("stratum")] == "high" and row[hdr.index("stratum_position")] == "1" and row[hdr.index("group_method")] == "stratified_block",
      "P001 log.csv stratum/stratum_position/group_method 正确")
# ---- 2. P005 重启续接 ----
start("P005", "experiment"); st = do_t0("P005", "experiment", True); r1 = expect("P005", "high", 3)["randomization"]
stop_server(); start_server()
check("<html" in get("/page").lower() or "<!doctype" in get("/page").lower(), "重启后 /page 续接 P005")
with server._STATE_LOCK:
    s5 = state_mod.get_current_run_state(); server._lock_randomization(s5)
check(load("P005")["randomization"] == r1, "重启/重复调用后 P005 不重复取号")
post("/qanswer", {"direction": "next"})
check(load("P005")["randomization"] == r1, "重复 POST /qanswer 后 P005 不重复取号")
reveal("P005", "high", 3); finish()
# ---- 3. P006 保持 _break_，P007 同层 ----
start("P006", "experiment"); do_t0("P006", "experiment", False); expect("P006", "low", 3)
check(os.path.isdir(DR + "/formal/raw/psycho/_break_sub-P006"), "P006 仍为 _break_ 文件夹")
start("P007", "experiment"); do_t0("P007", "experiment", False); expect("P007", "low", 4)
# ---- 4. P008 判不适合 ----
start("P008", "experiment"); goto("P008", "experiment", "verify_h10")
post("/verdict", {"verdict": "unfit"}); post("/complete", {"checked": ["0"]})
check(load("P008")["current_page"] == "end", "P008 判不适合 → 结束页")
finish()
check(not load("P008").get("randomization"), "P008 未取号")
# ---- 5. 调整模式 ----
start("P001", "debug"); do_t0("P001", "debug", False)
dst = load("P001", "debug"); check(not dst.get("randomization"), "调整模式不写 randomization")
goto("P001", "debug", "reveal_group"); h = get("/page")
check("若在实验模式下，本被试将取 低焦虑层第 5 位 → %s" % SEQ["low"][4] in h, "调整模式第12页显示预览（低层第5位）")
check(h.count("<table") == 2 and "<details>" in h and "两张随机序列（调试用）" in h and "<details open" not in h, "调整模式含默认折叠的两张序列表")
check("<td>P001</td>" in h and "<td>P006</td>" in h and "<td>P007</td>" in h, "序列表标注已用位置的被试编号")
check("手动设定组别" in h and "调整模式下不执行" in h, "调整模式保留手动设定与按钮不工作说明")
post("/group_random", {}); check(not load("P001", "debug")["group"], "调整模式点揭晓不生效")
post("/group_set", {"group_value": "2"}); check(load("P001", "debug")["group"] == "对照组", "调整模式手动设定仍可用")
dlog = open(DR + "/pilot_and_test/test/raw/session_notes/_break_D_sub-P001/log.csv", encoding="utf-8-sig").read().splitlines()
dh, dr_ = dlog[0].split(","), dlog[1].split(",")
check(dr_[dh.index("stratum")] == "" and dr_[dh.index("stratum_position")] == "", "调整模式 log.csv 两列为空")
# 调整模式未提交 T0 的预览
start("P002", "debug"); goto("P002", "debug", "reveal_group")
check("T0 未提交，无法预览" in get("/page"), "调整模式 T0 未提交时提示无法预览")
# 实验模式下一位不受影响
start("P009", "experiment"); do_t0("P009", "experiment", False); expect("P009", "low", 5)
# ---- 6. 位置用尽 + 坏 state.json ----
fake = DR + "/formal/raw/psycho/_break_sub-P900"; os.makedirs(fake)
json.dump({"participant_id": "P900", "randomization": {"stratum": "high", "position": 100}}, open(fake + "/state.json", "w"))
bad = DR + "/formal/raw/psycho/_break_sub-P901"; os.makedirs(bad); open(bad + "/state.json", "w").write("{坏")
os.makedirs(DR + "/formal/raw/psycho/_other"); json.dump({"randomization": {"stratum": "high", "position": 99}}, open(DR + "/formal/raw/psycho/_other/state.json", "w"))
check(rz.used_positions(DR, "high") == [1, 2, 3, 100], "used_positions 忽略下划线其他文件夹、跳过坏文件：%s" % rz.used_positions(DR, "high"))
start("P010", "experiment"); do_t0("P010", "experiment", True)
check(not load("P010").get("randomization"), "位置用尽时 P010 未写入 randomization")
goto("P010", "experiment", "reveal_group"); h = get("/page")
check("无法分组" in h and "已用尽" in h and 'action="/group_random"' not in h and 'id="complete-btn"' not in h, "位置用尽时第12页红字提示、无揭晓/推进按钮")
post("/group_random", {}); check(not load("P010").get("group"), "位置用尽时不能揭晓")
try: rz.assign_for("high", list(range(1, 101)), SEQ); check(False, "assign_for 应抛异常")
except rz.RandomizationError as e: check(True, "assign_for 位置超出抛 RandomizationError")
print("\n数据根：", ROOT)
print("全部通过" if not FAILS else "失败 %d 项：%s" % (len(FAILS), FAILS))
sys.exit(1 if FAILS else 0)
