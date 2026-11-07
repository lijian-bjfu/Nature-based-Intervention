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


def default_data_root():
    """项目数据根目录（含 formal/、pilot_and_test/ 的 data/ 文件夹）的默认位置：流程单系统所在
    文件夹的上一级目录下的 data/。源码运行时是 <项目根>/data；打包运行时按 _app_root() 的上一级推算。"""
    return os.path.join(os.path.dirname(PROJECT_ROOT), config.DEFAULT_DATA_ROOT)


def physio_data_dir(mode, data_root=None):
    """LabRecorder 应该存生理数据（.xdf）的目录：<data 根>/<dataset>/raw/physio。只用来在"准备检查"
    页显示给实验员照着填，流程单系统自己不写这里的文件，也不保证目录已存在
    （LabRecorder 保存文件时会自动建目录）。"""
    root = data_root or default_data_root()
    return os.path.join(root, *config.PHYSIO_DATA_SUBDIR[mode].split("/"))


def xdf_filename(participant_id, mode):
    """该场 LabRecorder 文件名（含子文件夹），例如 sub-P001/sub-P001.xdf / D_sub-P001/D_sub-P001.xdf。
    与 config.LABRECORDER_FILENAME_TEMPLATE 一致（%p 换成被试编号）。"""
    folder = config.PARTICIPANT_DIR_TEMPLATE[mode].format(id=participant_id)
    return folder + "/" + folder + ".xdf"


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


def dataset_dir(data_root, mode):
    """给定数据根目录和运行模式，返回该模式对应的数据集目录（formal / pilot_and_test/test）。"""
    return os.path.join(data_root, *config.MODE_SUBDIR[mode].split("/"))


def participant_folder_name(participant_id, mode, broken=False):
    """被试文件夹名。broken=True 时加 BREAK_PREFIX，表示本场还没正常结束（进行中/中断）。"""
    name = config.PARTICIPANT_DIR_TEMPLATE[mode].format(id=participant_id)
    return (config.BREAK_PREFIX + name) if broken else name


def psycho_root(data_root, mode):
    return os.path.join(dataset_dir(data_root, mode), "raw", "psycho")


def notes_root(data_root, mode):
    return os.path.join(dataset_dir(data_root, mode), "raw", "session_notes")


def participant_dir(data_root, participant_id, mode, broken=False):
    """该被试的问卷/状态目录（raw/psycho/<文件夹名>/），state.json 在这里。"""
    return os.path.join(psycho_root(data_root, mode), participant_folder_name(participant_id, mode, broken))


def notes_dir(data_root, participant_id, mode, broken=False):
    """该被试的实验记录目录（raw/session_notes/<文件夹名>/）。"""
    return os.path.join(notes_root(data_root, mode), participant_folder_name(participant_id, mode, broken))


def state_path(data_root, participant_id, mode, broken=False):
    return os.path.join(participant_dir(data_root, participant_id, mode, broken), "state.json")


INTERRUPT_NOTE_NAME = "中断说明.txt"


def interrupt_note_paths(data_root, participant_id, mode, broken=True):
    """中断说明.txt 的两处路径：psycho 与 session_notes 各一份。默认在 _break_ 文件夹里；
    broken=False 是改名后正式文件夹里的位置（正常结束时用来删除）。"""
    return [os.path.join(participant_dir(data_root, participant_id, mode, broken), INTERRUPT_NOTE_NAME),
            os.path.join(notes_dir(data_root, participant_id, mode, broken), INTERRUPT_NOTE_NAME)]


def questionnaire_csv_path(data_root, participant_id, mode, broken=False):
    """该被试的问卷表（1 行，A、T0-T3 全部问卷）。"""
    return os.path.join(participant_dir(data_root, participant_id, mode, broken), "questionnaires.csv")


def questionnaire_codebook_path(data_root, participant_id, mode, broken=False):
    """该被试的问卷列名对照（与 questionnaires.csv 同一文件夹），导出那一刻的快照。"""
    return os.path.join(participant_dir(data_root, participant_id, mode, broken), "questionnaires_codebook.csv")


def log_csv_path(data_root, participant_id, mode, broken=False):
    """该被试的实验记录表（1 行：判定、分组、各页起止时间等）。"""
    return os.path.join(notes_dir(data_root, participant_id, mode, broken), "log.csv")


def notes_txt_path(data_root, participant_id, mode, broken=False):
    """该被试实验记录文字（按页列出，没写的页跳过）。"""
    return os.path.join(notes_dir(data_root, participant_id, mode, broken), "notes.txt")


def list_used_numbers(data_root, mode):
    """扫描该模式数据集 raw/psycho/ 和 raw/session_notes/ 下符合本模式文件夹名格式的文件夹，
    返回已用的数字部分（排序、去重）。带 _break_ 前缀的（进行中/中断）也算已用。"""
    prefix = config.PARTICIPANT_PREFIX[mode]
    name_re = re.escape(config.PARTICIPANT_DIR_TEMPLATE[mode]).replace(
        re.escape("{id}"), re.escape(prefix) + r"(\d{%d})" % config.PARTICIPANT_ID_DIGITS)
    # 进行中/中断的 _break_ 文件夹也占着编号，防止被重复使用。
    pattern = re.compile("^(?:" + re.escape(config.BREAK_PREFIX) + ")?" + name_re + "$")
    numbers = set()
    for root in (psycho_root(data_root, mode), notes_root(data_root, mode)):
        if not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            m = pattern.match(name)
            if m and os.path.isdir(os.path.join(root, name)):
                numbers.add(int(m.group(1)))
    return sorted(numbers)


def next_suggested_id(data_root, mode):
    prefix = config.PARTICIPANT_PREFIX[mode]
    used = list_used_numbers(data_root, mode)
    next_n = (used[-1] + 1) if used else 1
    return "%s%0*d" % (prefix, config.PARTICIPANT_ID_DIGITS, next_n)


def valid_participant_id(participant_id, mode):
    pattern = r"^%s\d{%d}$" % (re.escape(config.PARTICIPANT_PREFIX[mode]), config.PARTICIPANT_ID_DIGITS)
    return re.match(pattern, participant_id) is not None


def participant_exists(data_root, participant_id, mode):
    """正式名或 _break_ 名的文件夹只要有一个存在，就视为该编号已用。"""
    return any(os.path.isdir(f(data_root, participant_id, mode, b))
               for f in (participant_dir, notes_dir) for b in (False, True))


def create_participant(data_root, participant_id, durations_sec, mode):
    """新开一场实验：建目录、写初始 state.json、把它记成"当前进行中的会话"。
    mode 为 "experiment" 或 "debug"，写进 state["mode"]。"""
    if mode not in config.MODE_SUBDIR:
        raise ValueError("未知的运行模式：%r" % (mode,))
    pdir = participant_dir(data_root, participant_id, mode, True)
    if participant_exists(data_root, participant_id, mode):
        raise FileExistsError("被试编号 %s 已存在，禁止覆盖" % participant_id)
    os.makedirs(pdir, exist_ok=True)
    now = time.time()
    state = {
        "participant_id": participant_id,
        "mode": mode,
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
        "randomization": None,  # 实验模式 T0 提交时写入 {stait_total, stratum, position, condition, assigned_at}
        "ended": False,
        "end_reason": None,
        "broken": True,   # True = 文件夹名带 _break_（本场未正常结束）；正常结束时改回 False
        "drafts": {},     # {page_id: 实验记录草稿文字}，实时保存
    }
    save_state(state)
    set_current_run(data_root, participant_id, mode)
    return state


def load_state(data_root, participant_id, mode):
    """先找 _break_ 名的文件夹，找不到再找正式名（旧版数据）；据此设置 state["broken"]。"""
    for broken in (True, False):
        path = state_path(data_root, participant_id, mode, broken)
        if os.path.exists(path):
            st = _read_json(path)
            st["broken"] = broken
            st.setdefault("drafts", {})
            return st
    raise FileNotFoundError("找不到被试 %s 的 state.json" % participant_id)


def save_state(state):
    """只写 state.json。各处修改状态后请调用 export.save_all()（它会调用本函数，并同步导出文件和中断说明）。"""
    path = state_path(state["data_root"], state["participant_id"], state["mode"], state.get("broken", False))
    _atomic_write_json(path, state)


def rename_to_final(state):
    """正常结束：把 _break_ 文件夹改回正式名（psycho 与 session_notes 两处）。
    目标已存在则抛 FileExistsError，不覆盖。只改名，不删数据。"""
    if not state.get("broken"):
        return
    dr, pid, mode = state["data_root"], state["participant_id"], state["mode"]
    pairs = []
    for f in (participant_dir, notes_dir):
        src, dst = f(dr, pid, mode, True), f(dr, pid, mode, False)
        if os.path.isdir(src):
            if os.path.exists(dst):
                raise FileExistsError("正式文件夹已存在，不能改名：%s" % dst)
            pairs.append((src, dst))
    done = []
    try:
        for src, dst in pairs:
            os.rename(src, dst)
            done.append((src, dst))
    except OSError:
        for src, dst in reversed(done):  # 改到一半失败：把已改名的改回去，保持 _break_ 状态
            try:
                os.rename(dst, src)
            except OSError:
                pass
        raise
    state["broken"] = False


def set_current_run(data_root, participant_id, mode):
    _atomic_write_json(CURRENT_RUN_POINTER, {
        "data_root": data_root,
        "participant_id": participant_id,
        "mode": mode,
    })


def clear_current_run():
    """本场结束后让指针失效。不删文件，改写成空记录（读取时没有 mode 字段，视为无进行中的场次）。"""
    if os.path.exists(CURRENT_RUN_POINTER):
        _atomic_write_json(CURRENT_RUN_POINTER, {})


def get_current_run_state():
    """程序启动或刷新首页时调用：如果有一场尚未结束的实验，恢复它的状态。"""
    if not os.path.exists(CURRENT_RUN_POINTER):
        return None
    try:
        pointer = _read_json(CURRENT_RUN_POINTER)
    except (json.JSONDecodeError, OSError):
        return None
    mode = pointer.get("mode")
    if mode not in config.MODE_SUBDIR:
        # 空指针（上一场已结束）或旧版本留下的指针，无法续接。
        return None
    try:
        state = load_state(pointer["data_root"], pointer["participant_id"], mode)
    except (OSError, ValueError, KeyError):
        return None
    if state.get("ended"):
        return None
    return state
