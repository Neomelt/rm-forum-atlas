# RM 论坛技术图鉴

[bbs.robomaster.com](https://bbs.robomaster.com) 创站以来全部公开帖子的统计画像与技术索引，每日自动更新。

**在线访问：https://neomelt.github.io/rm-forum-atlas/**

## 内容

- 论坛十二年生命史、技术热词编年史、开源学校榜等全史统计图
- 93 项开源技术点图鉴（按主题分组，附直达链接）
- 65 篇远古精华（逐篇读过正文并实测链接存活后收录）
- 1 万余帖全量索引（按年分组、浏览量排序、实时过滤）

## 数据与更新

- 老论坛（2015–2024 Discuz 迁移档案）：逐 id 枚举快照，存于 `data/legacy_corpus.json`，不再变化
- 新论坛公开帖（文章/专栏/问答）：GitHub Actions 每日 09:17（北京时间）拉取官方列表接口重算全部图表并部署
- 编辑内容（图鉴/精华，`blocks/`）为 2026-08 人工评估结果

## 本地构建

```bash
python3 generate.py . dist/index.html   # 需联网(约 50 个列表请求)
```
