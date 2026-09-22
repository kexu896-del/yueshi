# 月食（yueshi）——采购驱动的周期断食周饮食计划技能

根据身体周期、所在地价格和做饭条件，生成真正**买得到、做得完、吃得完**的一周饮食方案：
先定食材篮子（买什么），再从结构化菜谱库选菜（怎么做），最后反向汇总采购清单（怎么买）。
输出：7 天菜单 + 采购清单（食材、购买量、常见规格、参考价、平替、剩余去向）+ 营养校验。

当前版本：yueshi-1.4.3（稳定基线）

## 仓库结构

- `yueshi/` — 技能本体（SKILL.md + 规则、数据、脚本；纯 Python 标准库，无需安装依赖）
- `yueshi-dingdong-helper/` — 叮咚查价助手源码（可选，仅选"叮咚查价"时需要；Windows）

## 安装与使用（Kimi Code CLI）

### 方式一：插件一键安装（推荐）

在 Kimi Code CLI 中执行：

```text
/plugins install https://github.com/kexu896-del/yueshi
```

然后运行 `/reload` 或开新会话，直接说"帮我做一周食谱"即可触发。

### 方式二：手动安装技能

```bash
git clone https://github.com/kexu896-del/yueshi.git
# 把 yueshi/ 文件夹复制到技能目录：
#   Windows:  C:\Users\<你的用户名>\.kimi-code\skills\
#   macOS/Linux:  ~/.kimi-code/skills/
```

新开会话后，对 Kimi 说"帮我做一周食谱"即可。技能只依赖 Python 3.10+ 标准库（PDF 渲染额外调用本机 Chrome/Edge 浏览器），**不需要 pip install**。

### 方式三：不安装，直接用

把 `yueshi/` 打包成 zip 作为附件发给 Kimi（或任何能读文件的 AI），让它"解压并运行此技能"即可——技能入口是 `yueshi/SKILL.md`。

## 叮咚查价助手（可选）

只有你在制定计划时选择"A. 使用叮咚查价助手"才需要：

1. **免安装版（推荐）**：从本仓库 [Releases](../../releases) 页面下载 `月食叮咚查价助手.zip`，**解压并保留完整文件夹，不要只复制其中的 exe**，双击 `月食叮咚查价助手.exe` 运行。
2. **源码运行**（需要 Python 3.11+）：进入 `yueshi-dingdong-helper/`，`pip install -r requirements.txt` 后运行 `dev/start-gui.bat`。

助手只读取页面商品与价格，**不加购、不下单、不支付、不领券、不改地址**，不读取也不保存你的具体收货地址。

## 使用过程

- **描述实际情况**：告诉月食人数、餐次、口味、预算、做饭条件和需要避开的食物。缺少的信息会合并询问。
- **删除不想要的食材**：月食给出本周候选，你只需要回复不想要的编号；都可以就回复"都可以"。
- **月食生成菜单并检查营养**：这一阶段通常不需要额外操作。
- **选择叮咚时，完成一次查价**：使用查价助手读取清单，完成后把价格结果上传回对话。
- **获取最终计划**：包括 7 天菜单、做法、采购清单、预算和剩余食材安排（PDF / 网页 / Markdown / Word 单选）。

## 安全声明

输出为一般性饮食建议，不构成医疗建议；孕产哺乳、未成年、慢病用药者请先咨询医生。

## 维护与开发

普通使用不需要运行脚本。维护者请阅读：

- `yueshi/SKILL.md`
- `yueshi/CHANGELOG.md`
- `yueshi/developer/maintenance-map.md`
- `yueshi/MAINTENANCE.md`
