#!/usr/bin/env python3
"""Twitter K 线 · Web UI（零依赖，纯标准库）。

把 skill 包成一个可点的网页：输入用户名 → 后端跑流水线 → 返回 K线/人设报告。
火花 data-token 只待在服务器端（env HUOHUA_DATA_TOKEN 或 ~/.config/huohua/data-token），
永不下发到浏览器。

  python3 webapp/server.py            # 默认 http://127.0.0.1:8787
  PORT=9000 python3 webapp/server.py
"""
import os, sys, html, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import kline_report as K

PORT = int(os.environ.get("PORT", "8787"))

LANDING = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>X 线 · 给你的推特号拍个 X 光片</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>body{background:radial-gradient(700px 360px at 85% -8%,#fdeede 0,rgba(253,238,222,0) 60%),#f2f0e9}</style></head>
<body class="text-[#1a1916] font-sans antialiased min-h-screen flex items-center justify-center px-5">
<div class="w-full max-w-md text-center">
  <div class="text-5xl mb-3">🩻</div>
  <h1 class="text-4xl font-extrabold tracking-tight">X 线</h1>
  <p class="text-stone-500 mt-2">给你的推特号拍个 X 光片——近一个月阅读量做成 K 线，测测你是哪种博主人设。</p>
  <form action="/report" method="get" class="mt-7 bg-white rounded-2xl shadow-lg ring-1 ring-black/5 p-5">
    <div class="flex items-center gap-2 bg-stone-100 rounded-xl px-3">
      <span class="text-stone-400 font-bold">@</span>
      <input name="handle" required autofocus placeholder="用户名，如 dotey"
        class="flex-1 bg-transparent py-3 outline-none text-lg" />
    </div>
    <button class="w-full mt-3 bg-[#d7352a] text-white font-bold rounded-xl py-3 hover:brightness-110 active:scale-95 transition">
      生成我的 K 线 →
    </button>
    <p class="text-xs text-stone-400 mt-3">拉取+计算约需 30–60 秒，请稍候</p>
  </form>
  <p class="text-xs text-stone-400 mt-5">数据来自 <a class="underline" href="https://huohuaapi.com/data-sources/social-twitter" target="_blank">火花 · 推特 API</a></p>
</div></body></html>"""

def page(title, body):
    return (f"<!doctype html><meta charset='utf-8'><title>{title}</title>"
            "<script src='https://cdn.tailwindcss.com'></script>"
            "<body class='font-sans bg-[#f2f0e9] text-[#1a1916] min-h-screen flex items-center justify-center px-5'>"
            f"<div class='text-center max-w-md'>{body}</div></body>")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # 静默，避免把 query 打进日志

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            return self._send(200, LANDING)
        if u.path == "/report":
            q = urllib.parse.parse_qs(u.query)
            handle = (q.get("handle", [""])[0] or "").strip().lstrip("@")
            days = int(q.get("days", ["31"])[0] or 31)
            if not handle:
                return self._send(400, page("缺少用户名", "<h1 class='text-xl font-bold'>请填用户名</h1><a href='/' class='text-[#d7352a] underline'>返回</a>"))
            try:
                report_html, kline = K.generate(handle, days)
            except ValueError as e:
                return self._send(404, page("没数据", f"<div class='text-5xl mb-3'>🌫️</div><h1 class='text-xl font-bold'>@{html.escape(handle)} 没生成成功</h1><p class='text-stone-500 mt-2'>{html.escape(str(e))}（账号可能近期无原创推文，或老推文无阅读量）</p><a href='/' class='inline-block mt-4 text-[#d7352a] underline'>换一个</a>"))
            except SystemExit as e:
                return self._send(502, page("上游错误", f"<h1 class='text-xl font-bold'>数据源出错</h1><p class='text-stone-500 mt-2'>{html.escape(str(e))}</p><a href='/' class='text-[#d7352a] underline'>返回</a>"))
            return self._send(200, report_html)
        self._send(404, page("404", "<a href='/' class='text-[#d7352a] underline'>返回首页</a>"))

def main():
    # 启动前确认至少有一个数据源 token（只检查存在，不打印）
    if not (K.x_token() or K.huohua_token()):
        print("未找到数据源 token：设置 X_BEARER_TOKEN（官方 X API）或 HUOHUA_DATA_TOKEN（火花）")
        sys.exit(1)
    src = "官方 X API" if K.x_token() else "火花"
    print(f"▶ X 线 Web UI: http://127.0.0.1:{PORT}（数据源：{src}）", file=sys.stderr)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()

if __name__ == "__main__":
    main()
