# 开发文档（维护者专用）

普通用户不需要本文件。正式用户包由维护者预构建，不包含源码与构建脚本。

**交付口径（round61）**：当前过渡交付方式为完整文件夹分发（免安装运行）；正式 Windows 安装版为既定目标。月食侧 README 只描述一种正式路径并标注过渡状态，不并列声称两种方式均为正式唯一路径；安装版落地后以安装版为唯一口径并回改两端文档。

## 交付物三层

| 交付物 | 内容 | 面向 |
|---|---|---|
| 用户包 | 预构建 windowed EXE + 浏览器运行时 + price-query.json 示例 + 使用说明.txt | 普通用户 |
| 源码包（本目录） | Python 源码、requirements、构建脚本、开发模式 | 开发维护 |
| 诊断包 | 用户主动导出的脱敏日志 zip | 排错 |

## 源码运行

```bash
python -m venv %LOCALAPPDATA%\YueshiDingdongHelper\build-venv
%LOCALAPPDATA%\YueshiDingdongHelper\build-venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python src\app.py                       # 命令行查价
python src\gui.py                       # 窗口
```

或构建一次后双击 `dev/start-gui.vbs` 静默启动窗口（无控制台，自动找
build-venv）。运行期数据（登录态/结果/日志）统一在
`%LOCALAPPDATA%\YueshiDingdongHelper\`，项目文件夹只留源码。

## 开发模式（inspect）

正式构建在代码层禁用 inspect（`config.INSPECT_ALLOWED` 需要环境变量 `YUESHI_DEV=1`）。
启用方式：

```bash
set YUESHI_DEV=1
python app.py --inspect
```

启用后窗口「更多」菜单才会出现开发者入口。inspect 日志写入
`logs/network-responses.jsonl`（脱敏：不记录 Cookie、请求头、手机号、地址全文、验证码）。

## 构建正式用户包

```bash
install-deps.bat   # 一次性
build-exe.bat      # 纯 ASCII 壳，实际逻辑在 build_exe.py
```

`build_exe.py`：安装 PyInstaller → 浏览器运行时下载到项目 `browsers\` →
PyInstaller windowed 打包（中文名「月食叮咚查价助手」）→ 组装 dist 用户包。
R08 门禁：任何一步失败即非零退出，不留下看似成功的空 dist；
打包前强制移除 YUESHI_DEV，正式构建不可能携带 inspect。

发布前必须在**无 Python、无依赖**的干净 Windows 环境烟测（R01–R08）。

## 数据契约

- 输入：`price-query.json`（`PriceQueryBatch`）；不依赖固定文件名——
  拖入 / 选择 / 目录内任何含 `request_id + items` 的 JSON 均可载入；
- 输出：清单旁边的 `price-result.json`（`PriceResultBatch`，schema_version "1.2"）；
- 诊断：`logs/diagnostics.json`（原始字段名、过滤计数、被剔除候选），不进正式结果。

## 已内置门禁

| 门禁 | 实现 |
|---|---|
| 价格单位门禁 | 数值型价格字段必须在 `PRICE_FIELD_UNITS` 显式登记单位；禁止按数值大小猜"元/分" |
| 商品相关性门禁 | positive_terms 命中其一即相关；hard_excluded_terms 命中即硬拒（熟食/预制/腌制/水饺等） |
| eligible SKU 门槛 | 商品 ID + 名称 + 当前价 + 可解析规格 + 可售库存，五要素齐备才进正式候选；聚合面板节点自动剔除 |
| 价格分类 | 当前价 < 原价 → 促销价（保留原价）；会员价单独记录，不默认当预算价 |
| 只读门禁 | 唯一允许的页面交互是填搜索框回车；命中 cart/checkout/pay/order/coupon 链路即中止（退出码 4） |
| 原子输出 | 先写 tmp 回读校验后才替换正式文件 |
| 效率门禁 | 主词取得 ≥3 个合格候选即停止，不足才查别名（每项最多 3 个词）；候选按商品 ID 去重 |

## 已确认接口字段（2026-08-26，search/searchProduct）

名称 = `name`；当前价 = `price`（字符串、元）；原价 = `origin_price`；会员价 = `vip_price`；
规格 = `net_weight` + `net_weight_unit`（缺失时回退从商品名解析"400g/份"）；
库存 = `today_stockout`（布尔）/ `stock_number`、`station_stock`（数值）。
接口漂移时开开发模式重新采集，更新映射即可，月食 Skill 不需重发。

## 退出码

- `0` 正常完成；`1` 运行失败；`2` 用户未确认登录；`4` 只读门禁触发；`130` 用户取消。

## 目录说明

- `browser-profile/`：浏览器登录会话，只存本机，不要分享或提交；
- `output/`：历史结果与诊断包；
- `logs/`：诊断日志，**不进入月食发布包**；
- `browsers/` / `build/` / `dist/`：构建产物，不进源码包分发。

---

## v1.4 安装程序形态（PRD）

- 数据目录分离：开发态数据在项目目录；冻结态（PyInstaller）数据在
  `%LOCALAPPDATA%\YueshiDingdongHelper\`（browser-profile / output / logs / perf.json），
  程序目录只读。
- 图标：`assets/icon-master.png`（AI 生成母图）→ `icon-1024.png`（裁边留白）→
  `app.ico`（16–256 多尺寸）+ `icon-64.png`（界面顶部）。build_exe.py 以
  `--icon assets/app.ico --add-data assets;assets` 打包。
- 首页为四步式布局（上传区 → 登录+地址确认勾选 → 开始查询 → 结果下载），
  进度经 `app.run(progress_callback=...)` 回报；登录用 `login_only=True`。
- ~~安装程序：Inno Setup~~（第二轮优化起移除，见下）。

---

## v1.6 目录重排（结构优化方案）

- src/ 只放运行时代码；构建工具在 build/；开发入口在 dev/；示例在 examples/；图标在 assets/。
- PyInstaller 临时目录为项目根 _build/（含 dist 中间产物，生成即删）；
  成品「月食叮咚查价助手」文件夹直接放项目根第一层，与入口 bat 并列。
- 唯一入口：根目录「一键生成安装包.bat」→ build/builder_ui.py（依赖安装 →
  build_exe.py → 成品文件夹复制，无安装程序，免安装运行；bat 仅供维护者）。
- dev 模式：`set YUESHI_DEV=1` 后运行 dev/start-gui.vbs。

---

## v1.7 浏览器策略与精简打包（第二轮优化）

- 启动浏览器按 4 级回退：系统 Chrome/Edge 常见安装路径（含 Edge 每用户安装
  路径与 PATH 兜底，`_system_browser_exe`）→ Playwright channel（chrome/msedge）
  → 自带 Chromium → 明确报错提示安装浏览器。
- 默认不再打包 Chromium（包体 1.65GB → ~150MB，Win10/11 自带 Edge 即可）；
  无浏览器环境可在构建前 `set YUESHI_BUNDLE_BROWSER=1` 打自带浏览器大包，
  冻结态经 `PLAYWRIGHT_BROWSERS_PATH=_MEIPASS\browsers` 定位。
- venv 搬至 `%LOCALAPPDATA%\YueshiDingdongHelper\build-venv`；运行期数据
  开发态/冻结态统一写 `%LOCALAPPDATA%\YueshiDingdongHelper`；构建前自动清理
  旧成品目录（含旧命名 -便携版）与 _build，防递归打包。

---

## 源码包结构与构建（方案 §8.4：自 README / 使用说明.txt 并入）

普通用户文档只保留「保留完整文件夹 + 四步操作」；以下内容仅供维护者。

### 目录结构

```
一键生成安装包.bat   构建入口（仅供维护者制作成品；普通用户不运行）
使用说明.txt         普通用户使用说明（随成品文件夹分发）
requirements.txt     运行依赖
src/                 运行时代码（app/gui/config/models/network_capture/normalizer/page_fallback/friendly_errors）
build/               构建工具（builder_ui 图形构建器 / build_exe）
dev/                 开发入口与开发文档（start-gui、DEVELOPMENT.md、测试）
examples/            月食-查价清单-示例.json
assets/              图标（白色像素小狗，16–256 全尺寸 ICO）
```

### 构建

双击「一键生成安装包.bat」：自动装依赖 → 打包 EXE →
成品「月食叮咚查价助手」文件夹直接出现在源码包第一层（与 README 并列）。
交付形态为免安装文件夹：整个文件夹拷给别人，双击里面的图标即可使用。
bat 仅供维护者制作成品；普通用户只接触成品文件夹，不接触 bat、
Python 或任何构建工具。

- 项目文件夹始终干净：虚拟环境在 %LOCALAPPDATA%\YueshiDingdongHelper\build-venv，
  运行期数据（登录态/结果/日志）在 %LOCALAPPDATA%\YueshiDingdongHelper，
  构建中间产物生成即删。
- 默认不打包浏览器：运行时依次查找系统 Chrome/Edge（含每用户安装路径与
  PATH 兜底）→ Playwright channel → 内置浏览器。包体约 150MB。
  无 Chrome/Edge 的目标机器：设 `YUESHI_BUNDLE_BROWSER=1` 再构建即可
  携带内置浏览器（约 600MB）。
- 开发者模式：`set YUESHI_DEV=1` 后运行 `dev/start-gui.vbs`。
- 构建前提：Python 3.11+（安装时勾选 Add python.exe to PATH）。

### round58 界面与导出更新（历史备忘）

- 完成页默认只显示摘要（成功/需处理计数 + "结果已通过格式校验"）；
  点「查看全部结果 ▾」展开可滚动明细，失败项可点击查看原因；
  主按钮固定在底部，清单再长也不会被挤出窗口。
- 窗口可调大小并记忆上次尺寸（不小于 600×440）；明细支持滚轮与
  PageUp/PageDown/Home/End。
- 导出自动带格式自检（E01–E05：schema_version/provider/request_id/
  results 非空/保存后回读校验），普通用户不需要理解这些字段；
  自检不通过时只提示重新保存，字段明细在「设置与帮助 → 导出诊断信息」。
- 精简查价清单支持：清单可只带食材 ID + 需求克数 + 用途约束，
  匹配规则由内置目录快照（1.3.0，含腊制鸡腿/刺身三文鱼/玉米茶/
  组合菜剔除规则）自动展开；清单内同名字段优先。

### 方案 §8 收口（本次）

- §8.1：导入后界面改为自检面板（三状态 + 唯一主按钮「开始查询」）；
  浏览器可用性探测见 `src/gui.py` 的 `browser_available()`。
- §8.2：完成态只显示「查价完成」+ 主按钮「下载结果并返回月食」。
- §8.3：内部错误码 → 用户文案映射在 `src/friendly_errors.py`，
  界面只显示操作建议；内部错误码写 `logs/internal-errors.log`，
  异常原文写 `logs/last-error.txt`。
- §8.4：README.md / 使用说明.txt 面向普通用户，只保留四步操作与
  「保留完整文件夹」提示；构建与开发说明统一收进本文件。
- 回归：`dev/test_ux_friendly_errors.py`。
