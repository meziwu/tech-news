"""
每日中文科技新聞聚合器
抓取台灣 + 中國科技媒體 RSS，生成靜態網頁並推播 Telegram
"""

import html as html_lib
import os
import time
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── 設定 ──────────────────────────────────────────────────────────────────────

TZ_TAIPEI = timezone(timedelta(hours=8))

SOURCES = [
    # 台灣
    {"name": "科技新報",   "url": "https://technews.tw/feed/",                   "region": "tw"},
    {"name": "iThome",    "url": "https://www.ithome.com.tw/rss",               "region": "tw"},
    {"name": "TechOrange","url": "https://buzzorange.com/techorange/feed/",     "region": "tw"},
    {"name": "Cool3c",   "url": "https://www.cool3c.com/rss",                  "region": "tw"},
    {"name": "T客邦",     "url": "https://www.techbang.com/posts.rss",          "region": "tw"},
    {"name": "數位時代",  "url": "https://www.bnext.com.tw/rss",                "region": "tw"},
    {"name": "電腦王阿達","url": "https://www.kocpc.com.tw/feed",               "region": "tw"},
    {"name": "INSIDE",   "url": "https://www.inside.com.tw/feed",              "region": "tw"},
    # 中國
    {"name": "少數派",    "url": "https://sspai.com/feed",                      "region": "cn"},
    {"name": "虎嗅",     "url": "https://www.huxiu.com/rss/0.xml",             "region": "cn"},
    {"name": "愛范兒",   "url": "https://www.ifanr.com/feed",                  "region": "cn"},
    {"name": "36氪",     "url": "https://36kr.com/feed",                       "region": "cn"},
]

REGION_LABEL = {"tw": "🇹🇼 台灣", "cn": "🇨🇳 中國"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TechNewsBot/1.0)"}
FETCH_TIMEOUT = 15   # 秒
HOURS_BACK    = 28   # 抓幾小時內的文章（多抓一點避免時區問題）


# ── 抓取 RSS ──────────────────────────────────────────────────────────────────

def fetch_feed(source: dict, cutoff: datetime) -> list[dict]:
    """抓單一 RSS，回傳文章列表"""
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"  [SKIP] {source['name']}: {e}")
        return []

    articles = []
    for entry in feed.entries:
        # 解析發布時間
        pub = None
        for attr in ("published_parsed", "updated_parsed"):
            t = getattr(entry, attr, None)
            if t:
                try:
                    pub = datetime(*t[:6], tzinfo=timezone.utc).astimezone(TZ_TAIPEI)
                    break
                except Exception:
                    pass

        # 沒有時間的文章也收（部分 RSS 不帶時間）
        if pub is not None and pub < cutoff:
            continue

        title = entry.get("title", "").strip()
        link  = entry.get("link", "").strip()
        if not title or not link:
            continue

        articles.append({
            "title":  title,
            "link":   link,
            "time":   pub.strftime("%H:%M") if pub else "──",
            "source": source["name"],
            "region": source["region"],
        })

    print(f"  {source['name']}: {len(articles)} 篇")
    return articles


def fetch_all() -> dict[str, list[dict]]:
    """抓所有來源，依 region 分組回傳"""
    cutoff = datetime.now(TZ_TAIPEI) - timedelta(hours=HOURS_BACK)
    result: dict[str, list[dict]] = {"tw": [], "cn": []}

    for source in SOURCES:
        arts = fetch_feed(source, cutoff)
        result[source["region"]].extend(arts)
        time.sleep(0.5)   # 避免太快被擋

    return result


# ── 生成 HTML ─────────────────────────────────────────────────────────────────

def build_html(articles_by_region: dict, date_str: str, pages_url: str) -> str:
    total = sum(len(v) for v in articles_by_region.values())

    def render_section(region: str) -> str:
        arts = articles_by_region.get(region, [])
        if not arts:
            return ""
        # 依來源分組
        by_source: dict[str, list] = {}
        for a in arts:
            by_source.setdefault(a["source"], []).append(a)

        rows = []
        for src, items in by_source.items():
            rows.append(f'<div class="source-label">{src} <span class="count">{len(items)}</span></div>')
            for a in items:
                title_esc = html_lib.escape(a["title"])
                link_esc  = html_lib.escape(a["link"])
                rows.append(
                    f'<div class="article">'
                    f'<span class="time">{a["time"]}</span>'
                    f'<a href="{link_esc}" target="_blank" rel="noopener">{title_esc}</a>'
                    f'</div>'
                )
        label = REGION_LABEL[region]
        return f'<section><h2>{label} <span class="count">{len(arts)}</span></h2>{"".join(rows)}</section>'

    tw_html = render_section("tw")
    cn_html = render_section("cn")

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日科技摘要 {date_str}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "Microsoft JhengHei", sans-serif;
         background: #f5f7fa; color: #222; }}
  header {{ background: #1a1a2e; color: #fff; padding: 20px 24px; }}
  header h1 {{ font-size: 1.3rem; }}
  header .meta {{ font-size: 0.85rem; color: #aab; margin-top: 4px; }}
  .container {{ max-width: 860px; margin: 0 auto; padding: 16px; }}
  .stats {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
  .stat {{ background: #fff; border-radius: 8px; padding: 10px 16px;
           box-shadow: 0 1px 4px rgba(0,0,0,.08); font-size: 0.9rem; }}
  .stat strong {{ font-size: 1.4rem; display: block; }}
  section {{ background: #fff; border-radius: 10px; margin-bottom: 16px;
             box-shadow: 0 1px 4px rgba(0,0,0,.08); overflow: hidden; }}
  section h2 {{ padding: 12px 16px; background: #f0f4ff;
                font-size: 1rem; border-bottom: 1px solid #e4e8f0; }}
  .source-label {{ padding: 8px 16px 4px; font-size: 0.78rem;
                   color: #888; font-weight: 600; letter-spacing: .05em;
                   border-top: 1px solid #f0f0f0; margin-top: 4px; }}
  .article {{ display: flex; align-items: baseline; gap: 10px;
              padding: 7px 16px; border-bottom: 1px solid #f5f5f5; }}
  .article:last-child {{ border-bottom: none; }}
  .time {{ font-size: 0.75rem; color: #aaa; min-width: 36px; flex-shrink: 0; }}
  .article a {{ color: #1a1a2e; text-decoration: none; font-size: 0.9rem;
                line-height: 1.5; }}
  .article a:hover {{ color: #2e75b6; text-decoration: underline; }}
  .count {{ background: #e8eeff; color: #2e75b6; border-radius: 99px;
            padding: 1px 8px; font-size: 0.75rem; font-weight: normal; }}
  footer {{ text-align: center; padding: 20px; color: #aaa; font-size: 0.8rem; }}
  @media (max-width: 600px) {{ .article {{ flex-direction: column; gap: 2px; }} }}
</style>
</head>
<body>
<header>
  <h1>📰 每日科技摘要</h1>
  <div class="meta">{date_str}　共 {total} 篇文章</div>
</header>
<div class="container">
  <div class="stats">
    <div class="stat"><strong>{len(articles_by_region.get("tw",[]))}</strong>台灣文章</div>
    <div class="stat"><strong>{len(articles_by_region.get("cn",[]))}</strong>中國文章</div>
    <div class="stat"><strong>{total}</strong>總計</div>
  </div>
  {tw_html}
  {cn_html}
</div>
<footer>自動生成於 {date_str} 08:30 &nbsp;|&nbsp;
  <a href="{pages_url}" style="color:#aaa">查看最新版本</a>
</footer>
</body>
</html>"""


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(bot_token: str, chat_id: str, articles_by_region: dict,
                  date_str: str, pages_url: str):
    total = sum(len(v) for v in articles_by_region.values())
    tw    = len(articles_by_region.get("tw", []))
    cn    = len(articles_by_region.get("cn", []))
    SEP   = "─────────────────────"

    tw_sources = {}
    for a in articles_by_region.get("tw", []):
        tw_sources[a["source"]] = tw_sources.get(a["source"], 0) + 1
    cn_sources = {}
    for a in articles_by_region.get("cn", []):
        cn_sources[a["source"]] = cn_sources.get(a["source"], 0) + 1

    def _esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    tw_line = "　".join(f"{_esc(k)} {v}篇" for k, v in tw_sources.items()) or "無"
    cn_line = "　".join(f"{_esc(k)} {v}篇" for k, v in cn_sources.items()) or "無"

    text = (
        f"📰 <b>每日科技摘要</b>\n"
        f"📅 {date_str}\n"
        f"{SEP}\n"
        f"🇹🇼 台灣（{tw} 篇）\n{tw_line}\n\n"
        f"🇨🇳 中國（{cn} 篇）\n{cn_line}\n"
        f"{SEP}\n"
        f"共 <b>{total}</b> 篇　"
        f'👉 <a href="{pages_url}">查看完整摘要</a>'
    )

    url  = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": True
    }, timeout=15)
    if resp.ok:
        print("Telegram 推播成功")
    else:
        print(f"Telegram 推播失敗: {resp.status_code} {resp.text}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now      = datetime.now(TZ_TAIPEI)
    date_str = now.strftime("%Y-%m-%d")

    # GitHub Pages URL（從環境變數取得，格式：https://username.github.io/repo）
    pages_url = os.environ.get("PAGES_URL", "#")

    print(f"[{date_str}] 開始抓取...")
    articles = fetch_all()
    total = sum(len(v) for v in articles.values())
    print(f"共抓到 {total} 篇文章")

    # 生成 HTML
    html = build_html(articles, date_str, pages_url)
    out  = Path("docs/index.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"已寫入 {out}")

    # Telegram 推播
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID", "")
    if bot_token and chat_id:
        send_telegram(bot_token, chat_id, articles, date_str, pages_url)
    else:
        print("未設定 Telegram 環境變數，跳過推播")


if __name__ == "__main__":
    main()
