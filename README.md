<p align="center">
  <img src="docs/icon.webp" width="112" alt="X 线">
</p>

<h1 align="center">X 线 · X-Kline</h1>

<p align="center"><em>给你的推特号拍个 X 光片：阅读量 K 线 + 人设鉴定。</em></p>

<p align="center">
  <img src="docs/full.webp" width="600" alt="X 线完整报告：阅读量 K 线 + 爆款时刻 + 复盘 + 分享海报">
</p>

把任意 X/Twitter 博主近一个月的推文做成一张**阅读量 K 线 + 自媒体人设**报告。以单条阅读量为价、统计分布蜡烛(box-plot)画日 K，自动算出主题阳线榜、爆款时刻、17 档人设（钻石老登 / 大喷子 / 出圈狂魔…），并生成可一键发到 X 的分享海报。

数据来自 [火花 · 推特 API](https://huohuaapi.com/data-sources/social-twitter)（social_twitter）。

两种用法：**命令行**（出一个 HTML 文件）或 **Web UI**（输入用户名即看）。

## 准备：数据源 token（两选一）

阅读量 = 推文的 impression（曝光）。两个数据源都能取，按可用 token 自动选（X 优先），也可用 `--source` 指定。

### 方式一（推荐）：官方 X API

最标准、最权威，直连 X。需要 [X API](https://developer.x.com) 的 **Bearer Token**（读取用户推文需 Basic 及以上付费档；`public_metrics.impression_count` 即阅读量）：

```bash
export X_BEARER_TOKEN='你的 Bearer Token'
# 或写入文件（权限 600）
mkdir -p ~/.config/x && printf '%s' '你的 Bearer Token' > ~/.config/x/bearer-token && chmod 600 ~/.config/x/bearer-token
```

### 方式二：火花 API（便宜、国内直连，免折腾 X 付费档）

懒得开通 X API 付费档的话，也可以用[火花 · 推特 API](https://huohuaapi.com/data-sources/social-twitter)（按次计费，国内直连优化线路）。去 https://huohuaapi.com/console/data-access 复制 token：

```bash
export HUOHUA_DATA_TOKEN='你的token'
# 或写入文件（权限 600）
mkdir -p ~/.config/huohua && printf '%s' '你的token' > ~/.config/huohua/data-token && chmod 600 ~/.config/huohua/data-token
```

> token 是计费凭证：只放环境变量或独立文件，**不要**提交进仓库或下发到浏览器。

## 用法 A · 命令行

```bash
python3 scripts/kline_report.py dotey                 # 出 dotey-kline.html（自动选数据源）
python3 scripts/kline_report.py @elonmusk --days 31 --out ./reports
python3 scripts/kline_report.py dotey --source x      # 强制用官方 X API
python3 scripts/kline_report.py dotey --source huohua # 强制用火花
```

把报告完整导出成一张长图（需 Chrome；装了 ImageMagick 会自动去白边）：

```bash
python3 scripts/export_png.py dotey-kline.html        # → dotey-kline.png
```

## 用法 B · Web UI（零依赖）

```bash
python3 webapp/server.py            # 打开 http://127.0.0.1:8787
```

输入用户名 → 后端拉数据、算 K 线、判人设 → 浏览器直接出报告。token 只待在服务器端。

## 报告内容

- **阅读量 K 线**：日 K；实体=当天单条阅读量四分位区间，上影=爆款、下影=哑火，红涨绿跌按中位数日环比；对数轴；点蜡烛看当天日内。
- **账号人设**：17 档里按数据自动判定一个。
- **你的流量密码**：哪类内容（教程/观点/转译/资讯/工具）最能打。
- **爆款时刻 + 代表作 + 分享海报**。

## 案例 · 不同博主，不同人设

人设按账号年龄、发推量、阅读中位、互动结构、数据波动等从 17 档里自动判定，每个号都不一样：

| | | |
|:--:|:--:|:--:|
| <img src="docs/cases/tiance.webp" width="230"><br>**@Leobai825**<br>🚀 出圈狂魔 | <img src="docs/cases/dotey.webp" width="230"><br>**@dotey**<br>👴 钻石老登 | <img src="docs/cases/aigclink.webp" width="230"><br>**@aigclink**<br>💪 腰部中坚 |

## 作为 AI Agent Skill

本目录同时是一个 Claude / OpenClaw skill（见 `SKILL.md`）。把目录放进 agent 的 skills 目录，agent 即可"给个用户名就生成报告"。

## 结构

```
.
├── SKILL.md                  # AI agent 技能说明书
├── README.md                 # 给人看的说明（本文件）
├── scripts/kline_report.py   # 流水线：拉数据(X API / 火花)→算K线/人设→渲染
├── scripts/export_png.py     # 把报告 HTML 导出成整张长图
├── assets/template.html      # 报告模板
└── webapp/server.py          # Web UI（标准库 http.server）
```

## 约束

- 只统计有阅读量(impression)的**原创**推文；很老的推文（约 2023 前）无阅读量，会跳过。
- 「单日」按北京时间(UTC+8)切；近 2 天标「未收盘」。
- 阅读量是抓取时刻的累计值，非发布当天值。
- 官方 X API 读取用户推文需 Basic 及以上付费档；火花按次计费。两者均自备 token、自付费。

## License

MIT
