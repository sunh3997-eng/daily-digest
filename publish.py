#!/usr/bin/env python3
"""
Daily Digest Publisher — Bilingual (zh/en)
Usage:
  python publish.py --type news|radar \
    --title-zh "中文标题" --title-en "English Title" \
    --content-zh-file /tmp/zh.txt \
    --content-en-file /tmp/en.txt
"""
import argparse, json, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
SITE_DIR = Path(__file__).parent
POSTS_DIR = SITE_DIR / "posts"
POSTS_DIR.mkdir(exist_ok=True)

# ── Helpers ────────────────────────────────────────────────────
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def md_to_html(text: str) -> str:
    lines = text.split("\n")
    out, in_ul = [], False
    for line in lines:
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>"); continue
        if re.match(r'^---+\s*$', line):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append("<hr>"); continue
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<li>{inline(m.group(1))}</li>"); continue
        if not line.strip():
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(""); continue
        if in_ul: out.append("</ul>"); in_ul = False
        out.append(f"<p>{inline(line)}</p>")
    if in_ul: out.append("</ul>")
    return "\n".join(out)

def inline(s: str) -> str:
    s = re.sub(r'\*\*(.+?)\*\*|__(.+?)__',
               lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", s)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)',
               r'<a href="\2" target="_blank">\1</a>', s)
    s = re.sub(r'(?<!["\'>])(https?://\S+)',
               r'<a href="\1" target="_blank">\1</a>', s)
    return s

def first_line(text: str) -> str:
    for line in text.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            return re.sub(r'[#*_\[\]`]', '', line)[:120]
    return ""

# ── Post HTML template ─────────────────────────────────────────
POST_TMPL = """\
<!DOCTYPE html>
<html lang="zh-CN" data-lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_en} / {title_zh} — Daily Digest</title>
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>
<nav>
  <a class="logo" href="../index.html">📰 <span class="zh">每日</span><span class="en">Daily</span><span style="color:var(--accent)"><span class="zh">汇总</span><span class="en">Digest</span></span></a>
  <a href="../index.html"><span class="zh">首页</span><span class="en">Home</span></a>
  <div class="spacer"></div>
  <div class="lang-switcher">
    <button class="lang-btn" data-l="zh" onclick="setLang('zh')">中文</button>
    <button class="lang-btn active" data-l="en" onclick="setLang('en')">EN</button>
  </div>
</nav>
<div class="post-header">
  <div class="container" style="padding-top:0;padding-bottom:0">
    <div class="breadcrumb">
      <a href="../index.html"><span class="zh">首页</span><span class="en">Home</span></a>
      / <span class="zh">{type_label_zh}</span><span class="en">{type_label_en}</span>
    </div>
    <h1>
      <span class="zh">{title_zh}</span>
      <span class="en">{title_en}</span>
    </h1>
    <div class="post-meta">
      <span class="card-type {type_key}">
        <span class="zh">{type_label_zh}</span><span class="en">{type_label_en}</span>
      </span>
      <span>📅 <span class="zh">{date_fmt_zh}</span><span class="en">{date_fmt_en}</span></span>
      <span>⏱ <span class="zh">AI 自动生成</span><span class="en">AI Generated</span></span>
    </div>
  </div>
</div>
<div class="container">
  <div class="post-body">
    <div class="zh">{body_zh}</div>
    <div class="en">{body_en}</div>
  </div>
</div>
<footer>
  © Daily Digest · AI Generated ·
  <a href="https://github.com/sunh3997-eng/daily-digest">GitHub</a>
</footer>
<script>
function setLang(l) {{
  document.documentElement.dataset.lang = l;
  localStorage.setItem('digest-lang', l);
  document.querySelectorAll('.lang-btn').forEach(function(b) {{
    b.classList.toggle('active', b.dataset.l === l);
  }});
}}
(function() {{
  var saved = localStorage.getItem('digest-lang') || 'en';
  setLang(saved);
}})();
</script>
</body>
</html>
"""

def write_post(slug, title_zh, title_en, type_key, date, content_zh, content_en):
    type_label_zh = "每日早报" if type_key == "news" else "商机雷达"
    type_label_en = "Daily Briefing" if type_key == "news" else "Opportunity Radar"
    date_fmt_zh = date.strftime("%Y年%m月%d日 %H:%M")
    date_fmt_en = date.strftime("%B %d, %Y %H:%M CST")
    body_zh = md_to_html(content_zh)
    body_en = md_to_html(content_en) if content_en else "<p><em>English version not available.</em></p>"
    html = POST_TMPL.format(
        title_zh=esc(title_zh), title_en=esc(title_en),
        type_key=type_key, type_label_zh=type_label_zh, type_label_en=type_label_en,
        date_fmt_zh=date_fmt_zh, date_fmt_en=date_fmt_en,
        body_zh=body_zh, body_en=body_en
    )
    path = POSTS_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    print(f"✅ Post written: {path}")
    return path

# ── Index ──────────────────────────────────────────────────────
INDEX_JSON = SITE_DIR / "posts.json"

def load_index():
    return json.loads(INDEX_JSON.read_text()) if INDEX_JSON.exists() else []

def save_index(posts):
    INDEX_JSON.write_text(json.dumps(posts, ensure_ascii=False, indent=2))

INDEX_TMPL = """\
<!DOCTYPE html>
<html lang="zh-CN" data-lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Digest / 每日汇总 — AI Generated</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<nav>
  <a class="logo" href="index.html">📰 <span class="zh">每日</span><span class="en">Daily</span><span style="color:var(--accent)"><span class="zh">汇总</span><span class="en">Digest</span></span></a>
  <a href="#" onclick="filterType('all');return false"><span class="zh">全部</span><span class="en">All</span></a>
  <a href="#" onclick="filterType('news');return false"><span class="zh">早报</span><span class="en">Briefing</span></a>
  <a href="#" onclick="filterType('radar');return false"><span class="zh">商机</span><span class="en">Radar</span></a>
  <div class="spacer"></div>
  <div class="lang-switcher">
    <button class="lang-btn" data-l="zh" onclick="setLang('zh')">中文</button>
    <button class="lang-btn active" data-l="en" onclick="setLang('en')">EN</button>
  </div>
</nav>
<div class="hero">
  <h1>📰 <span class="zh">每日汇总</span><span class="en">Daily Digest</span></h1>
  <p>
    <span class="zh">每天 08:00 早报 · 09:00 商机雷达 · 全部由 AI 自动生成</span>
    <span class="en">08:00 Daily Briefing · 09:00 Opportunity Radar · All AI Generated</span>
  </p>
</div>
<div class="container">
  <div class="filter-tabs">
    <button class="active" onclick="filterType('all')">
      <span class="zh">📋 全部</span><span class="en">📋 All</span>
    </button>
    <button onclick="filterType('news')">
      <span class="zh">🌅 每日早报</span><span class="en">🌅 Daily Briefing</span>
    </button>
    <button onclick="filterType('radar')">
      <span class="zh">💡 商机雷达</span><span class="en">💡 Opportunity Radar</span>
    </button>
  </div>
  <div class="cards" id="cards">
{cards}
  </div>
</div>
<footer>
  © Daily Digest · AI Generated ·
  <span class="zh">最后更新：{updated}</span>
  <span class="en">Last updated: {updated}</span>
  · <a href="https://github.com/sunh3997-eng/daily-digest">GitHub</a>
</footer>
<script>
function setLang(l) {{
  document.documentElement.dataset.lang = l;
  localStorage.setItem('digest-lang', l);
  document.querySelectorAll('.lang-btn').forEach(function(b) {{
    b.classList.toggle('active', b.dataset.l === l);
  }});
}}
function filterType(type) {{
  document.querySelectorAll('.filter-tabs button').forEach(function(b) {{
    b.classList.remove('active');
  }});
  event.target.closest('button').classList.add('active');
  document.querySelectorAll('.card').forEach(function(c) {{
    c.style.display = (type === 'all' || c.dataset.type === type) ? '' : 'none';
  }});
}}
(function() {{
  var saved = localStorage.getItem('digest-lang') || 'en';
  setLang(saved);
}})();
</script>
</body>
</html>
"""

CARD_TMPL = """\
    <a class="card" href="posts/{slug}.html" data-type="{type_key}">
      <div class="card-meta">
        <span class="card-type {type_key}">
          <span class="zh">{type_label_zh}</span><span class="en">{type_label_en}</span>
        </span>
        <span class="card-date"><span class="zh">{date_fmt_zh}</span><span class="en">{date_fmt_en}</span></span>
      </div>
      <h2><span class="zh">{title_zh}</span><span class="en">{title_en}</span></h2>
      <p><span class="zh">{summary_zh}</span><span class="en">{summary_en}</span></p>
    </a>"""

def regen_index(posts):
    type_labels = {
        "news":  ("每日早报", "Daily Briefing"),
        "radar": ("商机雷达", "Opportunity Radar"),
    }
    cards_html = "\n".join(
        CARD_TMPL.format(
            slug=p["slug"], type_key=p["type"],
            type_label_zh=type_labels[p["type"]][0],
            type_label_en=type_labels[p["type"]][1],
            date_fmt_zh=p.get("date_fmt_zh", p.get("date_fmt","")),
            date_fmt_en=p.get("date_fmt_en", p.get("date_fmt","")),
            title_zh=esc(p.get("title_zh", p.get("title",""))),
            title_en=esc(p.get("title_en", p.get("title",""))),
            summary_zh=esc(p.get("summary_zh", p.get("summary",""))),
            summary_en=esc(p.get("summary_en", p.get("summary",""))),
        )
        for p in posts
    ) or '    <div class="empty"><div class="icon">📭</div><p class="zh">暂无内容</p><p class="en">No posts yet</p></div>'
    updated = datetime.now(CST).strftime("%Y-%m-%d %H:%M CST")
    (SITE_DIR / "index.html").write_text(
        INDEX_TMPL.format(cards=cards_html, updated=updated),
        encoding="utf-8"
    )
    print("✅ index.html regenerated")

# ── Git push ───────────────────────────────────────────────────
def git_push(message: str):
    for cmd in [
        ["git", "-C", str(SITE_DIR), "add", "-A"],
        ["git", "-C", str(SITE_DIR), "commit", "-m", message],
        ["git", "-C", str(SITE_DIR), "push", "-u", "origin", "main"],
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            print(f"⚠️  {r.stderr.strip()}", file=sys.stderr)
        else:
            print(r.stdout.strip() or f"✅ {cmd[2]}")

# ── Main ───────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["news","radar"], required=True)
    ap.add_argument("--title-zh", required=True)
    ap.add_argument("--title-en", default="")
    ap.add_argument("--content-zh-file", required=True)
    ap.add_argument("--content-en-file", default=None)
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    content_zh = Path(args.content_zh_file).read_text(encoding="utf-8")
    content_en = Path(args.content_en_file).read_text(encoding="utf-8") if args.content_en_file else ""

    now = datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d")
    slug = f"{args.type}-{date_str}"
    type_label_zh = "每日早报" if args.type == "news" else "商机雷达"
    date_fmt = now.strftime("%Y年%m月%d日")
    date_fmt_zh = date_fmt
    date_fmt_en = now.strftime("%b %d, %Y")

    write_post(slug, args.title_zh, args.title_en or args.title_zh,
               args.type, now, content_zh, content_en)

    posts = load_index()
    posts = [p for p in posts if p["slug"] != slug]
    posts.insert(0, {
        "slug": slug, "type": args.type,
        "type_label": type_label_zh,
        "title_zh": args.title_zh,
        "title_en": args.title_en or args.title_zh,
        "summary_zh": first_line(content_zh),
        "summary_en": first_line(content_en) if content_en else "",
        "date_fmt": date_fmt,
        "date_fmt_zh": date_fmt_zh,
        "date_fmt_en": date_fmt_en,
        "ts": now.isoformat()
    })
    save_index(posts)
    regen_index(posts)

    if not args.no_push:
        git_push(f"📰 {type_label_zh} {date_str}: {args.title_zh}")
    else:
        print("⏭  Skipped git push (--no-push)")

if __name__ == "__main__":
    main()
