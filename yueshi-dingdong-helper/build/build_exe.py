"""构建正式用户包（由 builder_ui.py 调用，也可单独运行）。

用法：build-venv\\Scripts\\python.exe build\\build_exe.py
产物：_build\\dist\\月食叮咚查价助手\\（中间产物，生成即删）
     → 复制到项目根第一层「月食叮咚查价助手」

R08：任何一步失败都以非零退出码结束，绝不留下看似成功的空 dist。
正式构建自动禁用开发者采集（config.INSPECT_ALLOWED 需要 YUESHI_DEV=1，
打包机默认不设置，即正式构建中 inspect 不可用）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent   # build\
TOP = BUILD_DIR.parent                        # 项目根
SRC = TOP / "src"
WORK = TOP / "_build"                          # PyInstaller 临时目录（生成即删）
# 虚拟环境放系统盘用户目录，项目文件夹始终干净（结构优化方案第二轮 3.3）。
PY = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "YueshiDingdongHelper" / "build-venv" / "Scripts" / "python.exe"
)
if not PY.exists():
    PY = Path(sys.executable)

APP_NAME = "月食叮咚查价助手"
# dist 只是中间产物，放进 _build 随构建结束一并删除；
# 成品文件夹直接放项目根第一层，与「一键生成安装包.bat」并列。
# v2.0 命名统一：用户可见名称不再带「便携版」等版本区分字样。
DIST_DIR = WORK / "dist" / APP_NAME
PORTABLE_DIR = TOP / APP_NAME
LEGACY_PORTABLE_DIR = TOP / f"{APP_NAME}-便携版"

os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = (
    "https://registry.npmmirror.com/-/binary/playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(TOP / "browsers")
# 确保正式构建不含开发者开关
os.environ.pop("YUESHI_DEV", None)


def run(cmd: list[str], step: str) -> None:
    print(f"[step] {step}")
    result = subprocess.run([str(c) for c in cmd], cwd=TOP)
    if result.returncode != 0:
        print(f"[FAIL] {step} (exit {result.returncode})")
        sys.exit(1)


def main() -> int:
    if not (SRC / "gui.py").exists():
        print("[FAIL] src/gui.py not found; run from project folder.")
        return 1

    run([PY, "-m", "pip", "install",
         "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
         "--timeout", "120", "pyinstaller"], "install PyInstaller")

    # 默认不打包浏览器：程序运行时优先调用系统 Chrome / Edge（Win10/11 自带），
    # 包体从约 1.6GB 降到约 150MB。少数无 Chrome/Edge 的机器，
    # 设 YUESHI_BUNDLE_BROWSER=1 重新构建即可携带内置浏览器。
    bundle_browser = os.environ.get("YUESHI_BUNDLE_BROWSER") == "1"
    if bundle_browser:
        # --no-shell：不下载用不到的无头浏览器，省约 115MB。
        run([PY, "-m", "playwright", "install", "chromium", "--no-shell"],
            "download browser runtime into browsers/")
    else:
        print("[step] skip bundled browser (use system Chrome/Edge)")

    # 构建前自动清理旧产物，防递归打包、防旧文件混入（结构优化 3.3.4）。
    # 同时清除旧命名（-便携版）目录，升级后只保留一个成品文件夹。
    shutil.rmtree(WORK, ignore_errors=True)
    for old in (PORTABLE_DIR, LEGACY_PORTABLE_DIR):
        try:
            shutil.rmtree(old)
        except OSError:
            time.sleep(1.5)
            shutil.rmtree(old, ignore_errors=True)

    pyinstaller_cmd = [
        PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", APP_NAME,
        "--icon", str(TOP / "assets" / "app.ico"),
        "--specpath", str(WORK),
        "--workpath", str(WORK),
        "--distpath", str(WORK / "dist"),
        "--collect-all", "playwright",
        "--collect-all", "tkinterdnd2",
        "--add-data", f"{TOP / 'assets'};assets",
        "--add-data", f"{TOP / 'examples' / '月食-查价清单-示例.json'};.",
    ]
    if bundle_browser and (TOP / "browsers").exists():
        pyinstaller_cmd += ["--add-data", f"{TOP / 'browsers'};browsers"]
    pyinstaller_cmd.append(str(SRC / "gui.py"))
    run(pyinstaller_cmd, "build windowed EXE")

    exe = DIST_DIR / f"{APP_NAME}.exe"
    if not exe.exists() or exe.stat().st_size < 1_000_000:
        print(f"[FAIL] expected EXE missing or too small: {exe}")
        return 1
    if not (DIST_DIR / "_internal" / "browsers").exists():
        # 默认不携带浏览器：属预期；仅在 bundle 模式下提示检查
        if bundle_browser:
            print("[warn] browsers not at _internal/browsers; check layout")

    # 用户包只放：EXE 运行时 + 清单示例 + 简明说明。源码与脚本不进 dist。
    shutil.copyfile(TOP / "examples" / "月食-查价清单-示例.json",
                    DIST_DIR / "月食-查价清单-示例.json")
    (DIST_DIR / "使用说明.txt").write_text(
        "月食 · 叮咚查价助手\n\n"
        "用法：把月食生成的「月食-查价清单.json」拖进软件。\n"
        "软件会打开叮咚网页，请在网页里登录（首次需要）并确认\n"
        "收货地址正确，然后回到软件点【我已确认收货地址，开始查价】。\n"
        "每次导入清单都要确认一次地址，软件不会自动开始查价。\n"
        "完成后点【保存价格结果】，把「月食-叮咚价格结果.json」上传回月食对话。\n\n"
        "本工具只读：不加购物车、不下单、不支付、不读取具体收货地址。\n"
        "登录、验证码、收货地址均由你本人在叮咚网页内完成。\n",
        encoding="utf-8",
    )

    print(f"[OK] user package ready: {DIST_DIR}")

    # 成品复制到项目根第一层，与「一键生成安装包.bat」并列，一眼可见。
    # 旧目录可能被资源管理器/杀软占用删不掉：先强删，删不掉就覆盖合并；
    # 复制步骤失败不算构建失败（_build 里已有完整产物）。
    try:
        shutil.copytree(DIST_DIR, PORTABLE_DIR, dirs_exist_ok=True)
        print(f"[OK] user package copy at: {PORTABLE_DIR}")
    except OSError as exc:
        print(f"[warn] 复制到最外层失败（{exc}）；可直接使用 {DIST_DIR}")

    # 中间产物（.spec / 构建缓存 / dist）立刻清掉，不让用户看见。
    shutil.rmtree(WORK, ignore_errors=True)
    stray_spec = TOP / f"{APP_NAME}.spec"
    if stray_spec.exists():
        stray_spec.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
