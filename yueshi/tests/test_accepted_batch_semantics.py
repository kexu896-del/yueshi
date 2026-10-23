#!/usr/bin/env python3
# 收口轮 P0-5："都可以吃"=accepted_batch(user_reviewed:true)，"直接生成/跳过"=bypassed，二者不得混淆
import os, re
import rule_corpus  # noqa: E402  合并语料唯一助手（round78）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sk = rule_corpus.load_corpus()  # round78：合并语料唯一助手

# 1) accepted_batch 分支存在且 user_reviewed: true
m = re.search(r"都可以吃 / 全部保留[^\n]*`user_reviewed: true`[^\n]*accepted_batch", sk)
assert m, "缺少『都可以吃/全部保留 → user_reviewed:true → accepted_batch』映射"

# 2) bypassed 分支存在且 user_reviewed: false
m = re.search(r"直接生成 / 跳过预选[^\n]*`user_reviewed: false`[^\n]*bypassed", sk)
assert m, "缺少『直接生成/跳过预选 → user_reviewed:false → bypassed』映射"

# 3) bypassed 分支不得包含"都可以"
byp = re.search(r"直接生成 / 跳过预选 / 不用问我[^\n]*", sk)
assert byp and "都可以" not in byp.group(0), "bypassed 分支混入了『都可以』"

# 4) 显式禁令
assert "不得" in sk and "被当作跳过预选" in sk, "缺少『都可以不得视为跳过预选』禁令"

# 5) 旧冲突写法已清除："都可以/直接生成/跳过预选"并列表述不再存在
assert "都可以/直接生成/跳过预选" not in sk, "旧的并列混义写法残留"

print("PASS")
