"""月食 · 叮咚查价助手 v1.5（精简版 PRD 1.1）。

形态：文件转换器。一个入口（拖入食材文件），一个出口（保存价格结果）。
- 首页只有拖放区；文件导入后自动校验、自动判断登录、自动查询；
- 登录是异常分支：会话有效直接查询，失效才弹出叮咚网页登录；
- 查询中只显示食材名和进度，附「取消」文字按钮；
- 完成后只显示「查价完成」和一个主按钮「下载结果并返回月食」，
  下载后可「打开文件位置」；
- 低频功能全部收进菜单「设置与帮助」；
- 正常成功不生成诊断文件，仅用户主动导出时才生成。

不读取、不保存、不验证具体收货地址；登录与地址由你本人在叮咚网页确认。
只读承诺：不加购物车、不下单、不支付、不领券、不改地址。
开发者模式仅在环境变量 YUESHI_DEV=1 时启用（日常使用不可见）。
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# ---- 路径（程序目录只读；用户数据在数据目录） ----
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    _MEI = Path(getattr(sys, "_MEIPASS", ROOT))
    ASSET_DIR = _MEI / "assets"
    if not ASSET_DIR.exists():
        ASSET_DIR = ROOT / "_internal" / "assets"
    DATA_DIR = (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        / "YueshiDingdongHelper"
    )
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_MEI / "browsers")
else:
    ROOT = Path(__file__).resolve().parent      # src/
    ASSET_DIR = ROOT.parent / "assets"          # 图标在项目根 assets/
    # 运行期数据（登录态/结果/日志）开发态也统一放 %LOCALAPPDATA%，
    # 项目文件夹始终只有源码，不再越用越乱。
    DATA_DIR = (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        / "YueshiDingdongHelper"
    )

OUTPUT_DIR = DATA_DIR / "output"
QUERY_DEFAULT = DATA_DIR / "月食-查价清单.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
RESULT_NAME = "月食-叮咚价格结果.json"

DEV_MODE = os.environ.get("YUESHI_DEV") == "1"

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    _HAS_DND = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    _HAS_DND = False

_state: dict = {"query_file": None, "item_names": []}


def looks_like_query(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(data, dict) and bool(data.get("items")) and bool(data.get("request_id"))


def adopt_query_file(path: Path) -> Path:
    path = Path(path)
    try:
        if path.resolve() != QUERY_DEFAULT.resolve():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, QUERY_DEFAULT)
    except OSError:
        pass
    _state["query_file"] = QUERY_DEFAULT if QUERY_DEFAULT.exists() else path
    return Path(_state["query_file"])


def current_result_file() -> Path:
    return OUTPUT_DIR / RESULT_NAME


def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    # 迁移清理：确认状态一律不持久化（最佳实践 §四），
    # 旧版本若写入过 delivery_confirmed，读取时直接抹掉。
    if isinstance(data, dict) and data.pop("delivery_confirmed", None) is not None:
        save_settings(data)
    return data if isinstance(data, dict) else {}


def save_settings(data: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


from friendly_errors import ERROR_MESSAGES, GENERIC_MESSAGE, friendly_error

# ---- 月食设计语言 ----
CREAM = "#faf9f6"
WHITE = "#ffffff"
INK = "#23201c"
INK_SOFT = "#6b675f"
LINE = "#e6e2d8"
GOLD = "#b98a2f"
GREEN = "#3d7a52"
RED = "#b04040"
VIOLET = "#7a68a6"
VIOLET_DARK = "#685896"
VIOLET_BG = "#f4f1fa"

FONT = "Microsoft YaHei"

STATUS_CN = {
    "success": "成功",
    "search_empty": "没搜到",
    "candidates_filtered": "不符合要求",
    "candidates_unpriced": "无价格",
    "candidates_unavailable": "售罄",
    "no_match": "没找到合适的商品",
    "parse_failed": "页面读取失败",
    "login_required": "未登录",
}

# ---- 导入后自检三状态（方案 §8.1 原文） ----
SELFCHECK_LIST_READY = "✓ 已读取本周查价清单"
SELFCHECK_BROWSER_OK = "✓ 浏览器可以使用"
SELFCHECK_BROWSER_FAIL = "✗ 未找到可用的浏览器"
SELFCHECK_DELIVERY_PENDING = "○ 请在叮咚网页中确认配送区域"


def browser_available() -> bool:
    """最简单的浏览器可用性探测（方案 §8.1）。

    没有独立的"试运行"函数：直接复用 app._system_browser_exe 检查本机
    Chrome/Edge 常见安装路径；打包携带内置浏览器时
    （PLAYWRIGHT_BROWSERS_PATH 指向的 browsers 目录存在）也视为可用。
    真正的启动失败仍由「无法打开浏览器」的友好提示兜底。"""
    try:
        import app as helper_app
        if helper_app._system_browser_exe():
            return True
    except Exception:
        pass
    raw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if raw:
        try:
            bdir = Path(raw)
            return bdir.is_dir() and any(bdir.iterdir())
        except OSError:
            return False
    return False


def _no_window_kwargs() -> dict:
    if sys.platform.startswith("win"):
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


class HelperWindow:
    """界面状态机：idle(拖放区) → wait(导入后自检面板) → querying(进度)
    → done(保存) / error。
    确认原则（最佳实践 v1.0）：确认前绝不自动——文件导入、登录成功、
    回到首页都不触发查价；只有用户点击「开始查询」
    才创建查询任务。确认状态只存内存、只对当前清单有效，绝不持久化。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("月食 · 叮咚查价助手")
        root.geometry("640x480")
        root.minsize(600, 440)
        root.resizable(True, True)
        # round58：窗口记忆上次尺寸（不小于最小尺寸；125%/150% 缩放下仍可见操作按钮）
        try:
            geo = str(load_settings().get("window_geometry", ""))
            if "x" in geo:
                w, h = (int(x) for x in geo.split("x")[:2])
                root.geometry(f"{max(w, 600)}x{max(h, 440)}")
        except (ValueError, TypeError):
            pass
        self._perf = {"app_start_ms": int((time.monotonic() - _T0) * 1000)}
        self._cancel_requested = False
        self._last_diags = None      # 仅在用户导出诊断时落盘
        self._last_collector_counts = (0, 0)  # (实时接口响应, 缓存命中)
        self._last_batch = None
        self._saved_path: Path | None = None
        # 任务级确认状态（最佳实践 §三）：只存内存，只对当前清单有效。
        self._job: dict | None = None
        # 结果保存成功标志：其后发生的浏览器关闭错误不算失败。
        self._results_saved = False

        # 浏览器会话由唯一后台线程持有（playwright 线程亲和），
        # 登录与查价复用同一窗口，不二次打开。
        self._tasks: queue.Queue = queue.Queue()
        self._session = None
        self._logged_in = False
        threading.Thread(target=self._session_worker, daemon=True).start()

        # ---- 菜单：设置与帮助 ----
        menubar = tk.Menu(root)
        settings = tk.Menu(menubar, tearoff=0, font=(FONT, 9))
        settings.add_command(label="重新登录叮咚", command=self.menu_relogin)
        settings.add_command(label="清除本地登录信息",
                             command=self.menu_clear_login)
        settings.add_separator()
        settings.add_command(label="打开结果文件夹", command=self.menu_open_output)
        settings.add_command(label="导出诊断信息",
                             command=self.menu_export_diagnostics)
        settings.add_separator()
        settings.add_command(label="关于与隐私说明", command=self.menu_about)
        if DEV_MODE:
            settings.add_separator()
            settings.add_command(label="开发者模式已启用（YUESHI_DEV）",
                                 state="disabled")
        menubar.add_cascade(label="设置与帮助", menu=settings)
        root.configure(menu=menubar)

        # ---- 顶部 ----
        band = tk.Frame(root, bg=WHITE)
        band.pack(fill="x")
        inner = tk.Frame(band, bg=WHITE)
        inner.pack(pady=(14, 10))
        self._icon_img = None
        icon_path = ASSET_DIR / "icon-64.png"
        if icon_path.exists():
            try:
                self._icon_img = tk.PhotoImage(file=str(icon_path))
                tk.Label(inner, image=self._icon_img, bg=WHITE).pack(
                    side="left", padx=(0, 10))
            except Exception:
                pass
        title_box = tk.Frame(inner, bg=WHITE)
        title_box.pack(side="left")
        tk.Label(title_box, text="月食 · 叮咚查价助手",
                 font=(FONT, 15, "bold"), bg=WHITE, fg=INK).pack(anchor="w")
        tk.Label(title_box,
                 text="只读工具：不加购物车、不下单、不支付",
                 font=(FONT, 8), bg=WHITE, fg=INK_SOFT).pack(anchor="w")
        tk.Frame(root, bg=GOLD, height=2).pack(fill="x")

        # ---- 中央区（状态切换） ----
        self.stage = tk.Frame(root, bg=CREAM)
        self.stage.pack(fill="both", expand=True, padx=18, pady=16)

        # 状态 1：拖放区（空状态，卡片式小区域，整个区域可点）
        self.f_idle = tk.Frame(self.stage, bg=CREAM)
        self.drop = tk.Frame(self.f_idle, bg=VIOLET_BG,
                             highlightbackground=VIOLET, highlightthickness=1,
                             highlightcolor=VIOLET,
                             width=460, height=170)
        self.drop.pack(pady=(26, 0))
        self.drop.pack_propagate(False)
        self.drop_label = tk.Label(
            self.drop,
            text="把月食生成的食材文件拖到这里\n或点击此处选择文件",
            justify="center", bg=VIOLET_BG, fg=INK, font=(FONT, 11),
            cursor="hand2",
        )
        self.drop_label.pack(expand=True, pady=(30, 4))
        tk.Label(self.drop, text="支持 JSON，单个文件",
                 bg=VIOLET_BG, fg=INK_SOFT, font=(FONT, 8)).pack(
            side="bottom", pady=(0, 16))
        self.drop_label.bind("<Button-1>", lambda _e: self.pick_query_file())
        self.drop.bind("<Button-1>", lambda _e: self.pick_query_file())
        if _HAS_DND:
            for widget in (self.drop, self.drop_label):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)

        # 状态 2：查询中（文件卡片 + 进度 + 取消）
        self.f_busy = tk.Frame(self.stage, bg=CREAM)
        self.file_label = tk.Label(self.f_busy, text="", bg=CREAM, fg=INK,
                                   font=(FONT, 11, "bold"), justify="left")
        self.file_label.pack(pady=(20, 4))
        self.items_label = tk.Label(self.f_busy, text="", bg=CREAM,
                                    fg=INK_SOFT, font=(FONT, 9))
        self.items_label.pack()
        self.progress_label = tk.Label(self.f_busy, text="", bg=CREAM,
                                       fg=INK, font=(FONT, 10))
        self.progress_label.pack(pady=(24, 4))
        self.bar = ttk.Progressbar(self.f_busy, orient="horizontal",
                                   mode="determinate", maximum=100,
                                   length=420)
        self.bar.pack()
        tk.Button(self.f_busy, text="取消", command=self.request_cancel,
                  bg=CREAM, fg=INK_SOFT, relief="flat", bd=0,
                  activebackground=CREAM, cursor="hand2",
                  font=(FONT, 9, "underline")).pack(pady=(16, 0))

        # 状态 2.5：导入后自检面板（方案 §8.1）——只显示三个状态 +
        # 唯一主操作「开始查询」。确认前绝不自动查价。
        self.f_wait = tk.Frame(self.stage, bg=CREAM)
        self.wait_file_label = tk.Label(self.f_wait, text="", bg=CREAM,
                                        fg=INK, font=(FONT, 11, "bold"),
                                        justify="center")
        self.wait_file_label.pack(pady=(22, 10))
        check_box = tk.Frame(self.f_wait, bg=CREAM)
        check_box.pack()
        self.check_list_label = tk.Label(
            check_box, text=SELFCHECK_LIST_READY,
            bg=CREAM, fg=GREEN, font=(FONT, 10), anchor="w")
        self.check_list_label.pack(fill="x", pady=1)
        self.check_browser_label = tk.Label(
            check_box, text=SELFCHECK_BROWSER_OK,
            bg=CREAM, fg=GREEN, font=(FONT, 10), anchor="w")
        self.check_browser_label.pack(fill="x", pady=1)
        self.check_delivery_label = tk.Label(
            check_box, text=SELFCHECK_DELIVERY_PENDING,
            bg=CREAM, fg=INK_SOFT, font=(FONT, 10), anchor="w")
        self.check_delivery_label.pack(fill="x", pady=1)
        self.btn_start = tk.Button(
            self.f_wait, text="开始查询",
            command=self.click_start_query,
            bg=VIOLET, fg=WHITE, activebackground=VIOLET_DARK,
            activeforeground=WHITE, relief="flat", bd=0, cursor="hand2",
            font=(FONT, 12, "bold"), width=26, height=2)
        self.btn_start.pack(pady=(22, 6))
        tk.Button(self.f_wait, text="重新选择文件", command=self.back_to_idle,
                  bg=CREAM, fg=INK_SOFT, relief="flat", bd=0, cursor="hand2",
                  font=(FONT, 9, "underline")).pack()
        tk.Label(self.f_wait,
                 text="软件会一直等你确认，不会自动开始查价",
                 bg=CREAM, fg=INK_SOFT, font=(FONT, 8)).pack(
            side="bottom", pady=6)

        # 状态 3：完成（方案 §8.2：只显示「查价完成」+ 唯一主按钮
        # 「下载结果并返回月食」；round58 默认只显示摘要，明细默认收起，
        # 底部操作栏固定不随列表滚动，主按钮始终可见）
        self.f_done = tk.Frame(self.stage, bg=CREAM)
        self.done_title = tk.Label(self.f_done, text="查价完成", bg=CREAM,
                                   fg=GREEN, font=(FONT, 13, "bold"))
        self.done_title.pack(pady=(16, 4))
        self.summary_label = tk.Label(self.f_done, text="", bg=CREAM, fg=INK,
                                      font=(FONT, 10), justify="left")
        self.summary_label.pack()
        self.btn_toggle_detail = tk.Button(
            self.f_done, text="查看全部结果 ▾", command=self._toggle_detail,
            bg=CREAM, fg=INK_SOFT, relief="flat", bd=0, cursor="hand2",
            font=(FONT, 9, "underline"))
        self.btn_toggle_detail.pack(pady=(8, 2))

        # 明细：独立滚动容器（Canvas + Scrollbar），默认收起；
        # 支持鼠标滚轮与 PageUp/PageDown/Home/End
        self._detail_visible = False
        self.detail_wrap = tk.Frame(self.f_done, bg=CREAM)
        self.detail_canvas = tk.Canvas(
            self.detail_wrap, bg=WHITE, highlightthickness=1,
            highlightbackground=LINE)
        self.detail_scroll = ttk.Scrollbar(
            self.detail_wrap, orient="vertical",
            command=self.detail_canvas.yview)
        self.detail_canvas.configure(yscrollcommand=self.detail_scroll.set)
        self.detail_scroll.pack(side="right", fill="y")
        self.detail_canvas.pack(side="left", fill="both", expand=True)
        self.detail_inner = tk.Frame(self.detail_canvas, bg=WHITE)
        self._detail_win = self.detail_canvas.create_window(
            (0, 0), window=self.detail_inner, anchor="nw")
        self.detail_inner.bind("<Configure>", lambda e: self.detail_canvas.configure(
            scrollregion=self.detail_canvas.bbox("all")))
        self.detail_canvas.bind("<Configure>", lambda e: self.detail_canvas.itemconfigure(
            self._detail_win, width=e.width))
        for seq, fn in (("<MouseWheel>", lambda e: self.detail_canvas.yview_scroll(int(-e.delta / 120), "units")),
                        ("<Prior>", lambda e: self.detail_canvas.yview_scroll(-1, "pages")),
                        ("<Next>", lambda e: self.detail_canvas.yview_scroll(1, "pages")),
                        ("<Home>", lambda e: self.detail_canvas.yview_moveto(0)),
                        ("<End>", lambda e: self.detail_canvas.yview_moveto(1))):
            self.detail_canvas.bind(seq, fn)
            self.detail_inner.bind(seq, fn)

        # 底部固定操作栏：先 pack side=bottom，小窗口/长清单下永远可见
        bar = tk.Frame(self.f_done, bg=CREAM)
        bar.pack(side="bottom", fill="x", pady=(6, 8))
        self.btn_restart = tk.Button(
            bar, text="再查一份", command=self.back_to_idle,
            bg=CREAM, fg=INK_SOFT, relief="flat", bd=0, cursor="hand2",
            font=(FONT, 9, "underline"))
        self.btn_restart.pack(side="bottom", pady=(4, 0))
        self.hint_label = tk.Label(
            bar, text="下载价格结果后，请将文件上传到月食对话。",
            bg=CREAM, fg=INK_SOFT, font=(FONT, 9))
        self.hint_label.pack(side="bottom", pady=(0, 2))
        self.btn_locate = tk.Button(
            bar, text="打开文件位置", command=self.open_saved_location,
            bg=CREAM, fg=INK_SOFT, relief="flat", bd=0, cursor="hand2",
            font=(FONT, 9, "underline"))
        self.btn_save = tk.Button(
            bar, text="下载结果并返回月食", command=self.save_result,
            bg=VIOLET, fg=WHITE, activebackground=VIOLET_DARK,
            activeforeground=WHITE, relief="flat", bd=0, cursor="hand2",
            font=(FONT, 12, "bold"), width=22, height=2)
        self.btn_save.pack(side="bottom", pady=(0, 6))

        self._show(self.f_idle)

    # ---------- 状态切换 ----------
    def _show(self, frame):
        for f in (self.f_idle, self.f_wait, self.f_busy, self.f_done):
            f.pack_forget()
        frame.pack(fill="both", expand=True)

    def _show_wait(self):
        """进入自检面板（方案 §8.1）：刷新三状态后再展示。"""
        # 能走到这里说明清单已成功读取
        self.check_list_label.configure(text=SELFCHECK_LIST_READY, fg=GREEN)
        if browser_available():
            self.check_browser_label.configure(
                text=SELFCHECK_BROWSER_OK, fg=GREEN)
        else:
            self.check_browser_label.configure(
                text=SELFCHECK_BROWSER_FAIL, fg=RED)
        # 配送区域只能由用户在叮咚网页确认，助手不读取、不验证
        self.check_delivery_label.configure(
            text=SELFCHECK_DELIVERY_PENDING, fg=INK_SOFT)
        self._show(self.f_wait)

    def _log_internal(self, code: str, detail: str = ""):
        """内部错误码只写日志（方案 §8.3）：界面不出现错误码原文。"""
        try:
            log_dir = DATA_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / "internal-errors.log").open(
                    "a", encoding="utf-8") as f:
                ts = datetime.now().astimezone().isoformat()
                f.write(f"{ts} {code} {detail}\n".rstrip() + "\n")
        except OSError:
            pass

    def _reset_job(self):
        """所有结束/重置路径统一清确认（最佳实践 §四）。"""
        self._job = None
        self._cancel_requested = False
        self._results_saved = False

    def back_to_idle(self):
        self._saved_path = None
        self.btn_locate.pack_forget()
        self._reset_job()
        self._show(self.f_idle)

    # ---------- 输入 ----------
    def _on_drop(self, event):
        path = (event.data or "").strip().strip("{}")
        if path:
            self._adopt(Path(path))

    def pick_query_file(self):
        picked = filedialog.askopenfilename(
            title="选择月食给你的食材文件",
            filetypes=[("JSON 文件", "*.json")],
            parent=self.root,
        )
        if picked:
            self._adopt(Path(picked))

    def _adopt(self, path: Path):
        if not looks_like_query(path):
            messagebox.showinfo(
                "文件无效", "这个文件不是有效的月食食材清单，请重新选择。",
                parent=self.root)
            return
        # 导入时自检（方案 §8.1）：本机没有可用浏览器就不进入后续流程，
        # 直接给操作建议，不让用户在后面的步骤才撞到失败。
        if not browser_available():
            self._log_internal("browser_unavailable")
            messagebox.showerror(
                "无法打开浏览器", friendly_error("browser_unavailable"),
                parent=self.root)
            return
        qf = adopt_query_file(path)
        try:
            data = json.loads(qf.read_text(encoding="utf-8"))
            names = [str(i.get("query", "?")) for i in data.get("items", [])]
        except Exception:
            names = []
        _state["item_names"] = names
        # 新清单 = 新任务：创建任务级状态，旧确认一律作废（最佳实践 §四）。
        self._reset_job()
        self._job = {
            "request_id": str(data.get("request_id", "")),
            "query_file": qf,
            "file_name": path.name,
            "item_names": names,
            "delivery_confirmed": False,
            "user_clicked_start": False,
        }
        summary = (f"{path.name}\n{len(names)} 种食材："
                   + "、".join(names[:12]) + ("…" if len(names) > 12 else ""))
        self.file_label.configure(text=summary)
        self.wait_file_label.configure(text=summary)
        self.btn_start.configure(state="normal")
        self.bar["value"] = 0
        self.progress_label.configure(text="正在打开叮咚网页…")
        self._show(self.f_busy)
        # 只准备环境（打开网页/检查登录），不排队任何查询任务。
        self._tasks.put(("prepare", qf))

    def click_start_query(self):
        """开始按钮：四条件同时成立才允许排队查询（最佳实践 §三）。"""
        job = self._job
        if not job:
            return
        job["delivery_confirmed"] = True
        job["confirmed_at"] = datetime.now().astimezone().isoformat()
        job["user_clicked_start"] = True
        self.btn_start.configure(state="disabled")  # 防重复点击
        self.bar["value"] = 0
        self.progress_label.configure(text="正在准备…")
        self._show(self.f_busy)
        self._tasks.put(("start_query",))

    # ---------- 会话后台线程 ----------
    def _session_worker(self):
        while True:
            task = self._tasks.get()
            try:
                if task[0] == "close":
                    # 关闭途中的报错（如浏览器已被用户先关掉）属正常收尾，
                    # 静默吞掉，不写 last-error、不弹错误界面。
                    try:
                        self._close_session()
                    except Exception:
                        pass
                    return
                if task[0] == "prepare":
                    self._do_prepare(task[1])
                elif task[0] == "start_query":
                    self._do_start_query()
                elif task[0] == "relogin":
                    self._do_relogin()
                elif task[0] == "clear_login":
                    self._do_clear_login()
            except Exception:
                # 结果已保存后发生的收尾错误（如用户随后关了浏览器）
                # 只留调试记录，不写 last-error、不弹失败界面（方案 §四）。
                if self._results_saved:
                    self._results_saved = False
                    continue
                self._record_error()
                self.root.after(0, self._fail_ui)

    def _ensure_session(self):
        if self._session is not None:
            try:
                _ = self._session[2].url
                return
            except Exception:
                self._close_session()
        import app as helper_app
        helper_app.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        helper_app.LOG_DIR.mkdir(parents=True, exist_ok=True)
        helper_app.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.root.after(0, lambda: self.progress_label.configure(
            text="正在打开叮咚网页…"))
        try:
            self._session = helper_app.open_browser_session(inspect_mode=False)
        except Exception as exc:
            # §8.3：异常原文只写日志，界面只给操作建议。
            self._log_internal("browser_unavailable", repr(exc))
            self._call_on_main(lambda: messagebox.showerror(
                "无法打开浏览器",
                friendly_error("browser_unavailable") + "\n\n"
                "· 可打开「开始」菜单搜索 Edge 或 Chrome 确认是否已安装\n"
                "· 都没有的话，请先安装 Microsoft Edge 或 Chrome",
                parent=self.root))
            raise

    def _close_session(self):
        if self._session is not None:
            try:
                import app as helper_app
                helper_app.close_browser_session(self._session)
            except Exception:
                pass
            self._session = None
            self._logged_in = False

    def _confirm_login_ui(self):
        """登录是异常分支：仅在会话失效时弹出。登录完成不触发查价，
        只回到等待确认页等用户点开始按钮（最佳实践 §二）。"""
        self._call_on_main(lambda: messagebox.showinfo(
            "需要登录",
            "请在打开的叮咚网页完成登录并确认收货地址，\n"
            "确认商品和价格能正常显示后，回到这里点【确定】。\n\n"
            "（本工具不读取你的具体地址；登录一次后会记住。）",
            parent=self.root,
        ))
        self._logged_in = True

    def _do_prepare(self, qf: Path):
        """导入后只做准备工作：打开网页、必要时引导登录，
        然后停在等待确认页，绝不自动查价。"""
        import app as helper_app
        self._ensure_session()
        _pw, _ctx, page, _collector = self._session

        page.goto(helper_app.DINGDONG_HOME,
                  wait_until="domcontentloaded", timeout=30000)
        helper_app.audit_current_url(page)

        if not self._logged_in and helper_app.session_needs_login(page):
            self.root.after(0, lambda: self.progress_label.configure(
                text="需要你登录叮咚…"))
            self._confirm_login_ui()
            page.goto(helper_app.DINGDONG_HOME,
                      wait_until="domcontentloaded", timeout=30000)
            helper_app.audit_current_url(page)

        # 就绪：进入自检面板，无限期等用户点击开始按钮。
        self.root.after(0, self._show_wait)

    def _do_start_query(self):
        import app as helper_app
        t0 = time.monotonic()
        # 开始按钮处理函数内再次校验（不只靠界面禁用）。
        job = self._job
        if (not job or not job.get("user_clicked_start")
                or not job.get("delivery_confirmed")):
            # §8.3：内部错误码写日志，界面只给操作建议。
            self._log_internal("delivery_context_missing")
            self.root.after(0, lambda: messagebox.showwarning(
                "需要确认配送区域",
                friendly_error("delivery_context_missing"),
                parent=self.root))
            self.root.after(0, self._show_wait)
            return
        self._ensure_session()  # 浏览器被关过会自动重开
        _pw, _ctx, page, collector = self._session

        page.goto(helper_app.DINGDONG_HOME,
                  wait_until="domcontentloaded", timeout=30000)
        helper_app.audit_current_url(page)

        # 点击开始后若发现会话失效，引导登录再回到等待页重新确认。
        if not self._logged_in and helper_app.session_needs_login(page):
            self.root.after(0, lambda: self.progress_label.configure(
                text="需要你登录叮咚…"))
            self._confirm_login_ui()
            page.goto(helper_app.DINGDONG_HOME,
                      wait_until="domcontentloaded", timeout=30000)
            helper_app.audit_current_url(page)
            job["delivery_confirmed"] = False
            job["user_clicked_start"] = False
            self.root.after(0, lambda: self.btn_start.configure(
                state="normal"))
            self.root.after(0, self._show_wait)
            return

        batch = helper_app.load_query(Path(job["query_file"]))
        self._last_batch = batch
        started_at = datetime.now().astimezone()
        total = len(batch.items)

        def on_progress(i, n, text):
            if self._cancel_requested:
                raise helper_app.QueryCancelled()
            self.root.after(0, lambda: (
                self.progress_label.configure(
                    text=f"正在查询 {i} / {n}：{text}"),
                self.bar.configure(value=int((i - 1) / max(n, 1) * 100))))

        cancelled = False
        results, diags = [], []
        try:
            results, diags = helper_app.execute_batch(
                page, collector, batch, on_progress)
        except helper_app.QueryCancelled:
            cancelled = True
        except helper_app.BrowserSessionLost:
            # 浏览器窗口被关掉/崩溃：清确认、回等待页，重开网页后重新确认。
            self._close_session()
            if self._job is not None:
                self._job["delivery_confirmed"] = False
                self._job["user_clicked_start"] = False
            self.root.after(0, lambda: self.btn_start.configure(
                state="normal"))
            self.root.after(0, lambda: messagebox.showwarning(
                "查询中断",
                "查询过程中叮咚网页被关闭或失去响应，剩余项目没有完成。\n\n"
                "网页会在你下次开始时自动重开，请重新确认地址后再查。",
                parent=self.root))
            self.root.after(0, self._show_wait)
            return

        self._perf["query_total_ms"] = int((time.monotonic() - t0) * 1000)
        self._perf["query_per_item_ms"] = (
            self._perf["query_total_ms"] // max(total, 1))

        if cancelled:
            # 取消即清除本次确认：再查需重新确认地址。
            if self._job is not None:
                self._job["delivery_confirmed"] = False
                self._job["user_clicked_start"] = False
            self.root.after(0, lambda: self.btn_start.configure(
                state="normal"))
            self.root.after(0, lambda: self.progress_label.configure(
                text="已取消"))
            self.root.after(0, self._show_wait)
            return

        self._last_diags = (batch, results, diags, started_at, True)
        self._last_collector_counts = (
            collector.search_response_count, collector.cache_hit_count)
        out = current_result_file()
        helper_app.finish_and_save(
            batch, results, diags, started_at,
            login_confirmed=True,
            delivery_confirmed=True,  # 本次任务用户已显式点击确认
            output_file=out, inspect_mode=False,
            write_diagnostics=False,  # 正常成功不生成诊断文件
            search_response_count=collector.search_response_count,
            cache_hit_count=collector.cache_hit_count)
        self._results_saved = True

        # 查询完成即清确认，防止下一任务复用（最佳实践 §四）。
        if self._job is not None:
            self._job["delivery_confirmed"] = False
            self._job["user_clicked_start"] = False

        self.root.after(0, lambda: self.bar.configure(value=100))
        self.root.after(0, self._show_done)

    # ---------- 完成态 ----------
    def _toggle_detail(self):
        """round58：默认只显示摘要；点击展开/收起可滚动明细列表。"""
        if self._detail_visible:
            self.detail_wrap.pack_forget()
            self.btn_toggle_detail.configure(text="查看全部结果 ▾")
        else:
            self.detail_wrap.pack(fill="both", expand=True,
                                  before=self.btn_save.master)
            self.btn_toggle_detail.configure(text="收起结果 ▴")
            self.detail_canvas.focus_set()
        self._detail_visible = not self._detail_visible

    # ---------- 完成态 ----------
    def _show_done(self):
        import app as helper_app
        rf = current_result_file()
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
        except Exception:
            self._fail_ui()
            return
        results = data.get("results", [])
        ok_n = sum(1 for r in results if r.get("status") == "success")
        need_fallback = len(results) - ok_n

        # ---- 摘要（默认可见）：成功/需处理计数 + 校验状态 + 价格变化 ----
        lines = [f"成功 {ok_n} 项   需处理 {need_fallback} 项", ""]
        # E01–E05 自检（round58）：技术字段由助手自检，用户只看结论
        req_id = (self._last_batch.request_id
                  if getattr(self, "_last_batch", None) else
                  (self._last_diags[0].request_id if self._last_diags else ""))
        check = helper_app.export_selfcheck(rf, req_id)
        if all(check[k] for k in ("E01", "E02", "E03", "E04", "E05", "E06")):
            # 2026-09-18：E01–E06 全通过（E06 = observed_at 非空）
            lines.append("结果已通过格式校验，可直接上传回月食对话。")
        elif not check["E03"]:
            # §8.3：结果不属于本次计划（内部码 request_id mismatch，写日志），
            # 界面只给操作建议。
            self._log_internal("request_id mismatch",
                               f"missing={','.join(check['missing'])}")
            lines.append(friendly_error("request_id mismatch"))
        else:
            lines.append("结果文件格式不完整，请回到查价助手重新保存。")
            lines.append("（字段明细见 设置与帮助 → 导出诊断信息）")
        # 价格变化摘要（v1.7/v2.0 口径不变）
        changes = data.get("price_changes") or []
        if changes:
            down = sum(1 for c in changes if c.get("change") == "down")
            up = sum(1 for c in changes if c.get("change") == "up")
            other = sum(1 for c in changes
                        if c.get("change") in ("new", "removed"))
            parts = []
            if down: parts.append(f"{down} 个降价")
            if up: parts.append(f"{up} 个涨价")
            if parts:
                lines.append("较上次查询：" + "、".join(parts))
            if other:
                lines.append(f"另有 {other} 个候选变化（详见结果文件）")
        if need_fallback:
            # §8.3：全部失败时内部码 all_candidates_rejected 写日志；
            # 界面文案统一走映射（部分/全部失败都给同一条操作建议）。
            if ok_n == 0:
                self._log_internal("all_candidates_rejected",
                                   f"total={len(results)}")
            lines.append(friendly_error("all_candidates_rejected"))
        self.summary_label.configure(text="\n".join(lines))

        # ---- 明细（默认收起）：可滚动列表，失败项可点击查看原因 ----
        for child in self.detail_inner.winfo_children():
            child.destroy()
        for r in results:
            ok = r.get("status") == "success"
            mark = "✓" if ok else "✗"
            name = r.get("query", "?")
            if ok:
                tk.Label(self.detail_inner, text=f"{mark} {name}",
                         bg=WHITE, fg=INK, font=(FONT, 10),
                         anchor="w").pack(fill="x", padx=10, pady=1)
            else:
                reason = STATUS_CN.get(r.get("status"), r.get("status", "失败"))
                btn = tk.Label(self.detail_inner,
                               text=f"{mark} {name}（{reason}，点击查看）",
                               bg=WHITE, fg=RED, font=(FONT, 10),
                               anchor="w", cursor="hand2")
                btn.pack(fill="x", padx=10, pady=1)
                btn.bind("<Button-1>", lambda e, rr=r, rs=reason:
                         messagebox.showinfo(
                             "未取得价格的原因",
                             f"食材：{rr.get('query', '?')}\n状态：{rs}\n\n"
                             "月食会按后备估价处理本项，也可稍后在助手中重查。",
                             parent=self.root))
        # 明细默认收起；保持底部操作栏始终可见
        self.detail_wrap.pack_forget()
        self._detail_visible = False
        self.btn_toggle_detail.configure(text="查看全部结果 ▾")
        self._show(self.f_done)

    def save_result(self):
        rf = current_result_file()
        if not rf.exists():
            messagebox.showinfo("提示", "还没有结果，请先拖入食材文件。",
                                parent=self.root)
            return
        target = filedialog.asksaveasfilename(
            title="下载价格结果",
            defaultextension=".json",
            initialfile=RESULT_NAME,
            filetypes=[("JSON 文件", "*.json")],
            parent=self.root,
        )
        if not target:
            return
        try:
            shutil.copyfile(rf, target)
        except OSError as exc:
            # §8.3：异常原文只写日志，界面只给操作建议。
            self._log_internal("save_failed", repr(exc))
            messagebox.showerror(
                "保存失败", friendly_error("save_failed"), parent=self.root)
            return
        self._saved_path = Path(target)
        self.btn_locate.pack(pady=(0, 4))
        messagebox.showinfo(
            "保存成功", "价格结果已下载，请将文件上传到月食对话。",
            parent=self.root)

    def open_saved_location(self):
        target = self._saved_path or current_result_file()
        if target.exists():
            subprocess.Popen(["explorer", "/select,", str(target)],
                             **_no_window_kwargs())
        else:
            self.menu_open_output()

    # ---------- 菜单：设置与帮助 ----------
    def menu_relogin(self):
        self._tasks.put(("relogin",))

    def _do_relogin(self):
        self._logged_in = False
        # 重新登录即作废本次地址确认（最佳实践 §四）。
        if self._job is not None:
            self._job["delivery_confirmed"] = False
            self._job["user_clicked_start"] = False
            self.root.after(0, lambda: self.btn_start.configure(
                state="normal"))
        self._ensure_session()
        self._confirm_login_ui()
        self.root.after(0, lambda: messagebox.showinfo(
            "完成", "登录信息已更新。", parent=self.root))

    def menu_clear_login(self):
        ok = messagebox.askyesno(
            "清除本地登录信息",
            "将删除本机保存的叮咚登录状态，下次使用需要重新登录。\n\n确定清除？",
            parent=self.root)
        if ok:
            self._tasks.put(("clear_login",))

    def _do_clear_login(self):
        self._close_session()
        import app as helper_app
        shutil.rmtree(helper_app.PROFILE_DIR, ignore_errors=True)
        if self._job is not None:
            self._job["delivery_confirmed"] = False
            self._job["user_clicked_start"] = False
        self.root.after(0, lambda: messagebox.showinfo(
            "完成", "本地登录信息已清除。", parent=self.root))

    def menu_open_output(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(OUTPUT_DIR)], **_no_window_kwargs())

    def menu_export_diagnostics(self):
        try:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            target = OUTPUT_DIR / f"诊断包-{ts}.zip"
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
                # 诊断仅在用户主动导出时生成。
                if self._last_diags is not None:
                    import app as helper_app
                    batch, results, diags, started_at, delivery = \
                        self._last_diags
                    resp_count, cache_count = self._last_collector_counts
                    log = helper_app.DiagnosticsLog(
                        request_id=batch.request_id,
                        completed_at=datetime.now().astimezone(),
                        # v2.0：实时接口响应计数（不再是遍历节点数）。
                        search_response_count=resp_count,
                        cache_hit_count=cache_count,
                        recovered_record_count=sum(
                            1 for d in diags for item in d.dropped
                            if item.get("recovered") == "true"),
                        unique_sku_count=sum(
                            len(r.candidates) for r in results),
                        eligible_sku_count=sum(
                            1 for r in results for c in r.candidates
                            if c.eligible_for_purchase),
                        filtered_count=sum(
                            d.counts.get("excluded_count", 0) for d in diags),
                        parse_warnings=sorted({
                            w for r in results for c in r.candidates
                            for w in c.parse_warnings}),
                        per_query=diags,
                        extras={"inspect_mode": False,
                                "query_count": len(batch.items),
                                # 脱敏：只含来源类型与沙箱状态，无路径/用户名
                                "browser": helper_app.last_browser_info()},
                    )
                    z.writestr("diagnostics.json",
                               log.model_dump_json(indent=2))
                for fp in (current_result_file(),
                           _state.get("query_file") and Path(_state["query_file"]),
                           DATA_DIR / "logs" / "last-error.txt",
                           DATA_DIR / "logs" / "network-responses.jsonl"):
                    if fp and Path(fp).exists():
                        z.write(fp, Path(fp).name)
            subprocess.Popen(["explorer", "/select,", str(target)],
                             **_no_window_kwargs())
            messagebox.showinfo(
                "已导出", "诊断包已生成并为你打开，把这个 zip 发给维护者即可。",
                parent=self.root)
        except Exception as exc:  # noqa: BLE001
            # §8.3：异常原文只写日志，界面只给操作建议。
            self._log_internal("export_failed", repr(exc))
            messagebox.showerror(
                "导出失败", friendly_error("export_failed"), parent=self.root)

    def menu_about(self):
        version = "2.0"
        messagebox.showinfo(
            "关于与隐私说明",
            f"月食 · 叮咚查价助手 v{version}\n\n"
            "只读工具：不加购物车、不下单、不支付、不领券、不改地址。\n"
            "不读取、不保存、不验证你的具体收货地址；\n"
            "不记录手机号、Cookie、验证码。\n"
            "登录状态只保存在你自己的电脑上。\n\n"
            "价格为查询当时叮咚页面参考价，最终以下单结算为准。",
            parent=self.root)

    # ---------- 取消 / 失败 ----------
    def request_cancel(self):
        self._cancel_requested = True
        self.progress_label.configure(text="正在取消…")

    def _fail_ui(self):
        # §8.3：内部错误由 _record_error 写入日志，界面只给操作建议。
        messagebox.showerror(
            "程序失败", friendly_error("internal_error"), parent=self.root)
        self.back_to_idle()

    # ---------- 工具 ----------
    def _call_on_main(self, fn):
        done = threading.Event()
        box = {}

        def wrapper():
            try:
                box["value"] = fn()
            finally:
                done.set()

        self.root.after(0, wrapper)
        done.wait()
        return box.get("value")

    def _record_error(self):
        try:
            log_dir = DATA_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "last-error.txt").write_text(
                traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass

    def on_close(self):
        try:
            st = load_settings()
            st["window_geometry"] = f"{self.root.winfo_width()}x{self.root.winfo_height()}"
            save_settings(st)
        except Exception:
            pass
        try:
            log_dir = DATA_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "perf.json").write_text(
                json.dumps(self._perf, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except OSError:
            pass
        try:
            self._tasks.put_nowait(("close",))
        except Exception:
            pass
        self.root.destroy()


_T0 = time.monotonic()


def _set_window_icon(root: tk.Tk) -> None:
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Yueshi.DingdongHelper")
        except Exception:
            pass
    ico = ASSET_DIR / "app.ico"
    if ico.exists():
        try:
            root.iconbitmap(default=str(ico))
        except Exception:
            try:
                root.iconbitmap(str(ico))
            except Exception:
                pass
    png = ASSET_DIR / "icon-64.png"
    if png.exists():
        try:
            img = tk.PhotoImage(file=str(png))
            root.iconphoto(True, img)
            root._icon_ref = img
        except Exception:
            pass


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    if _HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    _set_window_icon(root)
    win = HelperWindow(root)

    # 拖到 EXE 图标上启动：文件路径作为第一个参数传入。
    if len(sys.argv) > 1:
        dropped = Path(sys.argv[1])
        if dropped.suffix.lower() == ".json" and dropped.exists() \
                and looks_like_query(dropped):
            win.root.after(300, lambda: win._adopt(dropped))

    root.protocol("WM_DELETE_WINDOW", win.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
