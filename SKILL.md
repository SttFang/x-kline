---
name: x-kline
description: X 线（X-Kline）——给推特号拍个 X 光片。把任意 X/Twitter 博主近一个月的推文做成一张自包含的「阅读量 K 线 + 自媒体人设鉴定」HTML 报告。以单条阅读量为价、统计分布蜡烛(box-plot)画日 K，自动算出主题阳线榜、爆款时刻、17 档人设(钻石老登/大喷子/出圈狂魔…)，并生成可一键发到 X、导流到火花推特 API 的分享海报。数据走火花 social_twitter API。当用户想给某个推特博主做数据复盘、战报、人设测评、可分享卡片时使用。
version: 1.0.0
metadata: {"requires":{"env":["HUOHUA_DATA_TOKEN"],"bins":["python3"]},"primaryEnv":"HUOHUA_DATA_TOKEN","dataSource":"https://huohuaapi.com/data-sources/social-twitter"}
---

# X 线 · 阅读量 K 线 + 人设鉴定

输入一个 X/Twitter 用户名，产出一张**双击即看、无需联网构建**的 HTML 报告（图表库走 CDN，数据内联）。

## 产出内容
- **阅读量 K 线**：一天一根日 K。实体=当天单条阅读量四分位区间(中间50%)，上影=爆款、下影=哑火，红涨绿跌按中位数日环比；Y 轴对数；点蜡烛弹出当天日内折线。
- **账号人设**：按账号年龄、发推量、阅读中位、互动结构、波动等数据，从 17 档里自动判定一个（如 👴 钻石老登 / 🔥 大喷子 / 🚀 出圈狂魔）。
- **你的流量密码**：按内容形式（教程/观点/转译/资讯/工具）排出「哪类最能打」。
- **爆款时刻 + 代表作**：全期 Top 推文。
- **分享海报**：竖版，可一键发到 X、下载 PNG，CTA 导流到火花推特 API。

## 第一步：配置火花 data-token

数据来自火花「推特中转 API」(social_twitter)。按顺序取 token，找到即用：

1. 环境变量 `HUOHUA_DATA_TOKEN`；
2. 文件 `~/.config/huohua/data-token`（权限 600）。

都没有时，去 https://huohuaapi.com/console/data-access 复制 token，然后：

```bash
mkdir -p ~/.config/huohua && printf '%s' '<你的token>' > ~/.config/huohua/data-token && chmod 600 ~/.config/huohua/data-token
```

token 是计费凭证：只放独立文件或环境变量，不要写进 shell rc、代码仓库或任何会被提交的文件；不要明文打印到日志。

## 第二步：生成报告

```bash
python3 {baseDir}/scripts/kline_report.py <用户名> [--days 31] [--out 输出目录]
```

例子：

```bash
python3 {baseDir}/scripts/kline_report.py dotey
python3 {baseDir}/scripts/kline_report.py @elonmusk --days 31 --out ./reports
```

- 用户名带不带 `@` 都行。
- 默认回看 31 天、输出到当前目录，文件名 `<用户名>-kline.html`。
- 跑完会打印路径和判定到的人设。用浏览器打开该 HTML 即可。

## 工作原理
`kline_report.py` 一步到位：火花 `social_twitter` API 拉近 N 天**原创**推文（自动过滤转推/嵌入推）→ 内存里算出蜡烛/阳线榜/人设/海报数据 → 注入 `assets/template.html` → 写出单文件 HTML。无中间文件。

## 注意
- 只统计**有 view_count 的原创推文**；很老的推文(约 2023 前)X 不返回阅读量，会被跳过。
- 「单日」按北京时间(UTC+8)切；近 2 天标「未收盘」（阅读量还在累积）。
- 阅读量是抓取时刻的累计快照，不是发布当天值。
- 每次调用按火花计费规则扣费（user_lookup + 若干页 user_posts）。
- 人设/阳线榜的判定阈值和关键词在 `scripts/kline_report.py` 顶部，可按需调。
