#!/usr/bin/env python3
"""
Daily Digest Publisher — Bilingual (zh/en) with SEO, RSS, Sitemap
"""
import argparse, json, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import formatdate
import time

CST = timezone(timedelta(hours=8))
SITE_DIR = Path(__file__).parent
POSTS_DIR = SITE_DIR / "posts"
POSTS_DIR.mkdir(exist_ok=True)
SITE_URL = "https://daily.sundigest.xyz"

# ── Helpers ────────────────────────────────────────────────────
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

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
            return re.sub(r'[#*_\[\]`]', '', line)[:160]
    return ""

# ── NAV / FOOTER shared snippets ───────────────────────────────
NAV = """\
<nav>
  <a class="logo" href="{root}index.html">📰 <span class="zh">每日</span><span class="en">Daily</span><span style="color:var(--accent)"><span class="zh">汇总</span><span class="en">Digest</span></span></a>
  <a href="{root}index.html"><span class="zh">首页</span><span class="en">Home</span></a>
  <div class="spacer"></div>
  <a href="{root}feed.xml" title="RSS Feed" style="font-size:18px;text-decoration:none;">🔔</a>
  <div class="lang-switcher">
    <button class="lang-btn" data-l="zh" onclick="setLang('zh')">中文</button>
    <button class="lang-btn active" data-l="en" onclick="setLang('en')">EN</button>
  </div>
</nav>"""

FOOTER = """\
<footer>
  <div class="footer-inner">
    <div>© Daily Digest · AI Generated · <a href="{root}feed.xml">RSS</a> · <a href="https://github.com/sunh3997-eng/daily-digest">GitHub</a></div>
    <div class="zh">最后更新：{updated}</div>
    <div class="en">Last updated: {updated}</div>
    <div class="disclaimer">Content summaries are AI-generated for informational purposes. All original content belongs to respective publishers. Click links to read full articles.</div>
  </div>
</footer>"""

LANG_JS = """\
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
</script>"""

# ── Post HTML ──────────────────────────────────────────────────
POST_TMPL = """\
<!DOCTYPE html>
<html lang="zh-CN" data-lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_en} / {title_zh} — Daily Digest</title>
<meta name="description" content="{desc_en}">
<meta property="og:title" content="{title_en}">
<meta property="og:description" content="{desc_en}">
<meta property="og:type" content="article">
<meta property="og:url" content="{site_url}/posts/{slug}.html">
<meta property="og:site_name" content="Daily Digest">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title_en}">
<meta name="twitter:description" content="{desc_en}">
<link rel="canonical" href="{site_url}/posts/{slug}.html">
<link rel="alternate" type="application/rss+xml" title="Daily Digest RSS" href="{site_url}/feed.xml">
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>
{nav}
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
{footer}
{lang_js}
</body>
</html>
"""

def write_post(slug, title_zh, title_en, type_key, date, content_zh, content_en, desc_en=""):
    type_label_zh = "每日早报" if type_key == "news" else "商机雷达"
    type_label_en = "Daily Briefing" if type_key == "news" else "Opportunity Radar"
    date_fmt_zh = date.strftime("%Y年%m月%d日 %H:%M")
    date_fmt_en = date.strftime("%B %d, %Y %H:%M CST")
    body_zh = md_to_html(content_zh)
    body_en = md_to_html(content_en) if content_en else "<p><em>English version coming soon.</em></p>"
    if not desc_en:
        desc_en = first_line(content_en or content_zh)
    updated = date.strftime("%Y-%m-%d %H:%M CST")
    nav = NAV.format(root="../")
    footer = FOOTER.format(root="../", updated=updated)
    html = POST_TMPL.format(
        title_zh=esc(title_zh), title_en=esc(title_en),
        type_key=type_key, type_label_zh=type_label_zh, type_label_en=type_label_en,
        date_fmt_zh=date_fmt_zh, date_fmt_en=date_fmt_en,
        body_zh=body_zh, body_en=body_en,
        slug=slug, site_url=SITE_URL, desc_en=esc(desc_en),
        nav=nav, footer=footer, lang_js=LANG_JS
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

SUBSCRIBE_BLOCK = """\
<div class="subscribe-block">
  <div class="subscribe-inner">
    <div>
      <div class="subscribe-title">
        <span class="zh">📬 订阅每日推送</span>
        <span class="en">📬 Subscribe for Daily Updates</span>
      </div>
      <div class="subscribe-desc">
        <span class="zh">每天早报 + 商机雷达，直接送到你的邮箱</span>
        <span class="en">Daily Briefing + Opportunity Radar, delivered to your inbox</span>
      </div>
    </div>
    <form class="subscribe-form" onsubmit="handleSubscribe(event)">
      <input type="email" id="sub-email" placeholder="your@email.com" required>
      <button type="submit">
        <span class="zh">订阅</span><span class="en">Subscribe</span>
      </button>
    </form>
    <div id="sub-msg" style="display:none;font-size:13px;color:#16a34a;margin-top:8px"></div>
  </div>
</div>
<script>
function handleSubscribe(e) {{
  e.preventDefault();
  var email = document.getElementById('sub-email').value;
  var msg = document.getElementById('sub-msg');
  // Open Buttondown subscribe URL (replace with your Buttondown username after signup)
  window.open('https://buttondown.com/daily-sundigest?email=' + encodeURIComponent(email), '_blank');
  msg.style.display = 'block';
  msg.textContent = document.documentElement.dataset.lang === 'zh'
    ? '✅ 正在跳转到订阅确认页...'
    : '✅ Redirecting to confirm your subscription...';
}}
</script>"""

INDEX_TMPL = """\
<!DOCTYPE html>
<html lang="zh-CN" data-lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Digest / 每日汇总 — AI-Powered Bilingual News & Opportunities</title>
<meta name="description" content="Daily AI-generated bilingual digest: tech news briefing + startup opportunity radar. Updated every day at 08:00 and 09:00 CST.">
<meta property="og:title" content="Daily Digest — AI-Powered Bilingual News & Opportunities">
<meta property="og:description" content="Daily AI-generated bilingual digest: tech news briefing + startup opportunity radar.">
<meta property="og:type" content="website">
<meta property="og:url" content="{site_url}">
<meta property="og:site_name" content="Daily Digest">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Daily Digest — AI-Powered Bilingual News">
<meta name="twitter:description" content="Daily AI-generated bilingual digest. Tech news + startup opportunities. Updated daily.">
<meta name="google-site-verification" content="Cw49nZUrpgxS-DWwwe-8W3gA7iy6-pQnxv69ypLKx9Q">
<link rel="canonical" href="{site_url}">
<link rel="alternate" type="application/rss+xml" title="Daily Digest RSS" href="{site_url}/feed.xml">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
{nav}
<div class="hero">
  <h1>📰 <span class="zh">每日汇总</span><span class="en">Daily Digest</span></h1>
  <p>
    <span class="zh">每天 08:00 早报 · 09:00 商机雷达 · 全部由 AI 自动生成</span>
    <span class="en">08:00 Daily Briefing · 09:00 Opportunity Radar · All AI Generated</span>
  </p>
</div>
{subscribe}
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
{footer}
<script>
function filterType(type) {{
  document.querySelectorAll('.filter-tabs button').forEach(function(b) {{
    b.classList.remove('active');
  }});
  event.target.closest('button').classList.add('active');
  document.querySelectorAll('.card').forEach(function(c) {{
    c.style.display = (type === 'all' || c.dataset.type === type) ? '' : 'none';
  }});
}}
</script>
{lang_js}
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
    nav = NAV.format(root="")
    footer = FOOTER.format(root="", updated=updated)
    (SITE_DIR / "index.html").write_text(
        INDEX_TMPL.format(
            cards=cards_html, nav=nav, footer=footer, lang_js=LANG_JS,
            subscribe=SUBSCRIBE_BLOCK, site_url=SITE_URL, updated=updated
        ),
        encoding="utf-8"
    )
    print("✅ index.html regenerated")

# ── RSS Feed ───────────────────────────────────────────────────
def regen_rss(posts):
    now_rfc = formatdate(time.time(), usegmt=True)
    items = []
    for p in posts[:20]:  # latest 20
        ts = p.get("ts", "")
        try:
            dt = datetime.fromisoformat(ts)
            pub_date = formatdate(dt.timestamp(), usegmt=True)
        except Exception:
            pub_date = now_rfc
        title_en = esc(p.get("title_en", p.get("title", "")))
        summary_en = esc(p.get("summary_en", p.get("summary", "")))
        slug = p["slug"]
        url = f"{SITE_URL}/posts/{slug}.html"
        type_label = "Daily Briefing" if p["type"] == "news" else "Opportunity Radar"
        items.append(f"""  <item>
    <title>{title_en} — {type_label}</title>
    <link>{url}</link>
    <guid isPermaLink="true">{url}</guid>
    <pubDate>{pub_date}</pubDate>
    <description>{summary_en}</description>
    <category>{type_label}</category>
  </item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>Daily Digest — AI-Powered Bilingual News &amp; Opportunities</title>
  <link>{SITE_URL}</link>
  <description>Daily AI-generated bilingual digest: tech news briefing + startup opportunity radar.</description>
  <language>en</language>
  <lastBuildDate>{now_rfc}</lastBuildDate>
  <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
  <image>
    <url>{SITE_URL}/assets/og.png</url>
    <title>Daily Digest</title>
    <link>{SITE_URL}</link>
  </image>
{chr(10).join(items)}
</channel>
</rss>"""
    (SITE_DIR / "feed.xml").write_text(rss, encoding="utf-8")
    print("✅ feed.xml regenerated")

# ── Sitemap ────────────────────────────────────────────────────
def regen_sitemap(posts):
    today = datetime.now(CST).strftime("%Y-%m-%d")
    urls = [f"""  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>"""]
    for p in posts:
        ts = p.get("ts","")
        try:
            lastmod = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
        except Exception:
            lastmod = today
        urls.append(f"""  <url>
    <loc>{SITE_URL}/posts/{p["slug"]}.html</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>""")
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""
    (SITE_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print("✅ sitemap.xml regenerated")

# ── robots.txt ─────────────────────────────────────────────────
def write_robots():
    robots = f"""User-agent: *
Allow: /
Sitemap: {SITE_URL}/sitemap.xml
"""
    p = SITE_DIR / "robots.txt"
    if not p.exists():
        p.write_text(robots)
        print("✅ robots.txt created")

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
    ap.add_argument("--content-zh-file", default=None)
    ap.add_argument("--content-en-file", default=None)
    ap.add_argument("--content-zh", default=None)
    ap.add_argument("--content-en", default=None)
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    if args.content_zh_file:
        content_zh = Path(args.content_zh_file).read_text(encoding="utf-8")
    elif args.content_zh:
        content_zh = args.content_zh
    else:
        print("❌ --content-zh or --content-zh-file required", file=sys.stderr); sys.exit(1)

    if args.content_en_file:
        content_en = Path(args.content_en_file).read_text(encoding="utf-8")
    elif args.content_en:
        content_en = args.content_en
    else:
        content_en = ""

    now = datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d")
    slug = f"{args.type}-{date_str}"
    type_label_zh = "每日早报" if args.type == "news" else "商机雷达"
    date_fmt = now.strftime("%Y年%m月%d日")

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
        "date_fmt_zh": date_fmt,
        "date_fmt_en": now.strftime("%b %d, %Y"),
        "ts": now.isoformat()
    })
    save_index(posts)
    regen_index(posts)
    regen_rss(posts)
    regen_sitemap(posts)
    write_robots()

    if not args.no_push:
        git_push(f"📰 {type_label_zh} {date_str}: {args.title_zh}")
    else:
        print("⏭  Skipped git push (--no-push)")

if __name__ == "__main__":
    main()
