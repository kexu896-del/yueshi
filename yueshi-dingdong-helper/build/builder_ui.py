"""月食 · 叮咚查价助手 —— 图形化一键构建器。

由根目录「一键生成安装包.bat」用 pythonw 启动（bat 仅供维护者，
一瞬黑框属正常；普通用户只接触构建好的成品文件夹，不运行 bat）。
之后全程是本窗口的进度条界面。

流程：装依赖(0-30%) → 打包程序(30-85%) → 复制成品到项目根(85-100%)。
成品文件夹「月食叮咚查价助手」出现在项目根第一层（与入口 bat 并列），
免安装运行：整个文件夹拷给别人，双击里面的图标即可使用。
任何一步失败：红字提示 + 「打开日志」按钮，绝不静默消失。
日志文件：build/logs/build.log
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parent          # build/
TOP = ROOT.parent                                # 项目根
SRC = TOP / "src"
# 虚拟环境放系统盘用户目录：项目文件夹里不再有 .venv 的几千个文件。
BUILD_VENV = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "YueshiDingdongHelper" / "build-venv"
)
VENV_PY = BUILD_VENV / "Scripts" / "python.exe"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "build.log"

FONT = "Microsoft YaHei"
CREAM = "#faf9f6"
WHITE = "#ffffff"
INK = "#23201c"
INK_SOFT = "#6b675f"
GOLD = "#b98a2f"
GREEN = "#3d7a52"
RED = "#b04040"
VIOLET = "#7a68a6"

NO_WINDOW = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} \
    if sys.platform.startswith("win") else {}


def _run_stream(cmd, log, progress_lines, env=None, cwd=ROOT):
    """运行子进程，输出写入日志和行队列；返回退出码。"""
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    proc = subprocess.Popen(
        [str(c) for c in cmd], cwd=cwd, env=merged_env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", **NO_WINDOW)
    assert proc.stdout is not None
    for line in proc.stdout:
        log.write(line)
        log.flush()
        progress_lines.put(line.rstrip())
    proc.wait()
    return proc.returncode


class BuilderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("月食 · 叮咚查价助手 —— 安装包制作")
        root.geometry("580x640")
        root.configure(bg=CREAM)
        root.resizable(False, False)
        icon = TOP / "assets" / "app.ico"
        if icon.exists():
            try:
                root.iconbitmap(str(icon))
            except Exception:
                pass

        head = tk.Frame(root, bg=WHITE)
        head.pack(fill="x")
        self._icon_img = None
        icon_png = TOP / "assets" / "icon-64.png"
        inner = tk.Frame(head, bg=WHITE)
        inner.pack(pady=10)
        if icon_png.exists():
            try:
                self._icon_img = tk.PhotoImage(file=str(icon_png))
                tk.Label(inner, image=self._icon_img, bg=WHITE).pack(
                    side="left", padx=(0, 10))
            except Exception:
                pass
        tk.Label(inner, text="正在制作安装包",
                 font=(FONT, 13, "bold"), bg=WHITE, fg=INK).pack(side="left")
        tk.Frame(root, bg=GOLD, height=2).pack(fill="x")

        body = tk.Frame(root, bg=CREAM)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        self.step_label = tk.Label(body, text="准备中…", anchor="w",
                                   font=(FONT, 10), bg=CREAM, fg=INK)
        self.step_label.pack(fill="x")

        self.bar = ttk.Progressbar(body, orient="horizontal",
                                   mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=(6, 10))

        self.log_text = tk.Text(body, height=10, state="disabled",
                                bg=WHITE, fg=INK_SOFT, font=("Consolas", 8),
                                relief="solid", bd=1, wrap="none")
        self.log_text.pack(fill="both", expand=True)

        self.bottom = tk.Frame(root, bg=CREAM)
        self.bottom.pack(fill="x", padx=18, pady=(0, 14))
        # 按钮区固定在窗口最底部，无论提示文字多长都不会被挤出可视区。
        self.btn_area = tk.Frame(self.bottom, bg=CREAM)
        self.btn_area.pack(side="bottom", fill="x")
        self.hint = tk.Label(self.bottom, text="", anchor="w",
                             font=(FONT, 9), bg=CREAM, fg=INK_SOFT,
                             justify="left", wraplength=540)
        self.hint.pack(fill="x")

        self.lines: queue.Queue[str] = queue.Queue()
        self.done = threading.Event()
        self.failed = False
        self.output_note = ""

        threading.Thread(target=self._worker, daemon=True).start()
        self.root.after(100, self._poll)

    # ---------- UI 工具 ----------
    def _set_step(self, text, pct):
        self.step_label.configure(text=text, fg=INK)
        self.bar["value"] = pct

    def _append_log(self, line):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        # 只保留最近 200 行，避免卡顿
        if int(self.log_text.index("end-1c").split(".")[0]) > 200:
            self.log_text.delete("1.0", "100.0")
        self.log_text.configure(state="disabled")

    def _poll(self):
        try:
            while True:
                line = self.lines.get_nowait()
                self._append_log(line)
                self._route_line(line)
        except queue.Empty:
            pass
        if self.done.is_set():
            self._finish()
            return
        self.root.after(100, self._poll)

    def _route_line(self, line):
        """根据子进程输出的 [step] 标记推进进度条。"""
        if "[step] download browser" in line:
            self._set_step("正在下载内置浏览器（约 200MB，首次较慢）…", 32)
        elif "[step] build windowed EXE" in line:
            self._set_step("正在打包程序…", 58)

    def _finish(self):
        for widget in self.btn_area.winfo_children():
            widget.destroy()
        if self.failed:
            self.step_label.configure(text="出错了，制作未完成", fg=RED)
            self.hint.configure(
                text="可以把日志发给维护者排查，或修复后重新双击「一键生成安装包.bat」。")
            tk.Button(self.btn_area, text="打开日志文件", command=self._open_log,
                      bg=WHITE, fg=INK, relief="solid", bd=1,
                      font=(FONT, 10), width=22, height=2,
                      cursor="hand2").pack(pady=(10, 0))
        else:
            self.bar["value"] = 100
            self.step_label.configure(text="全部完成 ✓", fg=GREEN)
            self.hint.configure(text=self.output_note)
            tk.Button(self.btn_area, text="打开输出文件夹",
                      command=self._open_output,
                      bg=VIOLET, fg=WHITE, activebackground="#685896",
                      relief="flat", font=(FONT, 12, "bold"),
                      width=22, height=2,
                      cursor="hand2").pack(pady=(10, 4))

    def _open_log(self):
        subprocess.Popen(["explorer", "/select,", str(LOG_FILE)], **NO_WINDOW)

    def _open_output(self):
        subprocess.Popen(["explorer", str(TOP)], **NO_WINDOW)

    # ---------- 构建流程 ----------
    def _worker(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("w", encoding="utf-8") as log:
            try:
                self._build(log)
            except Exception as exc:  # noqa: BLE001
                log.write(f"\n[FATAL] {exc}\n")
                self.failed = True
        self.done.set()

    def _build(self, log):
        lines = self.lines
        # 1) 环境
        self.root.after(0, lambda: self._set_step(
            "正在准备运行环境（首次需下载依赖，请保持网络畅通）…", 2))
        if not VENV_PY.exists():
            code = _run_stream([sys.executable, "-m", "venv", str(BUILD_VENV)],
                               log, lines)
            if code != 0:
                self.failed = True
                return
        # 每次都校验依赖（幂等）：新增依赖时旧环境也能自动补齐。
        code = _run_stream(
            [VENV_PY, "-m", "pip", "install",
             "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
             "--timeout", "120", "-r", str(TOP / "requirements.txt"),
             "pyinstaller"], log, lines)
        if code != 0:
            self.failed = True
            return
        self.root.after(0, lambda: self._set_step("环境就绪", 30))

        # 2) 浏览器 + 3) 打包（build_exe.py 内部两步，按输出推进进度条）
        code = _run_stream([VENV_PY, str(ROOT / "build_exe.py")], log, lines)
        if code != 0:
            self.failed = True
            return
        self.root.after(0, lambda: self._set_step("程序打包完成", 85))

        self.output_note = (
            "做好了：点「打开输出文件夹」，里面的"
            "「月食叮咚查价助手」文件夹就是成品，\n"
            "整个文件夹拷给别人，双击里面的图标就能用，不用安装。")
        self.root.after(0, lambda: self._set_step("全部完成", 100))
        return


def main():
    root = tk.Tk()
    BuilderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
