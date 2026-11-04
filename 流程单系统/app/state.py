"""
被试状态的读写：编号分配、原子落盘、当前进行中会话的记录与恢复。

设计原则（对应交接文档第二节"两种状态"）：所有"提示"都是从 state.json 里的
记录现算出来的，state.json 本身只保存"记录状态"的事实（谁、第几页、勾了什么、
写了什么）。只要 state.json 没写坏，程序随时重启都能从里面推出正确的提示。
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _app_root():
    """数据、崩溃恢复指针存放的稳定目录。

    正常用 python3 run.py 跑的时候，就是项目根目录（流程单系统/）。打包成单文件可
    执行程序后，__file__ 指向的是运行时解压出来的临时目录，每次启动都不一样，不能
    用来存数据——这时改用可执行文件自身所在的目录（sys.executable），双击运行时这
    个目录是稳定不变的。Mac 下打包成 .app 时，sys.executable 在 .app 包内部
    （…/XXX.app/Contents/MacOS/XXX），数据改存在 .app 旁边，不存进 .app 包里面。
    """
    if not getattr(sys, "frozen", False):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    marker = os.sep + "Contents" + os.sep + "MacOS"
    if marker in exe_dir:
        # exe_dir 形如 .../流程单系统.app/Contents/MacOS，退到 .app 包所在的目录。
        app_bundle_dir = exe_dir.split(marker)[0]
        return os.path.dirname(app_bundle_dir)
    return exe_dir


PROJECT_ROOT = _app_root()
RUNTIME_DIR = os.path.join(PROJECT_ROOT, "app_runtime")
CURRENT_RUN_POINTER = os.path.join(RUNTIME_DIR, "current_run.json")


def physio_data_dir():
    """LabRecorder 应该存生理数据（.xdf）的目录：项目根目录（流程单系统/ 的上一级）下的
    data/<dataset>/raw/physio/，dataset 跟当前 config.MODE 对应。只用来在"准备检查"页
    显示给实验员照着填，流程单系统自己不写这里的文件，也不保证这个目录已经存在
    （LabRecorder 保存文件时会自动建目录）。"""
    repo_root = os.path.dirname(PROJECT_ROOT)
    return os.path.join(repo_root, "data", *config.PHYSIO_DATA_SUBDIR[config.MODE].split("/"))


def _atomic_write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def mode_root(data_root):
    """给定数据根目录，返回当前运行模式（config.MODE）对应的子目录。"""
    return os.path.join(data_root, config.MODE_SUBDIR[config.MODE])


def participant_dir(data_root, participant_id):
    return os.path.join(mode_root(data_root), participant_id)


def state_path(data_root, participant_id):
    return os.path.join(participant_dir(data_root, participant_id), "state.json")


def questionnaire_csv_path(data_root):
    """问卷总表（A、T0-T3 全部五份问卷）的落盘路径，当前运行模式目录下。"""
    return os.path.join(mode_root(data_root), "questionnaires.csv")


def questionnaire_codebook_path(data_root):
    """问卷总表的列名对照（每列对应哪道题、怎么编码）的落盘路径。"""
    return os.path.join(mode_root(data_root), "questionnaires_codebook.csv")


def log_csv_path(data_root):
    """实验记录表（判定、分组、各页起止时间等）的落盘路径，当前运行模式目录下。"""
    return os.path.join(mode_root(data_root), "log.csv")


def notes_txt_path(data_root, participant_id):
    """该被试实验记录文字（按页列出，没写的页跳过）的落盘路径，在该被试自己的目录下。"""
    return os.path.join(participant_dir(data_root, participant_id), "notes.txt")


def list_used_numbers(data_root):
    """扫描当前模式目录下已存在的编号，返回已用的数字部分（排序）。"""
    prefix = config.PARTICIPANT_PREFIX[config.MODE]
    root = mode_root(data_root)
    if not os.path.isdir(root):
        return []
    pattern = re.compile(r"^%s(\d{%d})$" % (re.escape(prefix), config.PARTICIPANT_ID_DIGITS))
    numbers = []
    for name in os.listdir(root):
        m = pattern.match(name)
        if m:
            numbers.append(int(m.group(1)))
    return sorted(numbers)


def next_suggested_id(data_root):
    prefix = config.PARTICIPANT_PREFIX[config.MODE]
    used = list_used_numbers(data_root)
    next_n = (used[-1] + 1) if used else 1
    return "%s%0*d" % (prefix, config.PARTICIPANT_ID_DIGITS, next_n)


def participant_exists(data_root, participant_id):
    return os.path.isdir(participant_dir(data_root, participant_id))


def create_participant(data_root, participant_id, durations_sec):
    """新开一场实验：建目录、写初始 state.json、把它记成"当前进行中的会话"。"""
    pdir = participant_dir(data_root, participant_id)
    if os.path.isdir(pdir):
        raise FileExistsError("被试编号 %s 已存在，禁止覆盖" % participant_id)
    os.makedirs(pdir, exist_ok=True)
    now = time.time()
    state = {
        "participant_id": participant_id,
        "mode": config.MODE,
        "data_root": data_root,
        "created_at": now,
        "durations_sec": durations_sec,
        "history": ["consent"],
        "current_page": "consent",
        "page_started_at": now,
        "pages": {},
        "questionnaires": {},
        "verdict": None,
        "group": None,
        "group_code": None,
        "group_method": None,
        "ended": False,
        "end_reason": None,
    }
    save_state(state)
    set_current_run(data_root, participant_id)
    return state


def load_state(data_root, participant_id):
    return _read_json(state_path(data_root, participant_id))


def save_state(state):
    path = state_path(state["data_root"], state["participant_id"])
    _atomic_write_json(path, state)


def set_current_run(data_root, participant_id):
    _atomic_write_json(CURRENT_RUN_POINTER, {
        "data_root": data_root,
        "participant_id": participant_id,
        "mode": config.MODE,
    })


def clear_current_run():
    if os.path.exists(CURRENT_RUN_POINTER):
        os.remove(CURRENT_RUN_POINTER)


def get_current_run_state():
    """程序启动或刷新首页时调用：如果有一场尚未结束的实验，恢复它的状态。"""
    if not os.path.exists(CURRENT_RUN_POINTER):
        return None
    try:
        pointer = _read_json(CURRENT_RUN_POINTER)
    except (json.JSONDecodeError, OSError):
        return None
    if pointer.get("mode") != config.MODE:
        # 运行模式和上次记录的不一样（比如改了 config.py），不要跨模式续接。
        return None
    try:
        state = load_state(pointer["data_root"], pointer["participant_id"])
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if state.get("ended"):
        return None
    return state
