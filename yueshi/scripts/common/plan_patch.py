#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan.json 幂等补丁（round67，2026-09-18）

价格合并/预算更新等运行步骤对 plan.json 的写入必须幂等：
相同输入重复执行时——不重复插入提示、不重复写入执行说明、不改变已冻结业务数据、
输出内容哈希保持一致（方案 §14.3）。
"""
import json


def apply_patch(plan: dict, patch: dict) -> bool:
    """幂等应用补丁；返回是否有实际变化。

    - shopping / price_snapshot_meta：覆盖式写入（内容相同则不动）；
    - execution_tips：追加去重（相同内容不重复插入）；
    - 其他顶层键：覆盖式写入。
    """
    changed = False
    for key, value in patch.items():
        if key == "execution_tips":
            tips = list(plan.get("execution_tips") or [])
            for t in value or []:
                if t not in tips:
                    tips.append(t)
                    changed = True
            if tips != (plan.get("execution_tips") or []):
                plan["execution_tips"] = tips
            continue
        if plan.get(key) != value:
            plan[key] = value
            changed = True
    return changed


def content_hash(plan: dict) -> str:
    """规范化内容哈希（与字段顺序无关）。"""
    import hashlib
    canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
