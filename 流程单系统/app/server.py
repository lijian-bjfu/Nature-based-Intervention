"""本机 HTTP 服务：路由、表单处理、页面流转。只用标准库，不依赖第三方包。"""
import os
import re
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
import export
import flow
import judging
import questionnaire
import randomization
import render
import state as state_mod


def _default_durations():
    return {
        "practice": config.PRACTICE_DURATION_SEC,
        "rest": config.REST_DURATION_SEC,
        "writing": config.WRITING_DURATION_SEC,
        "writing_midpoint": config.WRITING_MIDPOINT_SEC,
        "intervention": config.INTERVENTION_DURATION_SEC,
        "post_intervention_rest": config.POST_INTERVENTION_REST_DURATION_SEC,
    }


def _default_data_root():
    return state_mod.default_data_root()


DATA_ROOT_MISSING_MSG = "找不到项目 data 文件夹，请手动填写路径"


# 开机/软件重启后第一次用、还没确认过设备准备工作时为 False；确认一次（点"准备检查"
# 页的按钮）后，这次服务进程运行期间都不用再确认——每个被试都弹一遍太烦，但每天/
# 每次重开软件至少确认一次。只在内存里，不落盘，重启服务又会回到 False。
_PREP_CONFIRMED = {"value": False}

# 自动保存请求和翻页/提交请求会同时到达（服务是多线程的），而每个请求都是"读 state.json → 改 → 写回"，
# 不加锁会互相覆盖。所有请求串行处理。
_STATE_LOCK = threading.RLock()


def _get_or_init_qstate(st, instrument_id):
    qstate = st["questionnaires"].get(instrument_id)
    if qstate is None:
        qstate = {
            "answers": {}, "current_subpage": 0, "submitted": False,
            "started_at": time.time(), "submitted_at": None,
        }
        st["questionnaires"][instrument_id] = qstate
        export.save_all(st)
    return qstate


def _sync_t3_record(st):
    """T3 在流程里拆成 T3a、T3b 两份问卷，各自记在 questionnaires["T3a"] / ["T3b"] 里。
    这里另外维护一份合并的 questionnaires["T3"]（答案合并，两份都提交后才算已提交，
    起止时间取 T3a 开始、T3b 提交），因为下游分析工具 psycho_check.py 按 T3 这个名字
    去读 state.json 里的问卷记录。"""
    qs = st["questionnaires"]
    parts = [qs.get("T3a"), qs.get("T3b")]
    answers = {}
    for part in parts:
        if part:
            answers.update(part["answers"])
    both_done = all(part and part["submitted"] for part in parts)
    first = parts[0] or parts[1]
    qs["T3"] = {
        "answers": answers,
        "current_subpage": 0,
        "submitted": both_done,
        "started_at": first["started_at"] if first else None,
        "submitted_at": parts[1]["submitted_at"] if both_done else None,
    }


def _lock_randomization(st):
    """实验模式下 T0 最终提交的那一刻（调用方已持有 _STATE_LOCK）：算 STAI-T 总分、分层、取号，
    写入 st["randomization"]。已有记录的不再取号；调整模式不取号；取号失败不写入（只打印），
    第 11 页会显示原因。调用方随后统一保存。"""
    if st.get("mode") != "experiment" or st.get("randomization"):
        return
    total = judging.stait_total_score(st["questionnaires"]["T0"]["answers"])
    if total is None:
        print("[警告] 随机分组：%s 的 STAI-T 未答全，未取号。" % st["participant_id"])
        return
    stratum = randomization.stratum_of(total)
    try:
        position, condition = randomization.assign_for(
            stratum, randomization.used_positions(st["data_root"], stratum), randomization.build_sequences())
    except randomization.RandomizationError as e:
        print("[错误] 随机分组取号失败（%s）：%s" % (st["participant_id"], e))
        return
    st["randomization"] = {
        "stait_total": total, "stratum": stratum, "position": position, "condition": condition,
        "assigned_at": time.time(),
    }


def _render_current_page(st):
    """渲染当前页；调整模式下统一给每个页面（含问卷页、空白页、结束页）加红色标识和跳页菜单。"""
    return render.with_debug_bar(_render_page_body(st), st)


def _render_page_body(st):
    page_id = st["current_page"]
    if page_id == "end":
        return render.render_end_page(st)
    page_def = flow.PAGES[page_id]
    kind = page_def["kind"]
    if kind == "task":
        return render.render_task_page(st, page_id, page_def)
    if kind == "placeholder":
        return render.render_placeholder_page(st, page_id, page_def)
    if kind == "verdict":
        return render.render_verdict_page(st, page_def)
    if kind == "group":
        return render.render_group_page(st)
    if kind == "questionnaire":
        qstate = _get_or_init_qstate(st, page_def["instrument"])
        if qstate["submitted"]:
            return questionnaire.render_blank_page()
        return questionnaire.render_questionnaire_page(
            page_def["instrument"], qstate["current_subpage"], qstate["answers"],
        )
    raise ValueError("未知的页面类型：%s" % kind)


class Handler(BaseHTTPRequestHandler):
    server_version = "NBIFlow/0.1"

    def log_message(self, fmt, *args):
        pass  # 静默默认访问日志；调试时可以注释掉这一行看每个请求

    # ---------- 基础工具 ----------
    def _send_html(self, html_text, status=200):
        encoded = html_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _no_content(self):
        self.send_response(204)
        self.end_headers()

    def _redirect(self, path):
        self.send_response(303)
        self.send_header("Location", path)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_form(self):
        """返回 {字段名: [值, ...]}，同名字段（比如多个勾选框）全部保留。"""
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return urllib.parse.parse_qs(raw, keep_blank_values=True)

    @staticmethod
    def _one(form, key, default=""):
        values = form.get(key)
        return values[0] if values else default

    # ---------- GET ----------
    def do_GET(self):
        with _STATE_LOCK:
            self._do_get()

    def _do_get(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._handle_index()
        elif path == "/page":
            self._handle_page()
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self._send_html(render.shell("未找到", "<p>404</p>"), status=404)

    def _handle_index(self):
        # 新开网页/输入地址一律先看到设置页，不自动跳回上次没做完的被试——
        # 真要接着做，设置页上会有一个"继续"按钮，点了才去 /page（那边本来就会按
        # 当前进行中的被试恢复到正确位置），不点就可以直接从头开始填新的被试。
        #
        # 但如果没有正在进行中的被试（要开始新的一个），设备准备工作（热点、关防火墙/
        # VPN、SensorBridge 事件、LabRecorder 设置等）还没确认过，先弹"准备检查"页，
        # 确认过才放行到设置页；已有进行中的被试（明显设备已经在用了）不弹这个。
        st = state_mod.get_current_run_state()
        if st is None and not _PREP_CONFIRMED["value"]:
            self._send_html(render.render_prep_page())
            return

        saved_folder = None
        query = urllib.parse.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        candidate = (query.get("saved") or [""])[0]
        if re.fullmatch(r"(D_)?sub-P\d{3}", candidate):
            saved_folder = candidate
        resume_info = None
        if st is not None:
            page_id = st["current_page"]
            page_def = flow.PAGES.get(page_id, {})
            page_label = "结束页" if page_id == "end" else "第 %s 页 · %s" % (
                page_def.get("number"), page_def.get("title", page_id),
            )
            resume_info = {"participant_id": st["participant_id"], "page_label": page_label}
        data_root = _default_data_root()
        suggested_ids = {m: state_mod.next_suggested_id(data_root, m) for m in config.MODE_SUBDIR}
        html_text = render.render_settings_page(
            data_root, suggested_ids, _default_durations(), resume_info=resume_info,
            data_root_missing=not os.path.isdir(data_root), saved_folder=saved_folder,
        )
        self._send_html(html_text)

    def _handle_prep_confirm(self):
        _PREP_CONFIRMED["value"] = True
        self._redirect("/")

    def _handle_page(self):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        self._send_html(_render_current_page(st))

    # ---------- POST ----------
    def do_POST(self):
        form = self._read_form()
        with _STATE_LOCK:
            self._do_post(form)

    def _do_post(self, form):
        path = self.path.split("?", 1)[0]
        if path == "/prep_confirm":
            self._handle_prep_confirm()
        elif path == "/start":
            self._handle_start(form)
        elif path == "/verdict":
            self._handle_verdict(form)
        elif path == "/verdict_reset":
            self._handle_verdict_reset()
        elif path == "/complete":
            self._handle_complete(form)
        elif path == "/qanswer":
            self._handle_qanswer(form)
        elif path == "/autosave_notes":
            self._handle_autosave_notes(form)
        elif path == "/qautosave":
            self._handle_qautosave(form)
        elif path == "/group_random":
            self._handle_group_random()
        elif path == "/group_set":
            self._handle_group_set(form)
        elif path == "/jump":
            self._handle_jump(form)
        elif path == "/group_reset":
            self._handle_group_reset()
        elif path == "/back":
            self._handle_back()
        elif path == "/finish":
            self._handle_finish()
        else:
            self._send_html(render.shell("未找到", "<p>404</p>"), status=404)

    def _handle_start(self, form):
        data_root = self._one(form, "data_root").strip() or _default_data_root()
        mode = self._one(form, "mode")
        participant_id = self._one(form, "participant_id").strip()
        defaults = _default_durations()

        def minutes(key, default_sec):
            raw = self._one(form, key).strip()
            if not raw:
                return default_sec
            try:
                return float(raw) * 60
            except ValueError:
                return None

        durations_sec = {
            "practice": minutes("practice_min", defaults["practice"]),
            "rest": minutes("rest_min", defaults["rest"]),
            "writing": minutes("writing_min", defaults["writing"]),
            "writing_midpoint": minutes("writing_midpoint_min", defaults["writing_midpoint"]),
            "intervention": minutes("intervention_min", defaults["intervention"]),
            "post_intervention_rest": minutes("post_intervention_rest_min", defaults["post_intervention_rest"]),
        }

        error = None
        if mode not in config.MODE_SUBDIR:
            mode = None
            error = "请先选择运行模式（实验模式 / 调整模式）。"
        elif not os.path.isdir(data_root):
            error = DATA_ROOT_MISSING_MSG
        elif not participant_id:
            error = "被试编号不能为空。"
        elif not state_mod.valid_participant_id(participant_id, mode):
            error = "被试编号格式应为 P 加 3 位数字（例如 P001）。"
        elif any(v is None for v in durations_sec.values()):
            error = "时长必须是数字。"
        elif state_mod.participant_exists(data_root, participant_id, mode):
            error = "被试编号 %s 已存在，不能开始（防止覆盖数据）。" % participant_id

        if error:
            suggested_ids = {m: state_mod.next_suggested_id(data_root, m) for m in config.MODE_SUBDIR}
            html_text = render.render_settings_page(
                data_root, suggested_ids, defaults, error=error,
                selected_mode=mode, participant_id_value=participant_id,
                data_root_missing=not os.path.isdir(data_root),
            )
            self._send_html(html_text)
            return

        st = state_mod.create_participant(data_root, participant_id, durations_sec, mode)
        export.save_all(st)  # 开始就把全套文件（含中断说明.txt）写进 _break_ 文件夹
        self._redirect("/page")

    def _handle_verdict(self, form):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        verdict = self._one(form, "verdict")
        if verdict in flow.VERDICT_OPTIONS:
            st["verdict"] = verdict
            export.save_all(st)
        self._redirect("/page")

    def _handle_verdict_reset(self):
        st = state_mod.get_current_run_state()
        if st is not None:
            st["verdict"] = None
            export.save_all(st)
        self._redirect("/page")

    def _handle_complete(self, form):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        page_id = st["current_page"]
        if page_id == "end":
            self._redirect("/page")
            return
        page_def = flow.PAGES[page_id]

        if page_def["kind"] == "verdict":
            verdict = st.get("verdict")
            if verdict is None:
                self._redirect("/page")
                return
            checklist_items = flow.normalize_list(flow.VERDICT_OPTIONS[verdict]["checklist"])
            next_page = flow.VERDICT_OPTIONS[verdict]["next"]
        elif page_def["kind"] == "group":
            if not st.get("group"):
                self._redirect("/page")
                return
            checklist_items = flow.flat_checklist(page_def)
            next_page = flow.NEXT_PAGE.get(page_id)
        elif page_def["kind"] == "questionnaire":
            # 这条路径只有空白页上的"进入下一阶段"按钮会走到；问卷没提交完就不能推进。
            qstate = st["questionnaires"].get(page_def["instrument"])
            if not qstate or not qstate["submitted"]:
                self._redirect("/page")
                return
            checklist_items = []
            next_page = flow.NEXT_PAGE.get(page_id)
        else:
            fmt = None
            if page_id == "check_signal":
                fmt = {"xdf_name": state_mod.xdf_filename(st["participant_id"], st["mode"]),
                       "pid": st["participant_id"]}
            checklist_items = flow.flat_checklist(page_def, fmt)
            next_page = flow.NEXT_PAGE.get(page_id)

        # checklist_items 里每项是 flow.normalize_item 的结果；记录的是纯文字（不带 ⚠）。
        checked_indices = {int(v) for v in form.get("checked", [])}
        checked_labels = [item["text"] for i, item in enumerate(checklist_items) if i in checked_indices]
        unchecked_labels = [item["text"] for i, item in enumerate(checklist_items) if i not in checked_indices]

        # 实验模式：清单没勾完不能推进（页面上按钮本来就是灰的点不了，这里是防止绕过前端再兜底
        # 一次）。调整模式不拦，未勾项照常记录（只记 checked 的，未勾的不在 checklist_checked 里）。
        if unchecked_labels and st["mode"] != "debug":
            self._redirect("/page")
            return

        notes_text = self._one(form, "notes").strip()

        now = time.time()
        st.setdefault("drafts", {})[page_id] = notes_text
        st["pages"][page_id] = {
            "started_at": st["page_started_at"],
            "completed_at": now,
            "checklist_checked": checked_labels,
            "notes": notes_text,
        }
        st["history"].append(next_page)
        st["current_page"] = next_page
        st["page_started_at"] = now
        # 保存时同时重新导出问卷表、实验记录表、记录文字和列名对照（任何时刻中断都是最新的）。
        export.save_all(st)
        self._redirect("/page")

    def _handle_qanswer(self, form):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        page_id = st["current_page"]
        page_def = flow.PAGES.get(page_id)
        if not page_def or page_def["kind"] != "questionnaire":
            self._redirect("/page")
            return

        instrument_id = page_def["instrument"]
        qstate = _get_or_init_qstate(st, instrument_id)
        if qstate["submitted"]:
            self._redirect("/page")
            return

        instrument = questionnaire.QUESTIONNAIRES[instrument_id]
        page_index = qstate["current_subpage"]
        page = instrument["pages"][page_index]

        # 不管是翻下一页还是翻回上一页，先把这一页填的内容存下来，不丢数据。
        questionnaire.merge_answers(page, form, qstate["answers"])
        export.save_all(st)

        direction = self._one(form, "direction", "next")
        if direction == "prev":
            if page_index > 0:
                qstate["current_subpage"] = page_index - 1
                export.save_all(st)
            self._redirect("/page")
            return

        # 前端已经挡过"还没答完不能翻页"，这里是防止绕过前端的兜底：没答完就不推进。
        if questionnaire.missing_items(page, qstate["answers"]):
            self._redirect("/page")
            return

        if page_index < len(instrument["pages"]) - 1:
            qstate["current_subpage"] = page_index + 1
        else:
            qstate["submitted"] = True
            qstate["submitted_at"] = time.time()
        if instrument_id in ("T3a", "T3b"):
            _sync_t3_record(st)
        if qstate["submitted"] and instrument_id == "T0":
            _lock_randomization(st)
        export.save_all(st)
        self._redirect("/page")

    def _handle_autosave_notes(self, form):
        """实验记录文字框实时保存：只在 page_id 等于当前页时写入 drafts，不翻页。"""
        st = state_mod.get_current_run_state()
        if st is None or self._one(form, "page_id") != st["current_page"] or st["current_page"] == "end":
            self._no_content()
            return
        st.setdefault("drafts", {})[st["current_page"]] = self._one(form, "notes")
        export.save_all(st)
        self._no_content()

    def _handle_qautosave(self, form):
        """问卷每答一题就保存：把整页表单合并进当前子页的 answers，不翻页、不查漏答、不提交。"""
        st = state_mod.get_current_run_state()
        if st is None:
            self._no_content()
            return
        page_def = flow.PAGES.get(st["current_page"])
        if not page_def or page_def["kind"] != "questionnaire":
            self._no_content()
            return
        instrument_id = page_def["instrument"]
        qstate = _get_or_init_qstate(st, instrument_id)
        page_index = qstate["current_subpage"]
        if qstate["submitted"] or self._one(form, "qsub", str(page_index)) != str(page_index):
            self._no_content()
            return
        page = questionnaire.QUESTIONNAIRES[instrument_id]["pages"][page_index]
        questionnaire.merge_answers(page, form, qstate["answers"])
        if instrument_id in ("T3a", "T3b"):
            _sync_t3_record(st)
        export.save_all(st)
        self._no_content()

    def _handle_group_random(self):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        # 调整模式下随机分配按钮不工作；实验模式分配后不能更改。
        if st["current_page"] != "reveal_group" or st["mode"] != "experiment" or st.get("group"):
            self._redirect("/page")
            return
        rec = st.get("randomization")
        if not rec:  # T0 提交时取号失败（或未取号）：不能揭晓
            self._redirect("/page")
            return
        st["group"] = rec["condition"]
        st["group_code"] = randomization.CONDITION_CODE[rec["condition"]]
        st["group_method"] = "stratified_block"
        export.save_all(st)
        self._redirect("/page")

    def _handle_group_set(self, form):
        """调整模式专用：手动设定组别（1 = 实验组，2 = 对照组），可反复覆盖。"""
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        value = self._one(form, "group_value").strip()
        if st["mode"] != "debug" or st["current_page"] != "reveal_group" or value not in ("1", "2"):
            self._redirect("/page")
            return
        st["group"] = "实验组" if value == "1" else "对照组"
        st["group_code"] = value
        st["group_method"] = "debug_manual"
        export.save_all(st)
        self._redirect("/page")

    def _handle_group_reset(self):
        # 实验模式分配后不能更改；调整模式用"设定组别"覆盖即可。该路由两种模式下都拒绝。
        self._redirect("/page")

    def _handle_jump(self, form):
        """调整模式专用：跳到任意一页。"""
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        target = self._one(form, "page_id")
        if st["mode"] != "debug" or target not in flow.PAGE_ORDER:
            self._redirect("/page")
            return
        st["history"].append(target)
        st["current_page"] = target
        st["page_started_at"] = time.time()
        export.save_all(st)
        self._redirect("/page")

    def _handle_back(self):
        st = state_mod.get_current_run_state()
        if st is not None and st["mode"] == "debug" and len(st["history"]) > 1:
            st["history"].pop()
            st["current_page"] = st["history"][-1]
            st["page_started_at"] = time.time()
            export.save_all(st)
        self._redirect("/page")

    def _handle_finish(self):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        st["ended"] = True
        export.save_all(st)
        # 正常结束：_break_ 文件夹改回正式名，成功后删除中断说明.txt，再按正式名重新保存。
        try:
            export.finalize(st)
        except OSError as e:  # FileExistsError 也是 OSError 的子类
            # 改名失败：数据留在 _break_ 文件夹，保持 ended/broken 并保存（中断说明.txt 保留并更新）。
            st["ended"] = True
            st["broken"] = True
            export.save_all(st)
            state_mod.clear_current_run()
            dr, pid, mode = st["data_root"], st["participant_id"], st["mode"]
            break_dirs = [state_mod.participant_dir(dr, pid, mode, True), state_mod.notes_dir(dr, pid, mode, True)]
            conflict_dirs = [p for p in (state_mod.participant_dir(dr, pid, mode, False),
                                         state_mod.notes_dir(dr, pid, mode, False)) if os.path.exists(p)]
            self._send_html(render.render_finish_error_page(break_dirs, conflict_dirs, str(e)))
            return
        state_mod.clear_current_run()
        folder = state_mod.participant_folder_name(st["participant_id"], st["mode"], False)
        self._redirect("/?saved=" + urllib.parse.quote(folder))


def run_server():
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    url = "http://%s:%s" % (config.HOST, config.PORT)
    print("流程单系统已启动，在浏览器打开 %s（运行模式在设置页选择）" % url)
    print("按 Ctrl+C 停止。")
    # 打包成可执行程序后双击就能用：自动开浏览器，不用自己去记网址、手动输入。
    # 放另一个线程延迟 0.5 秒再开，让 serve_forever() 先把端口监听起来，避免打开的
    # 页面抢在服务就绪之前加载，刷新一下才有内容。
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
