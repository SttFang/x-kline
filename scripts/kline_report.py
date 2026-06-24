#!/usr/bin/env python3
"""一条命令把任意 X/Twitter 博主的近一月推文做成自包含的「阅读量 K 线 + 人设」HTML。

流水线（全程内存，只产出最终 HTML）：
  火花 social_twitter API 拉近 N 天原创推文
  → 统计分布蜡烛(box-plot) + 主题阳线榜 + 17 档自媒体人设
  → 注入 assets/template.html → 写出 <handle>-kline.html

数据走火花「推特中转 API」(social_twitter)，需要火花 data-token。
"""
import json, os, sys, time, argparse, statistics, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta

API   = os.environ.get("HUOHUA_API_BASE", "https://api.huohuaapi.cn/v1")
TZ    = timezone(timedelta(hours=8))   # 「单日」按北京时间切
ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "template.html")


# ── token（两个数据源任选其一）──────────────────────────────
def x_token():
    """官方 X API v2 的 Bearer token。"""
    t = os.environ.get("X_BEARER_TOKEN")
    if t: return t
    p = os.path.expanduser("~/.config/x/bearer-token")
    return open(p).read().strip() if os.path.exists(p) else None

def huohua_token():
    """火花 social_twitter 的 data-token。"""
    t = os.environ.get("HUOHUA_DATA_TOKEN")
    if t: return t
    p = os.path.expanduser("~/.config/huohua/data-token")
    return open(p).read().strip() if os.path.exists(p) else None


# ── 数据源 A：官方 X API v2 ────────────────────────────────
X_API = "https://api.twitter.com/2"

def _x_get(path, params):
    url = X_API + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {x_token()}"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 503) and attempt == 0:
                time.sleep(8); continue
            sys.exit(f"X API HTTP {e.code}: {msg}（注意：读取用户推文需要 X API Basic 及以上付费访问）")
        except urllib.error.URLError as e:
            sys.exit(f"连不上 X API：{e.reason}")

def _x_ts(s):
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in s else "%Y-%m-%dT%H:%M:%SZ"
    return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp()

def pull_x(handle, days):
    u = _x_get(f"/users/by/username/{handle}",
               {"user.fields": "public_metrics,profile_image_url,description,created_at,verified"})
    if "data" not in u:
        sys.exit(f"X API 找不到 @{handle}: {json.dumps(u, ensure_ascii=False)[:200]}")
    ud = u["data"]; uid = ud["id"]; pm = ud.get("public_metrics", {})
    pf = {"name": ud.get("name") or handle, "description": ud.get("description", ""),
          "followers": pm.get("followers_count", 0), "statuses_count": pm.get("tweet_count", 0),
          "created_at": ud.get("created_at", ""), "is_blue_verified": bool(ud.get("verified")),
          "profile_picture": ud.get("profile_image_url", "")}
    start = datetime.fromtimestamp(time.time() - days * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, page_token, calls = [], None, 0
    while calls < 20:
        calls += 1
        params = {"max_results": 100, "exclude": "retweets,replies", "start_time": start,
                  "tweet.fields": "public_metrics,created_at,note_tweet"}
        if page_token: params["pagination_token"] = page_token
        resp = _x_get(f"/users/{uid}/tweets", params)
        for t in resp.get("data", []):
            m = t.get("public_metrics", {})
            views = m.get("impression_count")
            if not views: continue                          # 没阅读量(太老/无impression)跳过
            note = (t.get("note_tweet") or {}).get("text")
            txt = (note or t.get("text", "")).replace("\n", " ")[:240]
            rows.append({"id": t["id"], "ts": _x_ts(t["created_at"]), "views": int(views),
                         "fav": m.get("like_count", 0), "rt": m.get("retweet_count", 0),
                         "reply": m.get("reply_count", 0),
                         "url": f"https://x.com/{handle}/status/{t['id']}", "text": txt})
        page_token = resp.get("meta", {}).get("next_token")
        print(f"  X API 第{calls}页: 累计 {len(rows)} 条", file=sys.stderr)
        if not page_token: break
        time.sleep(1)
    rows.sort(key=lambda r: r["ts"])
    return rows, pf


# ── 数据源 B：火花 social_twitter API ──────────────────────
def search(filters, purpose, query=""):
    tk = huohua_token()
    if not tk:
        sys.exit("ERROR: 未找到火花 data-token。设置 HUOHUA_DATA_TOKEN 或写入 ~/.config/huohua/data-token")
    body = json.dumps({"source": "social_twitter", "purpose": purpose,
                       "filters": filters, "query": query,
                       "return": {"format": "json"}}).encode()
    req = urllib.request.Request(f"{API}/search", data=body, method="POST",
        headers={"Authorization": f"Bearer {tk}", "Content-Type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]
            if e.code in (502, 503) and attempt == 0:
                time.sleep(6); continue
            sys.exit(f"火花 API HTTP {e.code}: {msg}")
        except urllib.error.URLError as e:
            sys.exit(f"连不上火花 API：{e.reason}")

def parse_ts(s): return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").timestamp()
def daykey(ts):  return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d")
def pct(sv, p):
    if not sv: return 0
    if len(sv) == 1: return sv[0]
    k = (len(sv) - 1) * p; f = int(k); c = min(f + 1, len(sv) - 1)
    return sv[f] + (sv[c] - sv[f]) * (k - f)

def wan(n):
    """阅读量等大数转中文「万/亿」：399519→39.9万，9590000→959万，1.27e8→1.27亿。"""
    n = round(n or 0)
    if n >= 1e8: return f"{n/1e8:.2f}".rstrip("0").rstrip(".") + "亿"
    if n >= 1e4: return f"{n/1e4:.1f}".rstrip("0").rstrip(".") + "万"
    return str(n)


# ── 1) 拉数据：按可用 token 选数据源（官方 X 优先，火花备选）──
def pull(handle, days, source=None):
    src = source
    if src is None:
        src = "x" if x_token() else ("huohua" if huohua_token() else None)
    if src == "x":
        if not x_token(): sys.exit("指定了 --source x 但未设置 X_BEARER_TOKEN")
        return pull_x(handle, days)
    if src == "huohua":
        return pull_huohua(handle, days)
    sys.exit("没有可用数据源 token：设置 X_BEARER_TOKEN（官方 X API）或 HUOHUA_DATA_TOKEN（火花）")

def pull_huohua(handle, days):
    prof = search({"mode": "user_lookup", "username": handle}, "取博主资料用于K线报告")
    pf = (prof.get("items") or [{}])[0].get("fields", {})
    cutoff = time.time() - days * 86400
    rows, seen, page_token, calls, dry = [], set(), None, 0, 0
    while calls < 25:
        calls += 1
        f = {"mode": "user_posts", "username": handle, "max_pages": 2}
        if page_token: f["page_token"] = page_token
        resp = search(f, f"为@{handle}阅读量K线拉近{days}天推文")
        recent = 0
        for it in resp.get("items", []):
            fl = it.get("fields", {})
            tid = it.get("id", "").replace("tweet:", "")
            if tid in seen: continue
            seen.add(tid)
            dt = fl.get("published_at")
            if not dt: continue
            try: ts = parse_ts(dt)
            except Exception: continue
            txt = it.get("display_text") or ""
            if txt.startswith("RT @"): continue                                  # 转推不算
            if (fl.get("author_username") or handle).lower() != handle.lower():   # 嵌入的别人推不算
                continue
            vc = fl.get("view_count")
            if vc is None: continue
            if ts >= cutoff:
                rows.append({"id": tid, "ts": ts, "views": int(vc),
                             "fav": fl.get("like_count", 0), "rt": fl.get("repost_count", 0),
                             "reply": fl.get("reply_count", 0), "url": fl.get("url", ""),
                             "text": txt.replace("\n", " ")[:240]})
                recent += 1
        meta = resp.get("meta", {})
        page_token = meta.get("next_page_token")
        nd = len(set(daykey(r["ts"]) for r in rows))
        print(f"  call {calls}: +{recent} 条(窗口内), 累计 {len(rows)} 条 / {nd} 天", file=sys.stderr)
        dry = dry + 1 if recent == 0 else 0
        if dry >= 2: break                       # 连续2页没有新窗口内推文 → 翻到头了
        if not meta.get("has_next_page") or not page_token: break
        time.sleep(1.3)
    rows.sort(key=lambda r: r["ts"])
    return rows, pf


# ── 2) 算 K 线 / 人设 ─────────────────────────────────────
def build_kline(rows, pf, handle):
    days = {}
    for r in rows: days.setdefault(daykey(r["ts"]), []).append(r)
    candles, volumes, markers, intraday, median_line = [], [], [], {}, []
    all_top = max(rows, key=lambda r: r["views"]) if rows else None
    UP, DOWN = "#d7352a", "#1b8a5a"
    UP_W, DOWN_W = "rgba(215,53,42,.32)", "rgba(27,138,90,.32)"
    sorted_days = sorted(days)
    unsettled = set(sorted_days[-2:])
    prev_median = None
    TZSHIFT = 8 * 3600

    for d in sorted_days:
        ts_rows = sorted(days[d], key=lambda r: r["ts"])
        vs = sorted(max(r["views"], 1) for r in ts_rows)
        y, m, dd = map(int, d.split("-"))
        t = {"year": y, "month": m, "day": dd}
        hi, lo = vs[-1], vs[0]
        q25, q50, q75 = pct(vs, .25), pct(vs, .5), pct(vs, .75)
        is_uns = d in unsettled
        up = prev_median is None or q50 >= prev_median
        col = (UP_W if up else DOWN_W) if is_uns else (UP if up else DOWN)
        candles.append({"time": t, "open": q25, "close": q75, "high": hi, "low": lo,
                        "color": col, "wickColor": col, "borderColor": col})
        volumes.append({"time": t, "value": len(ts_rows), "color": (UP_W if up else DOWN_W)})
        median_line.append({"time": t, "value": round(q50)})
        prev_median = q50
        top = max(ts_rows, key=lambda r: r["views"])
        if top["views"] >= (all_top["views"] * 0.4 if all_top else 0):
            markers.append({"time": t, "position": "aboveBar", "color": "#e0962a",
                            "shape": "arrowDown", "text": f'★{wan(top["views"])}'})
        pts, last = [], None
        for r in ts_rows:
            sec = int(r["ts"]) + TZSHIFT
            if last is not None and sec <= last: sec = last + 1
            last = sec
            pts.append({"time": sec, "value": r["views"], "id": r["id"], "url": r.get("url", ""),
                        "fav": r["fav"], "rt": r["rt"], "reply": r["reply"],
                        "hhmm": datetime.fromtimestamp(r["ts"], TZ).strftime("%H:%M"), "text": r["text"]})
        intraday[d] = {"points": pts, "q25": round(q25), "median": round(q50), "q75": round(q75),
                       "high": hi, "low": lo, "count": len(ts_rows), "sumViews": sum(vs),
                       "topText": top["text"], "topViews": top["views"], "unsettled": is_uns}

    avatar = (pf.get("profile_picture") or "").replace("_normal", "_400x400")
    profile = {"name": pf.get("name") or handle, "username": handle, "avatar": avatar,
               "bio": pf.get("description", ""), "followers": pf.get("followers", 0),
               "verified": bool(pf.get("is_blue_verified") or pf.get("is_verified")),
               "statuses": pf.get("statuses_count", 0)}

    # 主题阳线榜
    TOPIC_RULES = [
        ("教程实操", ["如何","怎么","教程","步骤","方法","手把手","实操","演示","技巧","用法","教你","实现了","搭建","配置"]),
        ("观点输出", ["我觉得","其实","我认为","本质","真相","值得","道理","建议","应该","不要","误区","为什么","思考"]),
        ("外文转译", ["翻译","编译","原文","来自","一篇","分享一篇","长文","全文","转译","作者说"]),
        ("行业资讯", ["发布","推出","上线","openai","anthropic","google","融资","更新","版本","新模型","最新","刚刚","官宣"]),
        ("工具推荐", ["cursor","claude code","插件","工具","推荐","好用","试了","体验","神器","效率"]),
    ]
    def classify(text):
        tl = (text or "").lower()
        for name, kws in TOPIC_RULES:
            if any(k in tl for k in kws): return name
        return "其他/杂谈"
    BOMB = 100000
    agg = {}
    for r in rows:
        a = agg.setdefault(classify(r["text"]), {"topic": classify(r["text"]), "views": [], "bombs": 0})
        a["views"].append(r["views"])
        if r["views"] >= BOMB: a["bombs"] += 1
    topics = sorted(
        [{"topic": a["topic"], "count": len(a["views"]), "median": round(pct(sorted(a["views"]), .5)),
          "max": max(a["views"]), "total": sum(a["views"]), "bombs": a["bombs"]} for a in agg.values()],
        key=lambda x: -x["median"])
    bomb_count = sum(1 for r in rows if r["views"] >= BOMB)

    # 17 档自媒体人设
    followers = pf.get("followers", 0) or 0
    statuses = pf.get("statuses_count", 0) or 0
    try: age = max(0, datetime.now(timezone.utc).year - int((pf.get("created_at") or "0")[:4]))
    except Exception: age = 0
    vlist = sorted(r["views"] for r in rows)
    median_v = round(pct(vlist, .5)) if vlist else 0
    peak_v = vlist[-1] if vlist else 0
    daily = len(rows) / max(len(days), 1)
    bomb_rate = bomb_count / max(len(rows), 1)
    tot_fav = sum(r["fav"] for r in rows); tot_rt = sum(r["rt"] for r in rows); tot_reply = sum(r["reply"] for r in rows)
    reply_ratio = tot_reply / (tot_fav + 1); rt_ratio = tot_rt / (tot_fav + 1)
    dmeds = [intraday[d]["median"] for d in sorted_days] or [0]
    mean_dm = sum(dmeds) / len(dmeds)
    cv = (statistics.pstdev(dmeds) / mean_dm) if mean_dm > 0 and len(dmeds) > 1 else 0
    trend_up = dmeds[-1] > dmeds[0] * 1.1
    top_topic = topics[0]["topic"] if topics else "其他/杂谈"
    CATALOG = [
        ("👴","钻石老登","老号常青树，发了一堆还能打"), ("🐳","顶流大V","粉丝阅读双高的头部玩家"),
        ("🚀","出圈狂魔","动不动就冲出自己的圈层"), ("🔥","大喷子","评论区天天对线，回复比赞多"),
        ("❤️","点赞收割机","招人喜欢，点赞拿到手软"), ("🍀","转发锦鲤","内容被疯狂自来水转发"),
        ("🎰","爆款赌徒","大起大落，偶尔炸街"), ("🖨️","阅读印钞机","中位高又稳，闷声发大财"),
        ("⚡","日更狂魔","高产似母猪，日更不带停"), ("📘","干货教程区","手把手教学，实操型选手"),
        ("💭","嘴炮哲学家","爱发表观点，输出价值观"), ("🌐","搬运翻译机","搬运翻译外网一手信息"),
        ("📡","行业线人","天天爆料快讯，消息灵通"), ("🌱","冉冉新星","体量还小但数据在涨"),
        ("💪","腰部中坚","中等体量，稳定输出"), ("🗯️","自言自语","发得勤，但暂时没什么人理"),
        ("🌫️","默默无闻","还在等第一个爆款"),
    ]
    def pick():
        if age >= 8 and statuses >= 10000 and median_v >= 15000: return "钻石老登", f"{age}年老号、发了{wan(statuses)}条，中位还有{wan(median_v)}阅读"
        if followers >= 300000 and median_v >= 30000: return "顶流大V", f"{wan(followers)}粉、单条中位{wan(median_v)}阅读"
        if bomb_rate >= 0.3 or peak_v >= followers > 0: return "出圈狂魔", f"{bomb_count}条破10w、最高{wan(peak_v)}远超粉丝盘"
        if reply_ratio >= 0.5 and tot_reply >= 2000: return "大喷子", f"回复{tot_reply}>点赞{tot_fav}，评论区主战场"
        if tot_fav >= 5000 and reply_ratio < 0.15 and rt_ratio < 0.3: return "点赞收割机", f"点赞占绝对大头({tot_fav})，争议小"
        if rt_ratio >= 0.6: return "转发锦鲤", f"转发{tot_rt}/点赞{tot_fav}，自来水强"
        if cv >= 0.8: return "爆款赌徒", f"日中位波动剧烈(CV={cv:.1f})，偶尔炸街"
        if median_v >= 30000 and cv < 0.4: return "阅读印钞机", f"中位{wan(median_v)}且稳(CV={cv:.1f})"
        if daily >= 8: return "日更狂魔", f"日均{daily:.1f}条"
        if top_topic == "教程实操": return "干货教程区", f"主发教程实操，中位{wan(median_v)}"
        if top_topic == "观点输出": return "嘴炮哲学家", "主发观点输出"
        if top_topic == "外文转译": return "搬运翻译机", "主发外文转译"
        if top_topic == "行业资讯": return "行业线人", "主发行业资讯/快讯"
        if trend_up and followers < 50000: return "冉冉新星", "体量小但中位在上行"
        if 10000 <= followers and median_v >= 5000: return "腰部中坚", f"{wan(followers)}粉、稳定输出"
        if daily >= 4 and median_v < 3000: return "自言自语", f"日均{daily:.1f}条但中位仅{median_v}"
        return "默默无闻", "中位阅读低、暂无破10w爆款"
    pick_name, pick_why = pick()
    emoji = next((e for e, n, _ in CATALOG if n == pick_name), "🌫️")
    identity = {"name": pick_name, "emoji": emoji, "label": f"{emoji} {pick_name}", "why": pick_why,
                "catalog": [{"emoji": e, "name": n, "desc": d, "matched": n == pick_name} for e, n, d in CATALOG]}

    highlights = [{"date": daykey(r["ts"]), "hhmm": datetime.fromtimestamp(r["ts"], TZ).strftime("%H:%M"),
                   "views": r["views"], "fav": r["fav"], "rt": r["rt"], "reply": r["reply"],
                   "text": r["text"], "url": r.get("url", "")}
                  for r in sorted(rows, key=lambda r: -r["views"])[:6]]

    medians = [intraday[d]["median"] for d in sorted_days if not intraday[d]["unsettled"]]
    first_med = medians[0] if medians else 0
    last_med = medians[-1] if medians else 0
    peak = max((c["high"] for c in candles), default=0)
    peak_day = next((d for d in sorted_days if any(r["views"] == peak for r in days[d])), "")
    trend = "震荡上行" if last_med > first_med * 1.05 else "高位回落" if last_med < first_med * 0.95 else "横盘整理"
    summary = (f"近 {len(days)} 个交易日，单条阅读量中位数{trend}；全期最高单条 {wan(peak)}"
               + (f"（{peak_day}）" if peak_day else "") + f"，日均 {len(rows)//max(len(days),1)} 条。")

    return {
        "handle": handle, "profile": profile, "tz": "Asia/Shanghai (UTC+8)",
        "priceLabel": "推文阅读量", "range": [sorted_days[0], sorted_days[-1]] if days else [],
        "totalTweets": len(rows), "totalDays": len(days), "peakViews": peak, "peakDay": peak_day,
        "firstClose": first_med, "lastClose": last_med, "unsettledDays": list(unsettled),
        "summary": summary, "candles": candles, "volumes": volumes, "medianLine": median_line,
        "markers": markers, "intraday": intraday, "topics": topics, "bombCount": bomb_count,
        "bombThreshold": BOMB, "identity": identity, "highlights": highlights,
    }


# ── 3) 渲染 ───────────────────────────────────────────────
def render_str(kline):
    tpl = open(ASSET, encoding="utf-8").read()
    return tpl.replace("__KLINE_JSON__", json.dumps(kline, ensure_ascii=False))

def render(kline, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_str(kline))

def generate(handle, days=31, source=None):
    """完整流水线，返回 (html 字符串, kline dict)。供 CLI 和 Web UI 复用。"""
    handle = handle.lstrip("@")
    rows, pf = pull(handle, days, source)
    if not rows:
        raise ValueError("没有取到带阅读量的原创推文")
    kline = build_kline(rows, pf, handle)
    return render_str(kline), kline


def main():
    ap = argparse.ArgumentParser(description="生成 X/Twitter 博主阅读量 K 线 + 人设 HTML 报告")
    ap.add_argument("handle", help="X/Twitter 用户名（带不带 @ 都行）")
    ap.add_argument("--days", type=int, default=31, help="回看天数（默认 31）")
    ap.add_argument("--out", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--source", choices=["x", "huohua"], default=None,
                    help="数据源：x=官方 X API，huohua=火花；默认按可用 token 自动选（X 优先）")
    a = ap.parse_args()
    handle = a.handle.lstrip("@")
    print(f"拉取 @{handle} 近 {a.days} 天推文…", file=sys.stderr)
    rows, pf = pull(handle, a.days, a.source)
    if not rows:
        sys.exit("没有取到带阅读量的原创推文（账号可能近期无原创推文，或老推文无 view_count 字段）")
    kline = build_kline(rows, pf, handle)
    os.makedirs(a.out, exist_ok=True)
    out_path = os.path.join(a.out, f"{handle}-kline.html")
    render(kline, out_path)
    print(f"✅ 生成 {out_path}")
    print(f"   {kline['totalTweets']} 条推文 / {kline['totalDays']} 天 / 人设：{kline['identity']['label']}")


if __name__ == "__main__":
    main()
