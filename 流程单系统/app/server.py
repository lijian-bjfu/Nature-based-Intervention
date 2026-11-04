"""本机 HTTP 服务：路由、表单处理、页面流转。只用标准库，不依赖第三方包。"""
import os
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
import render
import state as state_mod


def _default_durations():
    return {
        "practice": config.PRACTICE_DURATION_SEC,
        "rest": config.REST_DURATION_SEC,
        "writing": config.WRITING_DURATION_SEC,
        "writing_midpoint": config.WRITING_MIDPOINT_SEC,
        "post_writing_rest": config.POST_WRITING_REST_DURATION_SEC,
        "intervention": config.INTERVENTION_DURATION_SEC,
        "post_intervention_rest": config.POST_INTERVENTION_REST_DURATION_SEC,
    }


def _default_data_root():
    return os.path.join(state_mod.PROJECT_ROOT, config.DEFAULT_DATA_ROOT)


# 开机/软件重启后第一次用、还没确认过设备准备工作时为 False；确认一次（点"准备检查"
# 页的按钮）后，这次服务进程运行期间都不用再确认——每个被试都弹一遍太烦，但每天/
# 每次重开软件至少确认一次。只在内存里，不落盘，重启服务又会回到 False。
_PREP_CONFIRMED = {"value": False}


def _get_or_init_qstate(st, instrument_id):
    qstate = st["questionnaires"].get(instrument_id)
    if qstate is None:
        qstate = {
            "answers": {}, "current_subpage": 0, "submitted": False,
            "started_at": time.time(), "submitted_at": None,
        }
        st["questionnaires"][instrument_id] = qstate
        state_mod.save_state(st)
    return qstate


def _render_current_page(st):
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

        resume_info = None
        if st is not None:
            page_id = st["current_page"]
            page_def = flow.PAGES.get(page_id, {})
            page_label = "结束页" if page_id == "end" else "第 %s 页 · %s" % (
                page_def.get("number"), page_def.get("title", page_id),
            )
            resume_info = {"participant_id": st["participant_id"], "page_label": page_label}
        data_root = _default_data_root()
        html_text = render.render_settings_page(
            data_root, state_mod.next_suggested_id(data_root), _default_durations(),
            resume_info=resume_info,
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
        path = self.path.split("?", 1)[0]
        form = self._read_form()
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
        elif path == "/group_random":
            self._handle_group_random()
        elif path == "/group_manual":
            self._handle_group_manual(form)
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
            "post_writing_rest": minutes("post_writing_rest_min", defaults["post_writing_rest"]),
            "intervention": minutes("intervention_min", defaults["intervention"]),
            "post_intervention_rest": minutes("post_intervention_rest_min", defaults["post_intervention_rest"]),
        }

        error = None
        if not participant_id:
            error = "被试编号不能为空。"
        elif any(v is None for v in durations_sec.values()):
            error = "时长必须是数字。"
        elif state_mod.participant_exists(data_root, participant_id):
            error = "被试编号 %s 已存在，不能开始（防止覆盖数据）。" % participant_id

        if error:
            html_text = render.render_settings_page(data_root, participant_id, defaults, error=error)
            self._send_html(html_text)
            return

        state_mod.create_participant(data_root, participant_id, durations_sec)
        self._redirect("/page")

    def _handle_verdict(self, form):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        verdict = self._one(form, "verdict")
        if verdict in flow.VERDICT_OPTIONS:
            st["verdict"] = verdict
            state_mod.save_state(st)
        self._redirect("/page")

    def _handle_verdict_reset(self):
        st = state_mod.get_current_run_state()
        if st is not None:
            st["verdict"] = None
            state_mod.save_state(st)
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
            checklist_items = flow.VERDICT_OPTIONS[verdict]["checklist"]
            next_page = flow.VERDICT_OPTIONS[verdict]["next"]
        elif page_def["kind"] == "group":
            if not st.get("group"):
                self._redirect("/page")
                return
            checklist_items = page_def.get("checklist", [])
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
            checklist_items = page_def.get("checklist", [])
            if page_id == "check_signal":
                checklist_items = [item.format(participant_id=st["participant_id"]) for item in checklist_items]
            next_page = flow.NEXT_PAGE.get(page_id)

        checked_indices = {int(v) for v in form.get("checked", [])}
        checked_labels = [item for i, item in enumerate(checklist_items) if i in checked_indices]
        unchecked_labels = [item for i, item in enumerate(checklist_items) if i not in checked_indices]

        # 清单没勾完不能推进（页面上按钮本来就是灰的点不了，这里是防止绕过前端再兜底一次）。
        if unchecked_labels:
            self._redirect("/page")
            return

        notes_text = self._one(form, "notes").strip()

        now = time.time()
        st["pages"][page_id] = {
            "started_at": st["page_started_at"],
            "completed_at": now,
            "checklist_checked": checked_labels,
            "notes": notes_text,
        }
        st["history"].append(next_page)
        st["current_page"] = next_page
        st["page_started_at"] = now
        state_mod.save_state(st)
        if next_page == "end":
            # 进入结束页前自动重新生成两张汇总表（问卷总表、实验记录表），
            # 不需要实验员另外点导出按钮。
            export.export_all(st["data_root"])
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
        state_mod.save_state(st)

        direction = self._one(form, "direction", "next")
        if direction == "prev":
            if page_index > 0:
                qstate["current_subpage"] = page_index - 1
                state_mod.save_state(st)
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
        state_mod.save_state(st)
        self._redirect("/page")

    def _handle_group_random(self):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        if st["current_page"] != "reveal_group" or config.MODE == "pilot" or st.get("group"):
            self._redirect("/page")
            return
        code, condition = judging.draw_random_group()
        st["group"] = condition
        st["group_code"] = code
        st["group_method"] = "random"
        state_mod.save_state(st)
        self._redirect("/page")

    def _handle_group_manual(self, form):
        st = state_mod.get_current_run_state()
        if st is None:
            self._redirect("/")
            return
        condition = self._one(form, "condition")
        if st["current_page"] != "reveal_group" or config.MODE != "pilot" or st.get("group") \
                or condition not in flow.GROUP_INSTRUCTIONS:
            self._redirect("/page")
            return
        st["group"] = condition
        st["group_code"] = None
        st["group_method"] = "manual"
        state_mod.save_state(st)
        self._redirect("/page")

    def _handle_group_reset(self):
        st = state_mod.get_current_run_state()
        if st is not None and st["current_page"] == "reveal_group":
            st["group"] = None
            st["group_code"] = None
            st["group_method"] = None
            state_mod.save_state(st)
        self._redirect("/page")

    def _handle_back(self):
        st = state_mod.get_current_run_state()
        if st is not None and config.MODE == "test" and len(st["history"]) > 1:
            st["history"].pop()
            st["current_page"] = st["history"][-1]
            st["page_started_at"] = time.time()
            state_mod.save_state(st)
        self._redirect("/page")

    def _handle_finish(self):
        st = state_mod.get_current_run_state()
        if st is not None:
            st["ended"] = True
            state_mod.save_state(st)
            state_mod.clear_current_run()
        self._redirect("/")


def run_server():
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    url = "http://%s:%s" % (config.HOST, config.PORT)
    print("流程单系统已启动（运行模式：%s），在浏览器打开 %s" % (config.MODE, url))
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
