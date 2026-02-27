#!/usr/bin/env python3
"""
Daily Digest Publisher
Usage: python publish.py --type news|radar --title "标题" --content "内容..."
Generates HTML post, updates index.html, commits and pushes to GitHub Pages.
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
SITE_DIR = Path(__file__).parent
POSTS_DIR = SITE_DIR / "posts"
POSTS_DIR.mkdir(exist_ok=True)

# ── HTML escaping ──────────────────────────────────────────────
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ── Minimal markdown → HTML (headings, bold, bullets, hr, links) ──
def md_to_html(text: str) -> str:
    lines = text.split("\n")
    out, in_ul = [], False
    for line in lines:
        # heading
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            level = len(m.group(1)); content = inline(m.group(2))
            out.append(f"<h{level}>{content}</h{level}>")
            continue
        # hr
        if re.match(r'^---+\s*$', line):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append("<hr>"); continue
        # bullet
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        # numbered
        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        # blank
        if not line.strip():
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(""); continue
        # paragraph
        if in_ul: out.append("</ul>"); in_ul = False
        out.append(f"<p>{inline(line)}</p>")
    if in_ul: out.append("</ul>")
    return "\n".join(out)

def inline(s: str) -> str:
    # bold **text** or __text__
    s = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", s)
    # link [text](url)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2" target="_blank">\1</a>', s)
    # bare urls
    s = re.sub(r'(?<!["\'>])(https?://\S+)', r'<a href="\1" target="_blank">\1</a>', s)
    return s

# ── Generate post HTML ─────────────────────────────────────────
POST_TMPL = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — 每日汇总</title>
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>
<nav>
  <a class="logo" href="../index.html">📰 每日<span>汇总</span></a>
  <a href="../index.html">首页</a>
  <div class="spacer"></div>
  <span class="tag">AI 自动生成</span>
</nav>
<div class="post-header">
  <div class="container" style="padding-top:0;padding-bottom:0">
    <div class="breadcrumb"><a href="../index.html">首页</a> / {type_label}</div>
    <h1>{title}</h1>
    <div class="post-meta">
      <span class="card-type {type_key}">{type_label}</span>
      <span>📅 {date_fmt}</span>
      <span>⏱ AI 自动生成</span>
    </div>
  </div>
</div>
<div class="container">
  <div class="post-body">
{body}
  </div>
</div>
<footer>
  © 每日汇总 · AI 自动生成 · <a href="https://github.com/sunh3997-eng/daily-digest">GitHub</a>
</footer>
</body>
</html>
"""

def write_post(slug: str, title: str, type_key: str, date: datetime, content: str) -> Path:
    type_label = "每日早报" if type_key == "news" else "商机雷达"
    date_fmt = date.strftime("%Y年%m月%d日 %H:%M")
    body = md_to_html(content)
    html = POST_TMPL.format(
        title=esc(title), type_key=type_key, type_label=type_label,
        date_fmt=date_fmt, body=body
    )
    path = POSTS_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    print(f"✅ Post written: {path}")
    return path

# ── Load/save posts index ──────────────────────────────────────
INDEX_JSON = SITE_DIR / "posts.json"

def load_index():
    if INDEX_JSON.exists():
        return json.loads(INDEX_JSON.read_text())
    return []

def save_index(posts):
    INDEX_JSON.write_text(json.dumps(posts, ensure_ascii=False, indent=2))

# ── Regenerate index.html ──────────────────────────────────────
INDEX_TMPL = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日汇总 — AI 生成的早报与商机</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<nav>
  <a class="logo" href="index.html">📰 每日<span>汇总</span></a>
  <a href="#" onclick="filter('all');return false">全部</a>
  <a href="#" onclick="filter('news');return false">早报</a>
  <a href="#" onclick="filter('radar');return false">商机</a>
  <div class="spacer"></div>
  <span class="tag">AI 自动生成</span>
</nav>
<div class="hero">
  <h1>📰 每日汇总</h1>
  <p>每天 08:00 早报 · 09:00 商机雷达 · 全部由 AI 自动生成</p>
</div>
<div class="container">
  <div class="filter-tabs">
    <button class="active" onclick="filter('all')">📋 全部</button>
    <button onclick="filter('news')">🌅 每日早报</button>
    <button onclick="filter('radar')">💡 商机雷达</button>
  </div>
  <div class="cards" id="cards">
{cards}
  </div>
</div>
<footer>
  © 每日汇总 · AI 自动生成 · 最后更新：{updated} · <a href="https://github.com/sunh3997-eng/daily-digest">GitHub</a>
</footer>
<script>
function filter(type) {{
  document.querySelectorAll('.filter-tabs button').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.card').forEach(c => {{
    c.style.display = (type === 'all' || c.dataset.type === type) ? '' : 'none';
  }});
}}
</script>
</body>
</html>
"""

CARD_TMPL = """\
    <a class="card" href="posts/{slug}.html" data-type="{type_key}">
      <div class="card-meta">
        <span class="card-type {type_key}">{type_label}</span>
        <span class="card-date">{date_fmt}</span>
      </div>
      <h2>{title}</h2>
      <p>{summary}</p>
    </a>"""

def regen_index(posts):
    cards_html = "\n".join(
        CARD_TMPL.format(
            slug=p["slug"], type_key=p["type"], type_label=p["type_label"],
            date_fmt=p["date_fmt"], title=esc(p["title"]), summary=esc(p.get("summary",""))
        )
        for p in posts
    ) or '    <div class="empty"><div class="icon">📭</div><p>暂无内容</p></div>'
    updated = datetime.now(CST).strftime("%Y-%m-%d %H:%M CST")
    (SITE_DIR / "index.html").write_text(
        INDEX_TMPL.format(cards=cards_html, updated=updated),
        encoding="utf-8"
    )
    print("✅ index.html regenerated")

# ── Git push ───────────────────────────────────────────────────
def git_push(message: str):
    cmds = [
        ["git", "-C", str(SITE_DIR), "add", "-A"],
        ["git", "-C", str(SITE_DIR), "commit", "-m", message],
        ["git", "-C", str(SITE_DIR), "push", "-u", "origin", "main"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in r.stdout + r.stderr:
            print(f"⚠️  {' '.join(cmd)}\n{r.stderr}", file=sys.stderr)
        else:
            print(r.stdout.strip() or f"✅ {cmd[2]}")

# ── Main ───────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["news","radar"], required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--content", default=None)
    ap.add_argument("--content-file", default=None, help="Read content from file")
    ap.add_argument("--no-push", action="store_true", help="Skip git push (local test)")
    args = ap.parse_args()

    if args.content_file:
        args.content = Path(args.content_file).read_text(encoding="utf-8")
    if not args.content:
        print("❌ --content or --content-file required", file=sys.stderr); sys.exit(1)

    now = datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d")
    slug = f"{args.type}-{date_str}"
    type_label = "每日早报" if args.type == "news" else "商机雷达"
    date_fmt = now.strftime("%Y年%m月%d日")

    # Extract summary (first non-empty, non-heading line)
    summary = ""
    for line in args.content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            summary = re.sub(r'[#*_\[\]`]', '', line)[:100]
            break

    # Write post
    write_post(slug, args.title, args.type, now, args.content)

    # Update index
    posts = load_index()
    # Remove duplicate for same slug (re-run same day overwrites)
    posts = [p for p in posts if p["slug"] != slug]
    posts.insert(0, {
        "slug": slug, "type": args.type, "type_label": type_label,
        "title": args.title, "date_fmt": date_fmt, "summary": summary,
        "ts": now.isoformat()
    })
    save_index(posts)
    regen_index(posts)

    if not args.no_push:
        git_push(f"📰 {type_label} {date_str}: {args.title}")
    else:
        print("⏭  Skipped git push (--no-push)")

if __name__ == "__main__":
    main()
