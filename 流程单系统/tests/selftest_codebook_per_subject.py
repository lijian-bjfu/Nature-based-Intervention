"""
自测：问卷 codebook 写进每位被试自己的文件夹，不再生成数据集级的一份；并确认
analysis/tools/psycho_merge.py 能在这种布局上正常合并两位被试。

用法（在"流程单系统"文件夹里）：
    python3 tests/selftest_codebook_per_subject.py

做的事：
  - 在 127.0.0.1:18769 起一个临时服务（不用 config.PORT）；
  - 数据根是一个新建的 /tmp/nbi_codebook_selftest_* 目录，里面建 formal/ 和 pilot_and_test/test/；
    当前运行指针也指向这个目录，不碰真实的 app_runtime/current_run.json；
  - 实验模式快速走完 P001、P002（问卷答案留空，只为检查导出位置）；
  - 检查每位被试文件夹下有 questionnaires.csv、questionnaires_codebook.csv、state.json，
    且 formal/raw/psycho/ 下没有数据集级的 questionnaires_codebook.csv；
  - 调用 analysis/tools/psycho_merge.py 的 run()，只在本脚本内把 paths.DATASETS["formal"]
    的根指向测试目录（analysis/ 下的文件一个字都不改），输出写在测试目录的 processed/ 下。

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
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
FLOW_ROOT = os.path.dirname(HERE)
PROJECT_ROOT = os.path.dirname(FLOW_ROOT)
sys.path.insert(0, FLOW_ROOT)
sys.path.insert(0, os.path.join(FLOW_ROOT, "app"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "analysis", "tools"))

import server  # noqa: E402
import state as state_mod  # noqa: E402

PORT = 18769
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


def run_subject(data_root, pid):
    """实验模式快速走完一位被试：直接跳到第 17 页（wrapup），勾完全部清单，推进到结束页
    （这一步会触发导出），然后取结束页、点结束。问卷答案不填，只为检查导出位置。"""
    post("/start", {"data_root": data_root, "mode": "experiment", "participant_id": pid})

    def set_page(page_id):
        st = state_mod.get_current_run_state()
        st["current_page"] = page_id
        st["page_started_at"] = time.time()
        state_mod.save_state(st)

    set_page("wrapup")
    post("/complete", {"checked": [str(i) for i in range(7)], "notes": "自测备注 " + pid})
    check(state_mod.get_current_run_state()["current_page"] == "end", "%s：推进到结束页" % pid)
    html = get("/page")
    expected = state_mod.questionnaire_codebook_path(data_root, pid, "experiment")
    check(expected in html, "%s：结束页列出的 codebook 路径是新位置" % pid)
    old_path = os.path.join(data_root, "formal", "raw", "psycho", "questionnaires_codebook.csv")
    check(old_path not in html, "%s：结束页不再出现数据集级 codebook 路径" % pid)
    post("/finish", {})


def check_files(data_root, pid):
    folder = os.path.join(data_root, "formal", "raw", "psycho", "sub-" + pid)
    for name in ("questionnaires.csv", "questionnaires_codebook.csv", "state.json"):
        check(os.path.isfile(os.path.join(folder, name)), "%s：sub-%s/%s 存在" % (pid, pid, name))
    with open(os.path.join(folder, "questionnaires_codebook.csv"), "rb") as f:
        head = f.read(3)
    check(head == b"\xef\xbb\xbf", "%s：codebook 为 utf-8-sig（带 BOM）" % pid)


def main():
    real_before = md5_of(REAL_POINTER)

    test_root = tempfile.mkdtemp(prefix="nbi_codebook_selftest_", dir="/tmp")
    data_root = test_root
    os.makedirs(os.path.join(data_root, "formal"))
    os.makedirs(os.path.join(data_root, "pilot_and_test", "test"))
    state_mod.CURRENT_RUN_POINTER = os.path.join(test_root, "app_runtime", "current_run.json")
    print("测试数据根：%s" % test_root)

    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        print("[实验模式] P001")
        run_subject(data_root, "P001")
        print("[实验模式] P002")
        run_subject(data_root, "P002")
    finally:
        httpd.shutdown()

    print("[文件位置]")
    check_files(data_root, "P001")
    check_files(data_root, "P002")
    dataset_codebook = os.path.join(data_root, "formal", "raw", "psycho", "questionnaires_codebook.csv")
    check(not os.path.exists(dataset_codebook), "formal/raw/psycho/ 下没有数据集级 questionnaires_codebook.csv")

    print("[psycho_merge.run()]")
    import paths  # noqa: E402  (analysis/tools/paths.py)
    import psycho_merge  # noqa: E402

    # 只在本进程内改 paths 的数据根，指向测试目录；analysis/ 下的文件不改。
    paths.DATASETS["formal"]["root"] = Path(data_root) / "formal"
    try:
        wide_rows, long_rows, _report = psycho_merge.run("formal", ["P001", "P002"])
        check(len(wide_rows) == 2, "合并了两位被试（宽表 2 行）")
        check(len(long_rows) > 0, "长表有数据行")
        check({r["subject"] for r in wide_rows} == {"P001", "P002"}, "宽表被试编号为 P001、P002")
    except Exception as e:  # 记录失败原因，便于汇报
        check(False, "psycho_merge.run() 报错：%s: %s" % (type(e).__name__, e))

    processed = os.path.join(data_root, "formal", "processed", "psycho")
    for name in ("items_wide.csv", "items_long.csv", "items_codebook.csv", "items_report.txt"):
        check(os.path.isfile(os.path.join(processed, name)), "输出存在：processed/psycho/" + name)

    real_after = md5_of(REAL_POINTER)
    check(real_before == real_after, "真实的 app_runtime/current_run.json 未被改动")
    print("测试数据根保留在：%s" % test_root)
    print()
    if FAILS:
        print("共 %d 项失败：" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        sys.exit(1)
    print("全部通过。")


if __name__ == "__main__":
    main()
