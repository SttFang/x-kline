#!/usr/bin/env python3
"""把生成的报告 HTML 完整导出成一张长图 PNG。

依赖：Chrome / Chromium（必需，用来跑图表 JS）；ImageMagick（可选，有则自动去白边）。

  python3 scripts/export_png.py <报告.html> [输出.png]
  python3 scripts/export_png.py dotey-kline.html      # → dotey-kline.png
"""
import os, sys, shutil, subprocess

def find_chrome():
    cands = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for c in cands:
        if os.path.exists(c): return c
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(n)
        if p: return p
    sys.exit("未找到 Chrome/Chromium，导出图片需要它（HTML 报告本身不依赖）")

def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python3 export_png.py <报告.html> [输出.png]")
    html = os.path.abspath(sys.argv[1])
    if not os.path.exists(html):
        sys.exit(f"找不到文件: {html}")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(html)[0] + ".png"
    chrome = find_chrome()
    mg = shutil.which("magick") or shutil.which("convert")
    raw = (out + ".raw.png") if mg else out

    # 高窗口一次性截全（虚拟时间让图表 JS 跑完），多余白边交给 ImageMagick 去
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", "--window-size=1180,4200",
                    "--virtual-time-budget=10000", "--screenshot=" + raw,
                    "file://" + html], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if mg and raw != out:
        subprocess.run([mg, raw, "-fuzz", "3%", "-trim", "+repage", out], check=True)
        os.remove(raw)
        print(f"✅ 完整长图（已去白边）→ {out}")
    else:
        print(f"✅ 完整长图 → {out}（装了 ImageMagick 可自动去白边）")

if __name__ == "__main__":
    main()
