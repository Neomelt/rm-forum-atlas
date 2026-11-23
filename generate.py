#!/usr/bin/env python3
"""RM 论坛技术图鉴 · 静态站生成器。
用法:
  python3 generate.py <repo_root> <out_dir>            # 联网拉取最新公开帖并构建 dist/
  python3 generate.py <repo_root> <out_dir> --offline  # 仅用本地 legacy_corpus.json 快速预览
"""
import collections
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT, OUT = sys.argv[1], sys.argv[2]
OFFLINE = "--offline" in sys.argv[3:]

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
API = "https://bbs.robomaster.com/developers-server/rest/posts/list"
FIELDS = [
    "id", "title", "authorNickname", "teamInfo", "tags", "views",
    "approvals", "comments", "createAt", "marrow", "official",
    "timesCited", "introduction", "category", "history",
]


def pull(cat):
    out, page = [], 1
    while True:
        body = json.dumps({"pageSize": 50, "pageNo": page, "filter": {"category": cat}})
        for attempt in range(5):
            r = subprocess.run(
                [
                    "curl", "-sL", "--max-time", "25", "-A", UA,
                    "-H", "Content-Type: application/json",
                    "-X", "POST", API, "-d", body,
                ],
                capture_output=True,
            )
            try:
                d = json.loads(r.stdout)
                assert d.get("code") == 0
                assert d["data"]["list"] or (page > 1)
                break
            except Exception:
                if attempt == 4:
                    raise RuntimeError(f"API {cat} p{page} 五次失败: {r.stdout[:120]!r}")
                time.sleep(3 * (attempt + 1))
        lst = d["data"]["list"]
        if not lst:
            break
        out += [{k: a.get(k) for k in FIELDS} for a in lst]
        if page * 50 >= d["data"]["total"]:
            break
        page += 1
        time.sleep(0.25)
    return out


legacy = json.load(open(os.path.join(ROOT, "data/legacy_corpus.json"), encoding="utf-8"))
fresh = {}
if not OFFLINE:
    for cat in ("ARTICLE", "WIKI", "FAQ"):
        got = pull(cat)
        print(f"  {cat}: {len(got)} 条", file=sys.stderr)
        for a in got:
            fresh[a["id"]] = a
        time.sleep(1)
    assert len(fresh) > 1100, f"列表拉取仅 {len(fresh)} 条,疑似异常,拒绝发布"

merged = {a["id"]: a for a in legacy}
merged.update(fresh)
corpus = list(merged.values())
listed = list(fresh.values()) if fresh else [a for a in corpus if not a.get("history")]

NOW = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
STAMP = NOW.strftime("%Y-%m-%d %H:%M")
CUR_Y = NOW.year


def yr(a):
    return str(a.get("createAt") or "")[:4]


def ym(a):
    return str(a.get("createAt") or "")[:7]


def v(a):
    return a.get("views") or 0


def esc(s):
    return html.escape(str(s), quote=True)


# ---------- SVG Charts ----------
def hbar(x0, y, w, h, r, cls):
    r = min(r, h / 2, max(w, 0.01))
    return (
        f'<path class="{cls}" d="M{x0},{y} h{max(w - r, 0):.1f} '
        f'a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} '
        f'a{r},{r} 0 0 1 -{r},{r} h-{max(w - r, 0):.1f} z"/>'
    )


def vbar(x, yb, w, hg, r, cls):
    r = min(r, w / 2, max(hg, 0.01))
    return (
        f'<path class="{cls}" d="M{x},{yb} v-{max(hg - r, 0):.1f} '
        f'a{r},{r} 0 0 1 {r},-{r} h{w - 2 * r:.1f} '
        f'a{r},{r} 0 0 1 {r},{r} v{max(hg - r, 0):.1f} z"/>'
    )


def hbarchart(rows, xmax, L, unit="帖", fmt=lambda val: str(val)):
    rh = 30
    H = len(rows) * rh + 14
    pw = 620 - L - 56
    p = [f'<svg class="chart" viewBox="0 0 620 {H}" role="img">']
    for i, (k, val) in enumerate(rows):
        y = 6 + i * rh
        bw = max(2.0, pw * val / xmax) if val else 0
        tip = esc(f"<b>{esc(k)}</b> · {fmt(val)} {unit}")
        p.append(f'<text class="rlab" x="{L - 10}" y="{y + 15}" text-anchor="end">{esc(k)}</text>')
        p.append(f'<g class="hit" data-tip="{tip}">{hbar(L, y + 4, bw, 14, 3, "s1")}</g>')
        p.append(f'<text class="dlab" x="{L + bw + 8:.1f}" y="{y + 15}">{fmt(val)}</text>')
    return "".join(p) + "</svg>"


# 图1 年度发帖量
yc = collections.Counter(yr(a) for a in corpus)
years = [str(y) for y in range(2015, CUR_Y + 1)]
ymax = max(2000, max((yc.get(y, 0) for y in years), default=2000))
W, H, L, T, B = 960, 240, 46, 20, 30
pw, ph = W - L - 18, H - T - B
n = len(years)
bw = pw / n - 10
p = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img">']
for gv in range(0, ymax + 1, 500):
    gy = T + ph * (1 - gv / ymax)
    p.append(
        f'<line class="grid-line" x1="{L}" y1="{gy:.1f}" x2="{W - 18}" y2="{gy:.1f}"/>'
        f'<text class="tick" x="{L - 8}" y="{gy + 4:.1f}" text-anchor="end">{gv}</text>'
    )
for i, y in enumerate(years):
    val = yc.get(y, 0)
    x = L + i * (pw / n) + 5
    hg = ph * val / ymax
    tip = esc(f"<b>{y} 年</b> · {val:,} 帖")
    p.append(f'<g class="hit" data-tip="{tip}">{vbar(x, T + ph, bw, hg, 3, "s1")}</g>')
    p.append(f'<text class="dlab" x="{x + bw / 2:.1f}" y="{T + ph - hg - 6:.1f}" text-anchor="middle">{val}</text>')
    p.append(f'<text class="tick" x="{x + bw / 2:.1f}" y="{H - 10}" text-anchor="middle">{y}</text>')
svg_year = "".join(p) + "</svg>"

# 图2 技术方向热词变化
WORDS = [
    ("图传 / 通信", r"图传|通信|链路|FEC"),
    ("视觉 / OpenCV", r"视觉|OpenCV|opencv"),
    ("PID / 控制", r"PID|pid"),
    ("陀螺 / 反陀螺", r"小陀螺|反陀螺|陀螺仪?"),
    ("飞镖 / 制导", r"飞镖|制导"),
    ("雷达站", r"雷达"),
    ("超级电容", r"超级电容|超电"),
    ("轮腿 / 平衡", r"轮腿|轮足|平衡步兵|平衡底盘"),
    ("导航 / SLAM", r"导航|SLAM|slam|建图|定位"),
    ("仿真 / Sim2Real", r"仿真|sim2real|Sim2Real|Gazebo|MuJoCo"),
    ("神经网络 / RL", r"神经网络|深度学习|YOLO|yolo|强化学习"),
    ("卡尔曼 / EKF", r"卡尔曼|EKF|KF\b"),
]
yw = {y: collections.Counter() for y in years}
for a in corpus:
    y = yr(a)
    if y not in yw:
        continue
    txt = (a.get("title") or "") + " " + (a.get("introduction") or "")
    for w_name, pat in WORDS:
        if re.search(pat, txt):
            yw[y][w_name] += 1

L2 = 128
cw = (960 - L2 - 16) / len(years)
ch = 30
H2 = len(WORDS) * ch + 44
p = [f'<svg class="chart" viewBox="0 0 960 {H2}" role="img">']
for j, y in enumerate(years):
    p.append(f'<text class="tick" x="{L2 + j * cw + cw / 2:.0f}" y="16" text-anchor="middle">{y}</text>')
for i, (w_name, _) in enumerate(WORDS):
    y0 = 24 + i * ch
    vals = [yw[y][w_name] for y in years]
    mx = max(vals) or 1
    p.append(f'<text class="rlab" x="{L2 - 10}" y="{y0 + ch / 2 + 4:.0f}" text-anchor="end">{esc(w_name)}</text>')
    for j, val in enumerate(vals):
        x = L2 + j * cw
        op = 0.08 + 0.90 * (val / mx) if val else 0.04
        tip = esc(f"<b>{esc(w_name)}</b> ({years[j]}) · {val} 帖")
        p.append(
            f'<g class="hit" data-tip="{tip}">'
            f'<rect x="{x + 1.5:.1f}" y="{y0 + 1.5}" width="{cw - 3:.1f}" height="{ch - 3}" rx="3" '
            f'class="s1" fill-opacity="{op:.2f}"/></g>'
        )
        if val:
            cls = "cthi" if op > 0.56 else "dlab"
            p.append(f'<text class="{cls}" x="{x + cw / 2:.1f}" y="{y0 + ch / 2 + 4}" text-anchor="middle" style="pointer-events:none">{val}</text>')
svg_heat = "".join(p) + "</svg>"

# 图3 月度发帖
mon = collections.Counter(ym(a) for a in listed if ym(a) >= "2024-06")
months = sorted(mon) or ["2024-06"]
mmax = max(100, max(mon.values(), default=100))
nm = len(months)
bw_m = max(4.0, (620 - 44 - 16) / nm - 3)
p = ['<svg class="chart" viewBox="0 0 620 228" role="img">']
for gv in range(0, mmax + 1, 25):
    gy = 16 + 178 * (1 - gv / mmax)
    p.append(
        f'<line class="grid-line" x1="44" y1="{gy:.1f}" x2="604" y2="{gy:.1f}"/>'
        f'<text class="tick" x="38" y="{gy + 4:.1f}" text-anchor="end">{gv}</text>'
    )
peak = sorted(months, key=lambda m: -mon[m])[:4]
for i, m in enumerate(months):
    val = mon[m]
    x = 44 + i * ((620 - 60) / nm) + 1.5
    hg = 178 * val / mmax
    tip = esc(f"<b>{m}</b> · {val} 篇")
    p.append(f'<g class="hit" data-tip="{tip}">{vbar(x, 194, bw_m, hg, 2, "s1")}</g>')
    if m in peak and val > 0:
        p.append(f'<text class="dlab" x="{x + bw_m / 2:.1f}" y="{194 - hg - 5:.1f}" text-anchor="middle">{val}</text>')
    if m.endswith("-01") or i == 0:
        p.append(f'<text class="tick" x="{x + bw_m / 2:.1f}" y="214" text-anchor="middle">{m[:4]}</text>')
svg_month = "".join(p) + "</svg>"


# 图4 高校发帖量
def school(a):
    ti = a.get("teamInfo")
    if isinstance(ti, dict):
        c = ti.get("colleges")
        if c:
            return c[0].get("collegeName")
    m = re.search(r"([一-鿿]{2,12}(?:大学|学院))", a.get("title") or "")
    return m.group(1) if m else None


sc = collections.Counter()
for a in corpus:
    s = school(a)
    if s:
        sc[s] += 1
top_sc = sc.most_common(10) or [("暂无", 0)]
svg_school = hbarchart(top_sc, max(60, top_sc[0][1]), 140, unit="帖")

# 图5 兵种标签分布
KIND = ["步兵", "英雄", "工程", "哨兵", "空中机器人", "飞镖系统", "雷达", "场地道具"]
kind = collections.Counter()
for a in listed:
    for t in (a.get("tags") or []):
        if t.get("name") in KIND:
            kind[t["name"]] += 1
rows_kind = [(k.replace("机器人", "").replace("系统", ""), kind[k]) for k in sorted(KIND, key=lambda k: -kind[k])]
svg_kind = hbarchart(rows_kind, max(100, rows_kind[0][1]), 82, unit="帖")

# 图6 被引榜
cited = sorted(corpus, key=lambda a: -(a.get("timesCited") or 0))[:10]
rows_cited = [((a.get("title") or "")[:20], a.get("timesCited") or 0) for a in cited]
svg_cited = hbarchart(rows_cited, max(40, rows_cited[0][1] if rows_cited else 40), 218, unit="次引用")


# ---------- Rankings ----------
def linkrow(a, extra=""):
    return (
        f'<tr><td class="n">{v(a):,}</td>'
        f'<td class="ti"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">{esc((a.get("title") or "")[:64])}</a>{extra}</td>'
        f'<td class="lk"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">#{a["id"]}</a></td></tr>'
    )


latest = sorted(listed, key=lambda a: str(a.get("createAt")), reverse=True)[:20]
t_latest = "\n".join(
    f'<tr><td class="n">{str(a.get("createAt"))[:10]}</td>'
    f'<td class="ti"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">{esc((a.get("title") or "")[:64])}</a></td>'
    f'<td class="n">{v(a):,}</td>'
    f'<td class="lk"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">#{a["id"]}</a></td></tr>'
    for a in latest
)
anc = sorted((a for a in corpus if a.get("history")), key=lambda a: -v(a))[:12]
t_anc = "\n".join(linkrow(a, f'<span class="cc">{ym(a)}</span>') for a in anc)

SKIP = ("公告", "官方信息", "宣传", "组织建设", "项目管理")
tech = [a for a in listed if not any(t.get("name") in SKIP for t in (a.get("tags") or []))]
hot = sorted(tech, key=lambda a: -v(a))[:15]
t_hot = "\n".join(linkrow(a) for a in hot)

el = [a for a in listed if v(a) >= 3000]
liked = sorted(el, key=lambda a: -(a.get("approvals") or 0) / v(a))[:12]
t_liked = "\n".join(
    f'<tr><td class="n">{(a.get("approvals") or 0) / v(a) * 1000:.1f}‰</td>'
    f'<td class="ti"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">{esc((a.get("title") or "")[:62])}</a></td>'
    f'<td class="n">{v(a):,}</td>'
    f'<td class="lk"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">#{a["id"]}</a></td></tr>'
    for a in liked
)


# ---------- Parse blocks/block_catalog.html -> Left Nav + Dense Stream ----------
cat_raw = open(os.path.join(ROOT, "blocks/block_catalog.html"), encoding="utf-8").read()
cat_sections = re.findall(r'<h3>([^<]+)</h3><div class="tblwrap"><table>(.*?)</table></div>', cat_raw, re.S)
cat_items = []
cat_counts = []
for sec_title, tbl_html in cat_sections:
    clean_cat = re.sub(r"（\d+）", "", sec_title).strip()
    rows_m = re.findall(
        r'<tr><td class="tm">(.*?)</td><td>(.*?)</td><td class="n">(.*?)</td><td class="lk">(.*?)</td></tr>',
        tbl_html,
        re.S,
    )
    cat_counts.append((clean_cat, len(rows_m)))
    for team, desc, views_s, lk_html in rows_m:
        m_href = re.search(r'href="([^"]+)"[^>]*>([^<]+)<', lk_html)
        if m_href:
            href, pid = m_href.group(1), m_href.group(2)
        else:
            href, pid = "", re.sub(r"<[^>]+>", "", lk_html).strip()
        cat_items.append({
            "cat": clean_cat,
            "team": team.strip(),
            "desc": desc.strip(),
            "views": views_s.strip(),
            "href": href,
            "pid": pid,
        })

side_html = [f'<button class="cat-side-btn on" data-cat="ALL"><span>全部方向</span><small>{len(cat_items)}</small></button>']
for cname, cnt in cat_counts:
    side_html.append(f'<button class="cat-side-btn" data-cat="{esc(cname)}"><span>{esc(cname)}</span><small>{cnt}</small></button>')

entries_html = []
for it in cat_items:
    plain_desc = re.sub(r"<[^>]+>", "", it["desc"])
    hay = esc(f"{it['cat']} {it['team']} {plain_desc} {it['pid']}".lower())
    lk = (
        f'<a class="entry-link" href="{esc(it["href"])}" target="_blank" rel="noopener">#{esc(it["pid"])} ↗</a>'
        if it["href"]
        else f'<span class="entry-views">{esc(it["pid"])}</span>'
    )
    v_txt = f"{it['views']} 浏览" if it["views"] and it["views"] != "—" else "早期源头帖"
    entries_html.append(
        f'<div class="entry" data-cat="{esc(it["cat"])}" data-hay="{hay}">'
        f'<div><div class="entry-team">{it["team"]}</div><span class="entry-cat">{esc(it["cat"])}</span></div>'
        f'<div class="entry-desc">{it["desc"]}</div>'
        f'<div class="entry-meta">{lk}<span class="entry-views">{esc(v_txt)}</span></div>'
        f"</div>"
    )


# ---------- Parse blocks/block_essence.html ----------
ess_raw = open(os.path.join(ROOT, "blocks/block_essence.html"), encoding="utf-8").read()
insights = re.findall(r'<li><b>(.*?)</b><span class="d">(.*?)</span></li>', ess_raw, re.S)
ess_eras = re.findall(r'<h3>(20\d\d[^<]+)</h3><div class="tblwrap"><table>(.*?)</table></div>', ess_raw, re.S)

notes_li = "".join(f"<li><b>{t}</b>{d}</li>" for t, d in insights)
era_tabs = []
era_panels = []
for idx, (etitle, etbl) in enumerate(ess_eras):
    key = f"era-{idx}"
    on = " on" if idx == 0 else ""
    label = etitle.replace("（", "<small>").replace("）", "</small>")
    era_tabs.append(f'<button class="sub-btn{on}" data-sub="{key}">{label}</button>')
    era_panels.append(
        f'<div class="sub-panel{on} sheet" data-subpanel="essence" data-key="{key}">'
        f'<div class="tblwrap"><table>{etbl}</table></div></div>'
    )


# ---------- Compact JSON for all.html (with author & intro snippet for full-text search) ----------
CAT_CODE = {"ARTICLE": 0, "WIKI": 1, "FAQ": 2}
corpus_sorted = sorted(corpus, key=lambda a: -v(a))
compact_rows = [
    [
        a["id"],
        (a.get("title") or "(无题)").strip()[:96],
        v(a),
        ym(a),
        CAT_CODE.get(a.get("category"), 0),
        1 if a.get("history") else 0,
        (a.get("authorNickname") or "").strip()[:24],
        re.sub(r"\s+", " ", (a.get("introduction") or "")).strip()[:140],
    ]
    for a in corpus_sorted
]
compact_json = json.dumps(compact_rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# ---------- Shared Shell ----------
total = len(corpus)
tviews = sum(v(a) for a in corpus)
nleg = sum(1 for a in corpus if a.get("history"))
head_raw = open(os.path.join(ROOT, "blocks/block_head.html"), encoding="utf-8").read()

BEYBLADE_BTN = """<button id="beybladeTop" class="beyblade-top" title="回到顶部" aria-label="回到顶部">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
  <rect x="6" y="6" width="12" height="12" rx="2"/>
  <path d="M4 7v4M20 7v4M4 13v4M20 13v4"/>
  <circle cx="12" cy="12" r="2.2" fill="currentColor"/>
</svg>
</button>"""


def topbar(cur):
    nav = (
        '<a class="top-link" href="./all.html">全量索引</a>'
        if cur == "atlas"
        else '<a class="top-link" href="./">← 返回图鉴</a>'
    )
    return f"""<div class="energy-bar"><div class="energy-fill" id="energyFill"></div></div>
<header class="topbar">
  <div class="topbar-in">
    <a class="brand" href="./">
      <span class="brand-name">RM 论坛技术图鉴</span>
      <span class="brand-stamp">更新于 {STAMP}</span>
    </a>
    <div class="top-right">
      {nav}
      <div class="factions" role="group" aria-label="主题配色">
        <button class="fbtn on" data-f="gold"><i class="dot"></i>金色十年</button>
        <button class="fbtn" data-f="red"><i class="dot"></i>红方</button>
        <button class="fbtn" data-f="blue"><i class="dot"></i>蓝方</button>
      </div>
    </div>
  </div>
</header>"""


def asset_ver(rel_path):
    data = open(os.path.join(ROOT, rel_path), "rb").read()
    return hashlib.sha1(data).hexdigest()[:8]


ATLAS_VER = asset_ver("static/atlas.js")
SEARCH_VER = asset_ver("static/index_search.js")


def shell(title, cur, body, extra_js=""):
    head = head_raw.replace("<title>RM 论坛技术图鉴</title>", f"<title>{esc(title)}</title>")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="RoboMaster 论坛公开帖技术图鉴、老帖精华与全量检索，每日自动更新">
{head}
</head>
<body>
<div class="site-bg" aria-hidden="true"></div>
{topbar(cur)}
<main class="wrap">
{body}
</main>
<div class="hud-tip" id="hudTip"></div>
{BEYBLADE_BTN}
<script src="./assets/atlas.js?v={ATLAS_VER}"></script>
{extra_js}
</body>
</html>"""


# ---------- Main Page Body (Workspace Tabs Architecture) ----------
atlas_body = f"""
<section class="hero">
  <div class="hero-copy">
    <h1>RM 论坛<span>技术图鉴</span></h1>
    <p class="hero-desc">98% 的人在这里被打败，但 100% 的人获得成长。</p>
    <div class="hero-stats">
      <div class="hstat"><b>{total:,}</b><span>收录公开帖</span></div>
      <div class="hstat"><b>{len(cat_items)}</b><span>精选开源方案</span></div>
      <div class="hstat"><b>65</b><span>实测存活老帖</span></div>
      <div class="hstat"><b>{tviews / 1e8:.2f} 亿</b><span>累计阅读量</span></div>
    </div>
  </div>
  <div class="rune-stage">
    <canvas id="runeCanvas" aria-label="大能量机关交互动画"></canvas>
    <div class="rune-caption">
      <span>大符转速 <b id="runeSpd">1.20 rad/s</b></span>
      <span>已激活 <b id="runeHit">0/5</b></span>
      <span>点击亮叶可试打</span>
    </div>
  </div>
</section>

<nav class="view-nav" aria-label="板块切换">
  <div class="vtabs">
    <button class="vtab on" data-view="catalog">开源图鉴<small>{len(cat_items)}</small></button>
    <button class="vtab" data-view="pulse">最新与热榜</button>
    <button class="vtab" data-view="stats">历年数据</button>
    <button class="vtab" data-view="essence">远古档案<small>65</small></button>
  </div>
  <a class="vnav-all" href="./all.html">搜索全部 {total:,} 帖 →</a>
</nav>

<section class="view-panel on" data-view="catalog">
  <div id="catalogApp" class="cat-layout">
    <aside class="sheet cat-side" aria-label="技术方向筛选">
      {"".join(side_html)}
    </aside>
    <div class="sheet">
      <div class="cat-main-bar">
        <input id="catSearch" class="search-in" type="search" placeholder="搜队伍、学校或关键词（如 MPC、轮腿、超电、雷达）…">
        <span id="catCount" class="cat-count">{len(cat_items)} / {len(cat_items)} 项</span>
      </div>
      <div>{"".join(entries_html)}</div>
      <div id="catEmpty" class="empty-msg" style="display:none">没有找到对应条目，换个关键词试试。</div>
    </div>
  </div>
</section>

<section class="view-panel" data-view="pulse">
  <div class="sub-tabs" data-subgroup="boards">
    <button class="sub-btn on" data-sub="latest">最近更新<small>{len(latest)}</small></button>
    <button class="sub-btn" data-sub="hot">新论坛高浏览<small>{len(hot)}</small></button>
    <button class="sub-btn" data-sub="liked">高赞密度<small>{len(liked)}</small></button>
    <button class="sub-btn" data-sub="anc">老论坛热帖<small>{len(anc)}</small></button>
  </div>
  <div class="sub-panel on sheet" data-subpanel="boards" data-key="latest">
    <div class="tblwrap"><table><thead><tr><th>日期</th><th>标题</th><th>浏览</th><th>帖号</th></tr></thead><tbody>{t_latest}</tbody></table></div>
  </div>
  <div class="sub-panel sheet" data-subpanel="boards" data-key="hot">
    <div class="tblwrap"><table><thead><tr><th>浏览</th><th>标题（已排除公告与宣传类）</th><th>帖号</th></tr></thead><tbody>{t_hot}</tbody></table></div>
  </div>
  <div class="sub-panel sheet" data-subpanel="boards" data-key="liked">
    <div class="tblwrap"><table><thead><tr><th>每千浏览获赞</th><th>标题（浏览 ≥ 3,000）</th><th>浏览</th><th>帖号</th></tr></thead><tbody>{t_liked}</tbody></table></div>
  </div>
  <div class="sub-panel sheet" data-subpanel="boards" data-key="anc">
    <div class="tblwrap"><table><thead><tr><th>浏览</th><th>标题（老论坛迁移快照）</th><th>帖号</th></tr></thead><tbody>{t_anc}</tbody></table></div>
  </div>
</section>

<section class="view-panel" data-view="stats">
  <div class="chart-stack">
    <figure class="sheet chart-box">
      <figcaption>历年发帖量（2015–{CUR_Y}）</figcaption>
      <p class="fignote">老论坛到新论坛迁移的起伏很明显；{CUR_Y} 年统计截至当日。</p>
      {svg_year}
    </figure>
    <figure class="sheet chart-box">
      <figcaption>技术方向热词变化</figcaption>
      <p class="fignote">按标题和简介统计，每一行按该词自身最高年份着色，能看出各个技术方向是哪一年火起来的。</p>
      {svg_heat}
    </figure>
    <div class="chart-grid">
      <figure class="sheet chart-box">
        <figcaption>新论坛月度发帖（2024.06 起）</figcaption>
        <p class="fignote">每年 8–9 月国赛结束后都会迎来一波集中开源。</p>
        {svg_month}
      </figure>
      <figure class="sheet chart-box">
        <figcaption>高校发帖量排行</figcaption>
        <p class="fignote">按战队绑定高校与标题校名合并统计。</p>
        {svg_school}
      </figure>
      <figure class="sheet chart-box">
        <figcaption>新论坛兵种标签分布</figcaption>
        <p class="fignote">一帖可带多个标签；按上场台数折算，雷达方向开源密度其实最高。</p>
        {svg_kind}
      </figure>
      <figure class="sheet chart-box">
        <figcaption>被引用最多的帖子</figcaption>
        <p class="fignote">新论坛原生引用计数，基本都是被后来队伍反复参考的基础方案。</p>
        {svg_cited}
      </figure>
    </div>
  </div>
</section>

<section class="view-panel" data-view="essence">
  <div class="sheet ess-intro">
    老论坛迁移过来的 <b>{nleg:,} 篇</b>帖子里（求助 3,288 / 无前缀 2,783 / 分享 2,176 / 开源 1,083 / 公告 191 / 技术报告 23），逐篇翻过正文并实测了网盘和附件链接，挑出 <b>65 篇</b>今天打开依然有用的留在这里。
  </div>
  <details class="sheet ess-notes">
    <summary>翻老帖时发现的 6 件有意思的事（点击展开）</summary>
    <ol>{notes_li}</ol>
  </details>
  <div class="sub-tabs" data-subgroup="essence">{"".join(era_tabs)}</div>
  {"".join(era_panels)}
</section>

<footer>
  <div>数据每日自动同步自 <a href="https://bbs.robomaster.com" target="_blank" rel="noopener">bbs.robomaster.com</a> · 本次构建于 {STAMP}</div>
  <div><a href="./all.html">去全量索引查 {total:,} 篇帖子 →</a></div>
</footer>
"""

# ---------- Full Index Page (all.html) ----------
all_body = f"""
<section class="idx-head">
  <h1>全量帖子索引</h1>
  <p>一共 {total:,} 篇（老论坛迁移 {nleg:,} 篇 + 新论坛公开 {len(listed):,} 篇），支持空格多关键词组合搜。</p>
</section>

<div class="sheet idx-bar">
  <input id="q" class="search-in" type="search" placeholder="搜标题、作者或正文简介（支持空格组合，比如：雷达 点云 / 轮腿 LQR / 超电）…">
  <select id="fYear" aria-label="按年份筛选"><option value="">全部年份</option></select>
  <select id="fCat" aria-label="按来源筛选">
    <option value="">全部来源</option>
    <option value="NEW">仅新论坛</option>
    <option value="LEGACY">仅老论坛档案</option>
    <option value="WIKI">专栏 (WIKI)</option>
    <option value="FAQ">问答 (FAQ)</option>
  </select>
  <select id="fSort" aria-label="排序方式">
    <option value="views">按浏览量高到低</option>
    <option value="newest">按发布时间最新</option>
    <option value="oldest">按发布时间最早</option>
  </select>
</div>

<div class="idx-meta">
  <span id="fc">加载中…</span>
  <span>老论坛浏览量为快照数据，新论坛每日刷新</span>
</div>

<div class="sheet tblwrap">
  <table>
    <thead><tr><th>年月</th><th>标题</th><th>浏览</th><th>帖号</th></tr></thead>
    <tbody id="idxBody"></tbody>
  </table>
</div>

<div class="pager">
  <button id="prevPage">← 上一页</button>
  <span id="pageInfo">1 / 1</span>
  <button id="nextPage">下一页 →</button>
</div>

<footer>
  <div>本次同步于 {STAMP} · 已过滤战队私有 Wiki 节点</div>
  <div><a href="./">← 返回技术图鉴</a></div>
</footer>
<script id="corpus-data" type="application/json">{compact_json}</script>
"""

# ---------- Write Outputs & Copy Static Assets ----------
os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
for fn in ("bg.webp", "favicon.png"):
    src = os.path.join(ROOT, "assets", fn)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(OUT, "assets", fn))
for fn in ("atlas.js", "index_search.js"):
    shutil.copy2(os.path.join(ROOT, "static", fn), os.path.join(OUT, "assets", fn))

p1 = os.path.join(OUT, "index.html")
p2 = os.path.join(OUT, "all.html")
open(p1, "w", encoding="utf-8").write(shell("RM 论坛技术图鉴", "atlas", atlas_body))
open(p2, "w", encoding="utf-8").write(
    shell("RM 论坛全量索引", "all", all_body, f'<script src="./assets/index_search.js?v={SEARCH_VER}"></script>')
)

latest_id = max((a["id"] for a in listed), default=0)
json.dump(
    {"latest_id": latest_id, "total": total, "stamp": STAMP},
    open(os.path.join(OUT, "state.json"), "w", encoding="utf-8"),
)
print(
    f"OK index.html={os.path.getsize(p1):,}B all.html={os.path.getsize(p2):,}B "
    f"state.latest_id={latest_id} | 语料 {total:,} ({'offline' if OFFLINE else 'online'})"
)
