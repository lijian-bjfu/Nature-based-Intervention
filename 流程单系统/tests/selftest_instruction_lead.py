"""
自测：计时页"念指导语加时"（config.INSTRUCTION_LEAD_SEC）。

用法（在"流程单系统"文件夹里）：
    python3 tests/selftest_instruction_lead.py

做的事：
  - 在 127.0.0.1:18768 起一个临时服务（不用 config.PORT）；
  - 数据根和当前运行指针都指向一个新建的 /tmp/nbi_lead_selftest_* 目录，不碰真实的
    data/ 和 app_runtime/current_run.json（结束前后检查真实指针文件没有被改动）；
  - 调整模式：跳到第 6、7、9、11、13、15 页，取回 HTML，检查嵌入页面的计时配置：
    到时点 = 阶段时长 + 加时；书写页中途提示点 = 180 + 75 = 255 秒；
    页面上有"预定 … （含念指导语 …）"的说明文字；
  - 没有加时项的页面（第 4 页、第 1 页）不出现计时器。

测试文件留着，不要删。
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
FLOW_ROOT = os.path.dirname(HERE)
sys.path.insert(0, FLOW_ROOT)
sys.path.insert(0, os.path.join(FLOW_ROOT, "app"))

import config  # noqa: E402
import server  # noqa: E402
import state as state_mod  # noqa: E402

PORT = 18768
BASE = "http://127.0.0.1:%d" % PORT
REAL_POINTER = os.path.join(FLOW_ROOT, "app_runtime", "current_run.json")

FAILS = []


def check(cond, label):
    print(("  PASS " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


def md5_of(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def get(path):
    return urllib.request.urlopen(BASE + path).read().decode("utf-8")


def post(path, data):
    body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    return urllib.request.urlopen(req).read().decode("utf-8")


def fmt(sec):
    sec = int(round(sec))
    return "%02d:%02d" % (sec // 60, sec % 60)


def timer_cfg(html):
    """取出页面里嵌入的 const TIMER = {...}; 配置。"""
    m = re.search(r"const TIMER = (\{.*?\});\n", html, re.S)
    return json.loads(m.group(1)) if m else None


# 页码 → (timer_key 对应的阶段时长（秒）, 加时（秒）)
EXPECT = {
    6: ("practice", config.PRACTICE_DURATION_SEC, config.INSTRUCTION_LEAD_SEC["practice"]),
    7: ("rest", config.REST_DURATION_SEC, config.INSTRUCTION_LEAD_SEC["rest"]),
    9: ("writing", config.WRITING_DURATION_SEC, config.INSTRUCTION_LEAD_SEC["writing"]),
    11: ("post_writing_rest", config.POST_WRITING_REST_DURATION_SEC,
         config.INSTRUCTION_LEAD_SEC["post_writing_rest"]),
    13: ("intervention", config.INTERVENTION_DURATION_SEC, config.INSTRUCTION_LEAD_SEC["intervention"]),
    15: ("post_intervention_rest", config.POST_INTERVENTION_REST_DURATION_SEC,
         config.INSTRUCTION_LEAD_SEC["post_intervention_rest"]),
}
PAGE_IDS = {
    6: "practice", 7: "rest", 9: "writing", 11: "post_writing_rest",
    13: "intervention", 15: "post_intervention_rest",
}


def main():
    real_before = md5_of(REAL_POINTER)

    test_root = tempfile.mkdtemp(prefix="nbi_lead_selftest_", dir="/tmp")
    data_root = os.path.join(test_root, "data")
    os.makedirs(data_root)
    state_mod.CURRENT_RUN_POINTER = os.path.join(test_root, "app_runtime", "current_run.json")
    print("测试数据根：%s" % test_root)

    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        run_debug(data_root)
    finally:
        httpd.shutdown()

    real_after = md5_of(REAL_POINTER)
    check(real_before == real_after, "真实的 app_runtime/current_run.json 未被改动")
    print()
    if FAILS:
        print("共 %d 项失败：" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        sys.exit(1)
    print("全部通过。")


def run_debug(data_root):
    print("[调整模式]")
    post("/start", {"data_root": data_root, "mode": "debug", "participant_id": "P001"})

    for page_no, (key, stage_sec, lead_sec) in EXPECT.items():
        post("/jump", {"page_id": PAGE_IDS[page_no]})
        html = get("/page")
        cfg = timer_cfg(html)
        label = "第 %d 页（%s）" % (page_no, PAGE_IDS[page_no])
        check(cfg is not None, label + "：页面嵌入了计时配置")
        if cfg is None:
            continue
        check(cfg["durationSec"] == stage_sec + lead_sec,
              label + "：到时点 %s = 阶段 %s + 加时 %s" % (
                  cfg["durationSec"], stage_sec, lead_sec))
        plan = "预定 %s（含念指导语 %s）" % (fmt(stage_sec + lead_sec), fmt(lead_sec))
        check(plan in html, label + "：页面显示“%s”" % plan)
        check("已用时" in html or 'id="timer-display"' in html, label + "：计时器元素存在")

        if PAGE_IDS[page_no] == "writing":
            check(cfg["midpointSec"] == 255, label + "：中途提示点 = 180 + 75 = 255（实际 %s）" % cfg["midpointSec"])
            check(cfg["midpointMessage"] and "请继续写" in cfg["midpointMessage"],
                  label + "：中途提示语仍为原文")
        else:
            check(cfg["midpointSec"] is None, label + "：没有中途提示")

    # 没有加时项的页面：不出现计时器、不出现"含念指导语"
    post("/jump", {"page_id": "check_signal"})
    html = get("/page")
    check('id="timer-display"' not in html and "含念指导语" not in html,
          "第 4 页（无计时器）行为不变：没有计时器和加时说明")
    check(timer_cfg(html) is None, "第 4 页没有嵌入计时配置")


if __name__ == "__main__":
    main()
