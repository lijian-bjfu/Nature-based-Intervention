"""
自测：警示清单项（第 4 页、第 17 页、第 18 页）的渲染与实验模式勾选逻辑。

用法（在"流程单系统"文件夹里）：
    python3 tests/selftest_warning_pages.py

做的事：
  - 在 127.0.0.1:18767 起一个临时服务（不用 config.PORT，不会和正在跑的流程单撞端口）；
  - 数据根和当前运行指针都指向一个新建的 /tmp/nbi_flow_selftest_* 目录，不碰真实的
    data/ 和 app_runtime/current_run.json（脚本结束前后会检查真实指针文件没有被改动）；
  - 调整模式：跳到第 1、4、17、18 页，取回 HTML 检查；
  - 实验模式：直接把当前页设为第 4 页，验证不勾警示项无法推进，勾完能推进，
    state.json 里记录的已勾项文字正确；再把当前页设为第 17 页，验证三项警示 + 普通清单
    没勾完不能推进。

测试文件留着，不要删。
"""
import hashlib
import os
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
FLOW_ROOT = os.path.dirname(HERE)
sys.path.insert(0, FLOW_ROOT)
sys.path.insert(0, os.path.join(FLOW_ROOT, "app"))

import flow  # noqa: E402
import server  # noqa: E402
import state as state_mod  # noqa: E402

PORT = 18767
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


def main():
    real_before = md5_of(REAL_POINTER)

    test_root = tempfile.mkdtemp(prefix="nbi_flow_selftest_", dir="/tmp")
    data_root = os.path.join(test_root, "data")
    os.makedirs(data_root)
    state_mod.CURRENT_RUN_POINTER = os.path.join(test_root, "app_runtime", "current_run.json")
    print("测试数据根：%s" % test_root)

    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        run_debug(data_root)
        run_experiment(data_root)
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


# ---------------------------------------------------------------- 调整模式
def run_debug(data_root):
    print("[调整模式]")
    post("/start", {"data_root": data_root, "mode": "debug", "participant_id": "P001"})

    # 第 1 页（普通字符串清单）：渲染应与原来一样，没有警示样式
    post("/jump", {"page_id": "consent"})
    html = get("/page")
    check('<label><input type="checkbox" name="checked" value="0"> 已签字</label>' in html,
          "第 1 页普通清单保持原样输出")
    check('class="warn-item"' not in html, "第 1 页没有警示项")

    # 第 4 页
    post("/jump", {"page_id": "check_signal"})
    html = get("/page")
    check('<div class="warn-title">⚠ 数据录制确认</div>' in html, "第 4 页有警示区块标题“⚠ 数据录制确认”")
    check(html.count('class="warn-item"') == 1, "第 4 页恰好 1 个警示项")
    check('value="4"> ⚠ LabRecorder 已点 Start：确认状态显示正在录制，文件大小在增长' in html,
          "第 4 页警示项是第 5 个勾选框（value=4）且带 ⚠ 文字")
    xdf_debug = state_mod.xdf_filename("P001", "debug")  # 调整模式是 D_sub-P001.xdf
    check("{xdf_name}" not in html and "文件名已设为 %s" % xdf_debug in html,
          "第 4 页 {xdf_name} 仍然正确填入文件名")
    check("big-check" in html, "第 4 页警示项的复选框带 big-check 样式")

    # 第 17 页：三段顺序 + 三项警示 + 普通清单
    post("/jump", {"page_id": "wrapup"})
    html = get("/page")
    i1 = html.find("我们的实验结束了。您现在有没有什么不适？")
    i2 = html.find("停止录制（按顺序，一项一行）")
    i3 = html.find("请您摘下心电记录仪")
    i4 = html.find("已取下 H10")
    check(0 <= i1 < i2 < i3 < i4, "第 17 页顺序：提示语 → 警示区块 → 提示语 → 普通清单")
    check('<div class="warn-title">⚠ 停止录制（按顺序，一项一行）</div>' in html,
          "第 17 页警示区块标题只出现一次且带 ⚠")
    check(html.count('class="warn-item"') == 3, "第 17 页恰好 3 个警示项")
    for line in ("⚠ 1. LabRecorder 已点击 End，停止录制",
                 "⚠ 2. PolarBridge 已按 ESC 停止",
                 "⚠ 3. SensorBridge 已点击“录制结束”"):
        check(line in html, "第 17 页警示项：" + line)
    check(html.count('name="checked"') == 7, "第 17 页共 7 个勾选框（3 警示 + 4 普通）")
    for old in ("已在 SensorBridge 打“录制结束”标记", "LabRecorder、SensorBridge 已停止"):
        check(old not in html, "第 17 页已删除旧项：" + old)
    for expect in ("已取下 H10", "书写稿已交由被试处理（自行带走或密封回收）",
                   "已支付报酬并签字", "H10 已清洁"):
        check(expect in html, "第 17 页普通清单含：" + expect)

    # 第 18 页：结束页顶部警示块 + 大按钮
    post("/jump", {"page_id": "end"})
    html = get("/page")
    w = html.find("⚠ 最后一步：务必点击下方「结束本场，返回设置页」按钮")
    line2 = html.find("不点击，这场实验不会被标记为结束，下一位被试开始时会出现续接提示。")
    done = html.find("本场流程已跑完")
    check(0 <= w < done and 0 <= line2 < done, "第 18 页警示块在“本场流程已跑完”之上，且两行都在")
    check('class="end-finish-btn"' in html, "第 18 页结束按钮带 end-finish-btn 大按钮样式")


# ---------------------------------------------------------------- 实验模式
def run_experiment(data_root):
    print("[实验模式]")
    pid = "P002"
    post("/start", {"data_root": data_root, "mode": "experiment", "participant_id": pid})
    check(os.path.exists(state_mod.CURRENT_RUN_POINTER)
          and state_mod.CURRENT_RUN_POINTER.startswith(data_root[: data_root.rfind(os.sep)]),
          "运行指针写在测试目录里")

    def set_page(page_id):
        st = state_mod.get_current_run_state()
        st["current_page"] = page_id
        st["page_started_at"] = time.time()
        state_mod.save_state(st)

    def current_page():
        return state_mod.get_current_run_state()["current_page"]

    # 第 4 页：不勾警示项 → 不能推进
    set_page("check_signal")
    html = get("/page")
    check("getElementById(\"complete-btn\")" in html or "complete-btn" in html,
          "第 4 页实验模式下有完成按钮的门控脚本")
    post("/complete", {"checked": ["0", "1", "2", "3"], "notes": ""})
    check(current_page() == "check_signal", "第 4 页：只勾普通项、不勾警示项 → 无法推进")

    # 勾完 5 项 → 推进到第 5 页（q_t0）
    post("/complete", {"checked": ["0", "1", "2", "3", "4"], "notes": ""})
    check(current_page() == "q_t0", "第 4 页：全部勾完（含警示项）→ 推进到 q_t0")

    st = state_mod.load_state(data_root, pid, "experiment")
    recorded = st["pages"]["check_signal"]["checklist_checked"]
    expected_name = state_mod.xdf_filename(pid, "experiment")
    check(recorded == [
        "PolarBridge 已打开",
        "SensorBridge 已连接 H10 并开始录制",
        "LabRecorder 文件名已设为 %s（不含 session/分组，BIDS 已关闭）" % expected_name,
        "心率数据连续、数值合理",
        "LabRecorder 已点 Start：确认状态显示正在录制，文件大小在增长",
    ], "state.json 记录的已勾项文字正确（警示项记纯文字，不带 ⚠）")

    # 第 17 页：警示项 + 普通清单都要勾完
    set_page("wrapup")
    post("/complete", {"checked": ["0", "1", "2", "3", "4", "5"], "notes": ""})
    check(current_page() == "wrapup", "第 17 页：三项警示有一项没勾（漏了第 3 项）→ 无法推进")
    post("/complete", {"checked": ["0", "1", "3", "4", "5", "6"], "notes": ""})
    check(current_page() == "wrapup", "第 17 页：漏了第 2 项警示 → 无法推进")
    post("/complete", {"checked": [str(i) for i in range(7)], "notes": ""})
    check(current_page() == "end", "第 17 页：三项警示和普通清单全部勾完 → 推进到结束页")


if __name__ == "__main__":
    main()
