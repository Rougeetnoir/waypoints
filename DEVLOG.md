# Waypoints — 从想法到上线的开发记录

**日期**：2026-03-14  
**用时**：约 3 小时（单次对话完成从零到上线）

---

## 起点：一个网站激发的想法

发现参考网站 [zaraintokyo.com](https://zaraintokyo.com/) — 一个东京个人地点指南，editorial 风格，干净、有品味、个人化。想法：**能不能把 Google Maps 里的收藏夹变成这样的网站？**

---

## 阶段一：可行性分析

在动手之前，先评估整个方案是否可行、需要多少成本。

**数据来源**：Google Takeout 导出 Maps 数据  
**图片生成**：Quiver.ai（矢量插画风格 SVG）  
**前端**：Astro/HTML + frontend-design skill  
**部署**：GitHub Pages（免费）

**成本评估结论**：

| 组件 | 费用 |
|------|------|
| Google Places API（52个地点） | $0（~$2.5，被 $200/月免费额度覆盖） |
| Quiver.ai（分类插画，免费额度内） | $0 |
| 托管（GitHub Pages） | $0 |
| **总计** | **$0** |

---

## 阶段二：项目命名与工作区搭建

已有一个旅行行程项目叫 **Waylog**。新项目命名为 **Waypoints**——两者形成呼应，同属个人旅行系列。

- 在 `/Users/yaner/Developer/Waypoints/` 创建新工作区
- 从 Accountant 项目复制 `frontend-design` skill 到新 workspace
- Windsurf 切换到新 workspace

---

## 阶段三：数据探索与意外发现

### Google Takeout 数据结构

导入 `Saved Places.json` 后发现：

```
Takeout/Maps (your places)/Saved Places.json   ← 只有星标收藏（旧版导出）
Takeout 2/Maps/My labeled places/Labeled places.json  ← 新版，只有 "Home" 一条
```

**关键发现**：Google Takeout **不导出自建列表**（如 "Japan" 列表）。这是 Google 的已知限制。

### 解决方案

手动从 Google Maps 网页爬取 Japan 列表，存为结构化 JSON（`japan_places.json`），包含：
- 地点名称、分类、类型
- 评分、评论数
- 所在街区
- 个人备注
- `maps_search` 字段（用于 Places API 文字搜索）

---

## 阶段四：数据清理

原始数据 58 条，清理如下：

| 删除原因 | 条目 | 数量 |
|---------|------|------|
| 交通枢纽（不适合城市指南） | 车站 × 3、成田机场 × 1 | 4 |
| 纯功能性地点 | SMBC 银行 | 1 |
| 重复条目 | Ghibli Museum（保留有备注的版本） | 1 |

**清理后：52 条有效地点**

---

## 阶段五：Google Places API 数据丰富

编写 `scripts/enrich_places.py`：

1. 读取 `japan_places.json`
2. 用 `maps_search` 字段调用 **Text Search API** → 获取 `place_id`
3. 用 `place_id` 调用 **Place Details API** → 地址、网站、营业时间
4. 下载 **Place Photos** 到 `public/images/places/`
5. 输出 `data/places_enriched.json`

**踩坑**：第一次运行全部 403，原因是启用了旧版 Places API 而非新版 Places API (New)。  
**解决**：在 GCP 控制台启用正确的 API 后重新运行。

**最终结果**：52/52 地点全部丰富，52 张照片下载完毕。

---

## 阶段六：静态站点构建

编写 `scripts/build_site.py`，生成 `docs/index.html`：

**设计方向**（frontend-design skill 指导）：
- **风格**：Japanese Magazine / Editorial — Kinfolk 遇上东京
- **配色**：羊皮纸暖白 (`#F4F0E8`) + 深墨色 (`#1A1714`) + 朱红点缀 (`#C8251F`)
- **字体**：Cormorant（display 衬线） + DM Mono（标签等宽）
- **质感**：SVG 噪点叠层，模拟纸张颗粒感

**设计迭代**：

| 版本 | 调整内容 |
|------|---------|
| v1 | 3列布局，4:3图片，底部"Open in Maps →"文字链接 |
| v2 | 改为5列布局，卡片更紧凑 |
| v3 | 图片改16:9（更扁），Maps 链接改为内联 pin 图标 |

---

## 阶段七：GitHub 部署

```bash
git init
git add .
git commit -m "Initial commit: Waypoints Japan guide v1"
gh repo create waypoints --public --source=. --remote=origin --push
gh api repos/Rougeetnoir/waypoints/pages --method POST -f 'source[branch]=main' -f 'source[path]=/docs'
```

**上线地址**：[rougeetnoir.github.io/waypoints](https://rougeetnoir.github.io/waypoints/)

---

## 最终项目结构

```
waypoints/
  japan_places.json          # 52个精选地点（手动整理 + 清理）
  scripts/
    enrich_places.py         # Places API 数据丰富脚本
    build_site.py            # 静态站点生成脚本（含完整 CSS/JS）
  data/places_enriched.json  # API丰富后的数据（本地生成，gitignored）
  docs/                      # 构建产物 → GitHub Pages
    index.html               # 43KB 单文件站点
    images/places/           # 52张本地照片（7.8MB）
  .env                       # API Key（gitignored）
  .env.example
  requirements.txt           # requests, python-dotenv
  README.md
  DEVLOG.md                  # 本文件
```

---

## 经验总结

- **Google Takeout 的限制**：只导出星标，不导出自建列表 — 需手动处理
- **Places API (New) vs 旧版**：两者是不同 SKU，要开启正确的那个
- **静态优先**：不用 Astro/Next.js，纯 Python 生成 HTML，零构建依赖，GitHub Pages 原生支持
- **照片本地化**：Places API 照片 URL 会过期，构建时下载到本地是正确做法
- **设计原则**：frontend-design skill 的核心是"bold aesthetic direction" — 确定一个方向，彻底执行，而非折中

---

## 后续计划

- [ ] 用 Quiver.ai 为每个分类生成 SVG 插画，替代或补充照片
- [ ] 添加 Starred Places（台北/香港/澳门）作为第二个城市指南
- [ ] 考虑加入全文搜索（Fuse.js，纯前端，无需后端）
- [ ] 自定义域名（可选）
