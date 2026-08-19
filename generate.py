#!/usr/bin/env python3
"""RM 论坛技术图鉴·合体页生成器。
用法: python3 generate.py <repo_root> <out_dir>  (产出 index.html 与 all.html)
payload: data/legacy_corpus.json + blocks/*.html (相对仓库根)
联网: 拉取 bbs.robomaster.com 三类公开列表(约50请求)。失败则非零退出、不产出。
"""
import json,sys,re,html,collections,subprocess,time,datetime

ROOT, OUT = sys.argv[1], sys.argv[2]
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
API="https://bbs.robomaster.com/developers-server/rest/posts/list"
FIELDS=['id','title','authorNickname','teamInfo','tags','views','approvals','comments','createAt','marrow','official','timesCited','introduction','category','history']

def pull(cat):
    out=[]; page=1
    while True:
        body=json.dumps({"pageSize":50,"pageNo":page,"filter":{"category":cat}})
        for attempt in range(5):
            r=subprocess.run(["curl","-sL","--max-time","25","-A",UA,"-H","Content-Type: application/json",
                "-X","POST",API,"-d",body],capture_output=True)
            try:
                d=json.loads(r.stdout); assert d.get('code')==0
                # 软限流会返回 code:0 + 空列表——首页拿到空且已知该类非空时按失败重试
                assert d['data']['list'] or (page>1)
                break
            except Exception:
                if attempt==4: raise RuntimeError(f"API {cat} p{page} 五次失败: {r.stdout[:120]!r}")
                time.sleep(3*(attempt+1))
        lst=d['data']['list']
        if not lst: break
        out += [{k:a.get(k) for k in FIELDS} for a in lst]
        if page*50>=d['data']['total']: break
        page+=1; time.sleep(0.25)
    return out

fresh={}
for cat in ("ARTICLE","WIKI","FAQ"):
    got=pull(cat)
    print(f"  {cat}: {len(got)} 条",file=sys.stderr)
    for a in got: fresh[a['id']]=a
    time.sleep(1)
assert len(fresh)>1100, f"列表拉取仅 {len(fresh)} 条,疑似异常,拒绝发布"
legacy=json.load(open(ROOT+'/data/legacy_corpus.json'))
merged={a['id']:a for a in legacy}
merged.update(fresh)                      # 新数据覆盖(views 更新)
corpus=list(merged.values())
listed=list(fresh.values())
NOW=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
STAMP=NOW.strftime('%Y-%m-%d %H:%M')
CUR_Y=NOW.year; CUR_YM=NOW.strftime('%Y-%m')

def yr(a): return str(a.get('createAt'))[:4]
def ym(a): return str(a.get('createAt'))[:7]
def v(a): return a.get('views') or 0

# ---------- SVG 工具 ----------
def hbar(x0,y,w,h,r,cls):
    r=min(r,h/2,max(w,0.01))
    return f'<path class="{cls}" d="M{x0},{y} h{max(w-r,0):.1f} a{r},{r} 0 0 1 {r},{r} v{h-2*r:.1f} a{r},{r} 0 0 1 -{r},{r} h-{max(w-r,0):.1f} z"/>'
def vbar(x,yb,w,hg,r,cls):
    r=min(r,w/2,max(hg,0.01))
    return f'<path class="{cls}" d="M{x},{yb} v-{max(hg-r,0):.1f} a{r},{r} 0 0 1 {r},-{r} h{w-2*r:.1f} a{r},{r} 0 0 1 {r},{r} v{max(hg-r,0):.1f} z"/>'
def hbarchart(rows,xmax,L,fmt=lambda v:str(v)):
    rh=30; H=len(rows)*rh+16; pw=860-L-52
    p=[f'<svg viewBox="0 0 860 {H}" role="img">']
    for i,(k,val) in enumerate(rows):
        y=8+i*rh; bw=pw*val/xmax
        p.append(f'<text class="rlab" x="{L-8}" y="{y+15}" text-anchor="end">{html.escape(str(k))}</text>')
        p.append(f'<g class="hit">{hbar(L,y+4,bw,14,4,"s1")}<title>{html.escape(str(k))}: {fmt(val)}</title></g>')
        p.append(f'<text class="dlab" x="{L+bw+6:.1f}" y="{y+15}">{fmt(val)}</text>')
    return ''.join(p)+'</svg>'

# ---------- 图1 年度 ----------
yc=collections.Counter(yr(a) for a in corpus)
years=[str(y) for y in range(2015,CUR_Y+1)]
ymax=max(2000,max(yc.get(y,0) for y in years))
W,H,L,T,B=860,240,44,18,30; pw,ph=W-L-16,H-T-B; n=len(years); bw=pw/n-8
p=[f'<svg viewBox="0 0 {W} {H}" role="img">']
step=500
for gv in range(0,ymax+1,step):
    gy=T+ph*(1-gv/ymax)
    p.append(f'<line class="grid" x1="{L}" y1="{gy:.1f}" x2="{W-16}" y2="{gy:.1f}"/><text class="tick" x="{L-6}" y="{gy+4:.1f}" text-anchor="end">{gv}</text>')
for i,y in enumerate(years):
    val=yc.get(y,0); x=L+i*(pw/n)+4; hg=ph*val/ymax
    p.append(f'<g class="hit">{vbar(x,T+ph,bw,hg,3,"s1")}<title>{y}: {val} 帖</title></g>')
    p.append(f'<text class="dlab" x="{x+bw/2:.1f}" y="{T+ph-hg-5:.1f}" text-anchor="middle">{val}</text>')
    p.append(f'<text class="tick" x="{x+bw/2:.1f}" y="{H-10}" text-anchor="middle">{y}</text>')
svg_year=''.join(p)+'</svg>'

# ---------- 图2 热词热力图 ----------
WORDS=[('图传/通信',r'图传|通信|链路|FEC'),('视觉/OpenCV',r'视觉|OpenCV|opencv'),('PID/控制入门',r'PID|pid'),
('陀螺/反陀螺',r'小陀螺|反陀螺|陀螺仪?'),('飞镖/制导',r'飞镖|制导'),('雷达站',r'雷达'),
('超级电容',r'超级电容|超电'),('轮腿/平衡',r'轮腿|轮足|平衡步兵|平衡底盘'),('导航/SLAM',r'导航|SLAM|slam|建图|定位'),
('仿真/sim2real',r'仿真|sim2real|Sim2Real|Gazebo|MuJoCo'),('神经网络/学习',r'神经网络|深度学习|YOLO|yolo|强化学习'),('卡尔曼/EKF',r'卡尔曼|EKF|KF\b')]
yw={y:collections.Counter() for y in years}
for a in corpus:
    y=yr(a)
    if y not in yw: continue
    txt=(a.get('title') or '')+' '+(a.get('introduction') or '')
    for w,pat in WORDS:
        if re.search(pat,txt): yw[y][w]+=1
L2=118; cw=(860-L2-16)/len(years); ch=30; H2=len(WORDS)*ch+50
p=[f'<svg viewBox="0 0 860 {H2}" role="img">']
for j,y in enumerate(years):
    p.append(f'<text class="tick" x="{L2+j*cw+cw/2:.0f}" y="16" text-anchor="middle">{y[2:]}</text>')
for i,(w,_) in enumerate(WORDS):
    y0=26+i*ch; vals=[yw[y][w] for y in years]; mx=max(vals) or 1
    p.append(f'<text class="rlab" x="{L2-8}" y="{y0+ch/2+4:.0f}" text-anchor="end">{w}</text>')
    for j,val in enumerate(vals):
        x=L2+j*cw; op=0.05+0.95*(val/mx) if val else 0.04
        p.append(f'<g class="hit"><rect x="{x+1:.1f}" y="{y0+1}" width="{cw-2:.1f}" height="{ch-2}" rx="4" class="s1" fill-opacity="{op:.2f}"/><title>{w} {years[j]}: {val} 帖</title></g>')
        if val: p.append(f'<text class="{"cthi" if op>0.55 else "dlab"}" x="{x+cw/2:.1f}" y="{y0+ch/2+4}" text-anchor="middle">{val}</text>')
svg_heat=''.join(p)+'</svg>'

# ---------- 图3 月度(新论坛) ----------
mon=collections.Counter(ym(a) for a in listed if ym(a)>='2024-06')
months=sorted(mon)
mmax=max(100,max(mon.values()))
n=len(months); bw=(860-44-16)/n-3
p=[f'<svg viewBox="0 0 860 240" role="img">']
for gv in range(0,mmax+1,25):
    gy=18+188*(1-gv/mmax)
    p.append(f'<line class="grid" x1="44" y1="{gy:.1f}" x2="844" y2="{gy:.1f}"/><text class="tick" x="38" y="{gy+4:.1f}" text-anchor="end">{gv}</text>')
peak=sorted(months,key=lambda m:-mon[m])[:4]
for i,m in enumerate(months):
    val=mon[m]; x=44+i*((860-60)/n)+1.5; hg=188*val/mmax
    p.append(f'<g class="hit">{vbar(x,206,bw,hg,3,"s1")}<title>{m}: {val} 篇</title></g>')
    if m in peak: p.append(f'<text class="dlab" x="{x+bw/2:.1f}" y="{206-hg-5:.1f}" text-anchor="middle">{val}</text>')
    if m.endswith('-01') or i==0: p.append(f'<text class="tick" x="{x+bw/2:.1f}" y="226" text-anchor="middle">{m[:4]}</text>')
svg_month=''.join(p)+'</svg>'

# ---------- 图4 学校榜(全史) ----------
def school(a):
    ti=a.get('teamInfo')
    if isinstance(ti,dict):
        c=ti.get('colleges')
        if c: return c[0].get('collegeName')
    m=re.search(r'([一-鿿]{2,12}(?:大学|学院))',a.get('title') or '')
    return m.group(1) if m else None
sc=collections.Counter()
for a in corpus:
    s=school(a)
    if s: sc[s]+=1
top_sc=sc.most_common(10)
svg_school=hbarchart(top_sc,max(60,top_sc[0][1]),150)

# ---------- 图5 兵种(列表口径) ----------
KIND=['步兵','英雄','工程','哨兵','空中机器人','飞镖系统','雷达','场地道具']
kind=collections.Counter()
for a in listed:
    for t in (a.get('tags') or []):
        if t.get('name') in KIND: kind[t['name']]+=1
rows=[(k.replace('机器人','').replace('系统',''),kind[k]) for k in sorted(KIND,key=lambda k:-kind[k])]
svg_kind=hbarchart(rows,max(260,rows[0][1]),96)

# ---------- 图6 被引榜 ----------
cited=sorted(corpus,key=lambda a:-(a.get('timesCited') or 0))[:10]
rows=[((a['title'] or '')[:26],a['timesCited'] or 0) for a in cited]
svg_cited=hbarchart(rows,max(110,rows[0][1]),252)

# ---------- 表: 最新/远古热帖/新论坛热度/赞率 ----------
def linkrow(a,extra=''):
    return (f'<tr><td class="n">{v(a):,}</td><td>{html.escape((a.get("title") or "")[:60])}{extra}</td>'
            f'<td class="lk"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">{a["id"]}</a></td></tr>')
latest=sorted(listed,key=lambda a:str(a.get('createAt')),reverse=True)[:15]
t_latest='\n'.join(f'<tr><td class="n">{str(a.get("createAt"))[:10]}</td><td>{html.escape((a.get("title") or "")[:62])}</td><td class="n">{v(a):,}</td><td class="lk"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">{a["id"]}</a></td></tr>' for a in latest)
anc=sorted((a for a in corpus if a.get('history')),key=lambda a:-v(a))[:9]
t_anc='\n'.join(linkrow(a,f'<span class="cc">{ym(a)}</span>') for a in anc)
SKIP=('公告','官方信息','宣传','组织建设','项目管理')
tech=[a for a in listed if not any(t.get('name') in SKIP for t in (a.get('tags') or []))]
hot=sorted(tech,key=lambda a:-v(a))[:10]
t_hot='\n'.join(linkrow(a) for a in hot)
el=[a for a in listed if v(a)>=3000]
liked=sorted(el,key=lambda a:-(a.get('approvals') or 0)/v(a))[:6]
t_liked='\n'.join(f'<tr><td class="n">{(a.get("approvals") or 0)/v(a)*1000:.1f}‰</td><td>{html.escape((a.get("title") or "")[:58])}</td><td class="lk"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">{a["id"]}</a></td></tr>' for a in liked)

# ---------- 全量索引 ----------
byy=collections.defaultdict(list)
for a in corpus:
    y=yr(a)
    if y.isdigit(): byy[y].append(a)
secs=[]
for y in sorted(byy,reverse=True):
    items=sorted(byy[y],key=lambda a:-v(a))
    rws=[]
    for a in items:
        t=html.escape((a.get('title') or '(无题)').strip()[:80])
        cc={'FAQ':'<span class="cc">问答</span>','WIKI':'<span class="cc">专栏</span>'}.get(a.get('category'),'')
        rws.append(f'<tr data-t="{t.lower()}"><td class="ti"><a href="https://bbs.robomaster.com/article/{a["id"]}" target="_blank" rel="noopener">{t}</a>{cc}</td><td class="n">{v(a):,}</td><td class="n">{str(a.get("createAt"))[5:7]}月</td></tr>')
    op=' open' if y in (str(CUR_Y),str(CUR_Y-1)) else ''
    secs.append(f'<details{op} data-year="{y}"><summary>{y} 年 <span class="cnt">{len(items):,} 帖</span></summary><div class="tblwrap"><table><tr><th>标题</th><th>浏览</th><th>月份</th></tr>{"".join(rws)}</table></div></details>')
index_html='\n'.join(secs)

total=len(corpus); tviews=sum(v(a) for a in corpus); nleg=sum(1 for a in corpus if a.get('history'))

head_raw=open(ROOT+'/blocks/block_head.html').read()
EXTRA_CSS="""
.filter{position:sticky;top:0;background:var(--bg);padding:12px 0;z-index:5;border-bottom:1px solid var(--line);margin-bottom:14px}
.filter input{width:100%;padding:10px 14px;font-size:15px;border:1.5px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);font-family:inherit}
.filter input:focus{outline:2px solid var(--accent);border-color:var(--accent)}
.fcount{font-size:12.5px;color:var(--muted);margin-top:6px}
details{background:var(--surface);border:1px solid var(--line);border-radius:8px;margin-bottom:10px}
summary{cursor:pointer;padding:12px 16px;font-weight:700;font-size:16px}
summary .cnt{color:var(--muted);font-weight:400;font-size:13px;margin-left:8px}
td.ti a{color:var(--ink);text-decoration:none}
td.ti a:hover{color:var(--accent);text-decoration:underline}
.cc{display:inline-block;font-size:10.5px;color:var(--accent);background:var(--code-bg);border-radius:4px;padding:0 5px;margin-left:6px;vertical-align:1px}
tr.hid{display:none}
.stamp{display:inline-block;background:var(--accent-soft);color:var(--accent);border-radius:99px;padding:2px 12px;font-size:12.5px;font-weight:700}
.pnav{display:flex;gap:8px;margin:0 0 22px}
.pnav a{padding:7px 18px;border:1px solid var(--line);border-radius:99px;text-decoration:none;color:var(--muted);font-weight:700;font-size:13.5px;background:var(--surface)}
.pnav a.on{background:var(--accent);color:#fff;border-color:var(--accent)}
</style>"""
essence=open(ROOT+'/blocks/block_essence.html').read()
catalog=open(ROOT+'/blocks/block_catalog.html').read()

def shell(title,body,script=''):
    head=head_raw.replace('<title>RM 论坛技术图鉴</title>',f'<title>{title}</title>').replace('</style>',EXTRA_CSS)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="RoboMaster 论坛全史统计画像、开源技术点索引与远古精华,每日自动更新">
{head}
</head>
<body>
<div class="wrap">
{body}
</div>
{script}
</body>
</html>"""

def navi(cur):
    a=' class="on"' if cur=='atlas' else ''
    b=' class="on"' if cur=='all' else ''
    return f'<nav class="pnav"><a href="./"{a}>图鉴</a><a href="./all.html"{b}>全量索引</a></nav>'

atlas_body=f"""{navi('atlas')}<header class="hero">
<div class="eyebrow">bbs.robomaster.com · 每日自动更新</div>
<h1>RM 论坛技术图鉴</h1>
<div class="meta">论坛创站以来 <b>{total:,} 帖</b>的全史统计画像、<b>93 项</b>开源技术点与 <b>65 篇</b>远古精华。<span class="stamp">数据截至 {STAMP}</span></div>
</header>
<div class="tiles">
<div class="tile"><b>{total:,}</b><span>全量帖子（2015-02 起）</span></div>
<div class="tile"><b>{tviews/1e8:.2f}亿</b><span>总浏览量</span></div>
<div class="tile"><b>{nleg:,}</b><span>远古帖（老论坛迁移）</span></div>
<div class="tile"><b>{len(listed):,}</b><span>新论坛公开帖</span></div>
<div class="tile"><b>93 / 65</b><span>图鉴收录 / 远古精华</span></div>
<div class="tile"><b>{CUR_Y-2015}.5 年</b><span>时间跨度</span></div>
</div>

<h2>最新动态</h2>
<div class="tblwrap"><table><tr><th>日期</th><th>标题</th><th>浏览</th><th>帖号</th></tr>
{t_latest}
</table></div>

<h2>统计画像</h2>
<figure><figcaption>论坛生命史：<em>创站热潮 → 老论坛衰退 → 迁移低谷 → 新论坛复兴</em>（年度发帖量）</figcaption>
<p class="fignote">{CUR_Y} 年数据截至当月。</p>{svg_year}</figure>
<figure><figcaption>技术热词编年史：<em>每个技术方向的诞生年清晰可辨</em></figcaption>
<p class="fignote">按标题+简介关键词匹配，逐行按各词自身峰值归一化上色。{CUR_Y} 年仅含年初至今。</p>{svg_heat}</figure>
<figure><figcaption>月度发帖量（新论坛，2024-06 起）：<em>8–9 月是赛后开源收获季</em></figcaption>{svg_month}</figure>
<figure><figcaption>开源学校榜（全史）：<em>开源声望以「代」为单位积累</em></figcaption>{svg_school}</figure>
<figure><figcaption>兵种标签分布（新论坛列表口径）</figcaption>
<p class="fignote">一帖可挂多标签；雷达帖数对应最小的上场数量——单位机器人开源密度最高的是雷达。</p>{svg_kind}</figure>
<figure><figcaption>被引用次数榜：<em>社区的「谱系根节点」</em></figcaption>
<p class="fignote">被引 = 被其它帖子引用的次数（新论坛功能），衡量一篇开源被当作基础设施的程度。</p>{svg_cited}</figure>

<h3>远古热帖 TOP（浏览以百万计）</h3>
<div class="tblwrap"><table><tr><th>浏览</th><th>帖子</th><th>帖号</th></tr>{t_anc}</table></div>
<p class="fignote">远古区浏览量为 2026-08 快照，不随每日更新变动。</p>
<h3>新论坛技术帖热度 TOP10（按标签剔除公告/宣传类）</h3>
<div class="tblwrap"><table><tr><th>浏览</th><th>帖子</th><th>帖号</th></tr>{t_hot}</table></div>
<h3>赞率 TOP（每千浏览获赞，浏览≥3000）</h3>
<div class="tblwrap"><table><tr><th>赞率</th><th>帖子</th><th>帖号</th></tr>{t_liked}</table></div>

{essence}
{catalog}

<footer>数据截至 {STAMP}（每日自动刷新）· 全量检索见「全量索引」页 · 图鉴 93 项与远古精华 65 篇为 2026-08 编辑内容</footer>"""

all_body=f"""{navi('all')}<header class="hero">
<div class="eyebrow">bbs.robomaster.com · 每日自动更新</div>
<h1>RM 论坛全量索引</h1>
<div class="meta">全部 <b>{total:,} 帖</b>：按年分组、组内按浏览量降序、标题实时过滤。<span class="stamp">数据截至 {STAMP}</span></div>
</header>
<p class="sub">口径：老论坛迁移档案全量（id 1–30000 枚举快照，浏览量为 2026-08 快照）+ 新论坛公开列表（文章/专栏/问答，每日刷新）；战队私有 wiki 模板节点已排除；新论坛未过审帖不可枚举。</p>
<div class="filter"><input id="q" type="search" placeholder="过滤标题…（如：陀螺 / 超级电容 / 雷达 / 轮腿 / 开源）"><div class="fcount" id="fc">共 {total:,} 帖</div></div>
{index_html}
<footer>数据截至 {STAMP}（每日自动刷新）</footer>"""

all_script=f"""<script>
const q=document.getElementById('q'),fc=document.getElementById('fc');
const rows=[...document.querySelectorAll('tr[data-t]')];
const dets=[...document.querySelectorAll('details[data-year]')];
let tm=null;
q.addEventListener('input',()=>{{clearTimeout(tm);tm=setTimeout(run,140)}});
function run(){{
  const s=q.value.trim().toLowerCase();
  let n=0;
  if(!s){{rows.forEach(r=>r.classList.remove('hid'));dets.forEach(d=>{{d.style.display='';d.open=['{CUR_Y}','{CUR_Y-1}'].includes(d.dataset.year)}});fc.textContent='共 {total:,} 帖';return}}
  dets.forEach(d=>{{
    let k=0;
    d.querySelectorAll('tr[data-t]').forEach(r=>{{const hit=r.dataset.t.includes(s);r.classList.toggle('hid',!hit);if(hit)k++}});
    d.style.display=k?'':'none';d.open=k>0;n+=k;
  }});
  fc.textContent='命中 '+n.toLocaleString()+' 帖';
}}
</script>"""

import os
os.makedirs(OUT,exist_ok=True)
p1=os.path.join(OUT,'index.html'); p2=os.path.join(OUT,'all.html')
open(p1,'w').write(shell('RM 论坛技术图鉴',atlas_body))
open(p2,'w').write(shell('RM 论坛全量索引',all_body,all_script))
print(f"OK index.html={os.path.getsize(p1):,}B all.html={os.path.getsize(p2):,}B | 语料 {total:,} (新论坛 {len(listed):,})")
