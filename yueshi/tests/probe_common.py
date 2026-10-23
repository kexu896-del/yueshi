# -*- coding: utf-8 -*-
"""跨仓探针公共辅助（round75）

技能仓测试对助手仓（yueshi-dingdong-helper，独立仓库）的探针统一经本模块：

- helper_src_dir(skill_root=None)：兼容平铺（../yueshi-dingdong-helper/src）与
  嵌套（../yueshi-dingdong-helper/yueshi-dingdong-helper/src）两种布局；
  缺失返回 None（调用方据此 SKIP），不抛异常。
- read_helper(rel)：读取助手 src 下文件；缺失返回 None。
- load_helper_module(name, rel)：按文件路径加载助手模块；缺失返回 None。
- skip(reason)：打印统一 SKIP 标记（测试进程照常 exit 0）。

探针策略（docs/adr/0003）：同步类校验（词表/版本/判定行为）必须是行为对拍
（tests/test_round73_*）；功能契约类与结构守卫类保留文本/源码探针，但必须
经本模块读取并在助手缺席时 SKIP。
"""
import importlib.util
import os

HELPER_DIRNAME = "yueshi-dingdong-helper"


def _skill_root(skill_root):
    return skill_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def helper_src_dir(skill_root=None):
    """返回助手源码目录（绝对路径）；缺失返回 None。"""
    root = _skill_root(skill_root)
    base = os.path.join(root, "..", HELPER_DIRNAME)
    for cand in (os.path.join(base, "src"),
                 os.path.join(base, HELPER_DIRNAME, "src")):
        if os.path.isdir(cand):
            return os.path.abspath(cand)
    return None


def read_helper(rel, skill_root=None):
    """读取助手 src 下文件（rel 相对 src/）；缺失返回 None。"""
    src = helper_src_dir(skill_root)
    if not src:
        return None
    path = os.path.join(src, rel.replace("/", os.sep))
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_helper_module(name, rel, skill_root=None):
    """按文件路径加载助手模块（不写入 sys.path）；缺失返回 None。"""
    src = helper_src_dir(skill_root)
    if not src:
        return None
    path = os.path.join(src, rel.replace("/", os.sep))
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def skip(reason):
    """打印统一 SKIP 标记（外部仓库缺席时的降级路径）。"""
    print("SKIP: " + reason)
