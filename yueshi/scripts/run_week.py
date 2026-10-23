#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_week.py —— 周计划确定性收尾一键编排（round79）。

把「目标校验 → 价格结果校验 → 采购汇总 → 渲染」压成一个入口，fail-fast，
不代替菜单设计（AI 与用户确认仍在前置步骤完成）。

用法：
    python scripts/run_week.py --plan plan.json --out-dir out --format html \
        [--targets daily_targets.json] [--price-result price-result.json] \
        [--request-id ID] [--meals menu.csv] [--prices prices.csv] \
        [--packages packages.csv] [--inventory inventory.csv] \
        [--selection-report report.jsonl] [--no-render]

退出码：0 全部通过；2 参数/输入错误；3 任一步校验或渲染失败。
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _run(step, args):
    cmd = [sys.executable, "-X", "utf8"] + args
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    return {
        "step": step,
        "rc": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
    }


def main():
    ap = argparse.ArgumentParser(description="周计划确定性收尾一键编排")
    ap.add_argument("--plan", required=True, help="plan.json 路径")
    ap.add_argument("--out-dir", required=True, help="产物目录（自动创建）")
    ap.add_argument("--format", default="html",
                    help="渲染格式，多格式用逗号分隔（html/md/pdf/docx）")
    ap.add_argument("--targets", help="daily_targets.json（做完整性校验）")
    ap.add_argument("--price-result", help="price-result.json（P01–P08 校验）")
    ap.add_argument("--request-id", help="期望的 request_id（P08）")
    ap.add_argument("--query", help="price-query.json（P07 对照）")
    ap.add_argument("--meals", help="餐次明细 CSV（生成采购清单）")
    ap.add_argument("--inventory", help="家中库存 CSV")
    ap.add_argument("--prices", help="本地价格 CSV")
    ap.add_argument("--packages", help="包装规格 CSV")
    ap.add_argument("--selection-report", help="预选追溯 JSONL")
    ap.add_argument("--no-render", action="store_true", help="只做校验不渲染")
    args = ap.parse_args()

    if not os.path.isfile(args.plan):
        print("plan.json 不存在: " + args.plan, file=sys.stderr)
        return 2
    os.makedirs(args.out_dir, exist_ok=True)

    steps = []
    if args.targets:
        steps.append(_run("targets", [
            os.path.join(HERE, "daily_target_compiler.py"),
            "--check", args.targets]))

    if args.price_result:
        cmd = [os.path.join(HERE, "price_result_validator.py"),
               args.price_result]
        if args.request_id:
            cmd += ["--request-id", args.request_id]
        if args.query:
            cmd += ["--query", args.query]
        steps.append(_run("price_result", cmd))

    if args.meals:
        cmd = [os.path.join(HERE, "shopping_aggregator.py"),
               "--menu", args.meals,
               "--csv-out", os.path.join(args.out_dir, "shopping.csv")]
        for flag, value in (("--inventory", args.inventory),
                            ("--prices", args.prices),
                            ("--packages", args.packages),
                            ("--selection-report", args.selection_report)):
            if value:
                cmd += [flag, value]
        steps.append(_run("shopping", cmd))

    if not args.no_render:
        fmts = [f.strip() for f in args.format.split(",") if f.strip()]
        if not fmts:
            print("--format 不能为空", file=sys.stderr)
            return 2
        target = (os.path.join(args.out_dir, "weekly-plan." + fmts[0])
                  if len(fmts) == 1 else args.out_dir)
        steps.append(_run("render", [
            os.path.join(HERE, "render_output.py"),
            "--input", args.plan,
            "--format", args.format,
            "--output", target]))

    ok = all(step["rc"] == 0 for step in steps)
    report = {
        "plan": args.plan,
        "out_dir": args.out_dir,
        "skipped_render": bool(args.no_render),
        "steps": [{"step": s["step"], "rc": s["rc"]} for s in steps],
        "ok": ok,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not ok:
        for step in steps:
            if step["rc"] != 0:
                detail = step["stderr"] or step["stdout"]
                print("[失败] %s rc=%d\n%s" % (step["step"], step["rc"],
                                               detail), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
