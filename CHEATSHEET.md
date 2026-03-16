# Waypoints — 操作手册

> 所有操作的精确指令。电脑路径：`/Users/yaner/Developer/Waypoints`

---

## 一、访问网站

| 目的 | 操作 |
|------|------|
| 线上网站 | 直接打开 → [rougeetnoir.github.io/waypoints](https://rougeetnoir.github.io/waypoints/) |
| 本地预览 | 见下方「本地预览」 |
| Admin 管理界面 | 见下方「启动 Admin UI」 |

---

## 二、日常操作（已有电脑，已配好环境）

### 启动 Admin UI（推荐方式）

```bash
cd /Users/yaner/Developer/Waypoints
venv/bin/python scripts/admin.py
```

浏览器打开 → `http://localhost:5001`
密码在 `.env` 文件里（`ADMIN_PASSWORD=...`）

Admin UI 可以：
- 浏览所有地点（按分类筛选）
- 粘贴 Google Maps URL 添加新地点
- 删除、修改分类/备注/名称
- 点击 **Build & Deploy** 一键发布到线上

### 本地预览网站（不启动 admin）

```bash
cd /Users/yaner/Developer/Waypoints
python3 -m http.server 8080 --directory docs
```

浏览器打开 → `http://localhost:8080`

---

## 三、添加新地点（三种方式）

### 方式 A — Admin UI（最简单）

1. 启动 Admin UI（见上）
2. 点击右上角 **+ Add Place**
3. 粘贴 Google Maps 链接（如 `https://maps.google.com/maps/place/...`）
4. 选择分类（Food / Cafe / Shopping / ...）
5. 可选：填写备注、街区
6. 点击 **Add**
7. 点击 **Build & Deploy** → 等待日志完成 → 线上更新

### 方式 B — 一键脚本

```bash
cd /Users/yaner/Developer/Waypoints
# 先手动编辑 japan_places.json 添加条目，再：
./update.sh "add new cafe in Harajuku"
```

### 方式 C — 完全手动

```bash
# 1. 编辑地点数据
nano japan_places.json   # 或用任意编辑器

# 2. 拉取 API 数据（只处理新增地点，不重复调用旧地点）
venv/bin/python scripts/enrich_places.py

# 3. 重新生成 HTML
venv/bin/python scripts/build_site.py

# 4. 提交并发布
git add .
git commit -m "add new place"
git push
```

---

## 四、`japan_places.json` 字段说明

```json
{
  "id": 61,
  "name": "地点名称",
  "category": "food",          // food / cafe / shopping / vintage / sightseeing / hotel / spa / neighborhood
  "neighborhood": "Shibuya",   // 街区（可选）
  "notes": "个人备注",         // 显示在卡片底部（可选）
  "maps_url": "https://maps.google.com/...",  // Google Maps 链接
  "place_id": ""               // 留空，enrich 脚本会自动填充
}
```

---

## 五、换电脑部署（新环境完整配置）

```bash
# 1. 克隆仓库
git clone https://github.com/Rougeetnoir/waypoints.git
cd waypoints

# 2. 创建虚拟环境并安装依赖
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. 创建 .env 文件（复制模板再填写真实值）
cp .env.example .env
```

编辑 `.env`，填入三个值：
```
GOOGLE_PLACES_API_KEY=AIza...    # Google Places API Key
ADMIN_PASSWORD=your_password      # Admin 登录密码
FLASK_SECRET=any_random_string    # Flask session 密钥（随意填）
```

```bash
# 4. 因为 places_enriched.json 已在 git 里，直接 build 即可（无需重新 enrich）
venv/bin/python scripts/build_site.py

# 5. 启动 Admin UI
venv/bin/python scripts/admin.py
```

> **注意**：如果你添加了新地点需要 enrich（调用 Places API），才需要 `GOOGLE_PLACES_API_KEY`。
> 只是浏览/预览已有地点，只需要 `ADMIN_PASSWORD` 和 `FLASK_SECRET`。

---

## 六、Google Places API Key 申请（首次 / 换账号时）

1. 打开 [console.cloud.google.com](https://console.cloud.google.com)
2. 创建项目（或选已有项目）
3. 左侧菜单 → **APIs & Services** → **Enable APIs**
4. 搜索并启用 **Places API (New)**（注意：不是旧版 Places API）
5. 左侧 → **Credentials** → **Create Credentials** → **API Key**
6. 复制 key 填入 `.env` 的 `GOOGLE_PLACES_API_KEY=`

费用：每个地点约 $0.05，$200/月免费额度，53 个地点首次 enrich ≈ $2.50。
**之后只有新增地点才调用 API，不重复收费。**

---

## 七、常见问题

**Q: Admin UI 提示端口 5001 被占用**
```bash
lsof -ti:5001 | xargs kill -9
venv/bin/python scripts/admin.py
```

**Q: 本地预览端口 8080 被占用**
```bash
python3 -m http.server 8081 --directory docs
# 改用 localhost:8081
```

**Q: 添加地点后线上没有更新**
1. 确认 Admin UI 里点了 **Build & Deploy** 且日志显示 `push` 成功
2. GitHub Pages 部署有 1-2 分钟延迟，等一等
3. 浏览器强制刷新：`Cmd + Shift + R`
4. 实在不行：无痕窗口打开确认

**Q: 换电脑后 enrich 报错找不到照片**
```bash
# photos 存在 public/images/places/ 里，需要从旧电脑复制过来
# 或者重新 enrich（会重新下载照片，但 API 只调用没有 place_id 的新地点）
venv/bin/python scripts/enrich_places.py
```

---

## 八、文件速查

| 文件 | 作用 |
|------|------|
| `japan_places.json` | 地点数据源，手动维护 |
| `data/places_enriched.json` | API 丰富后的数据缓存，自动生成 |
| `docs/index.html` | 构建产物，自动生成，不要手动改 |
| `docs/images/places/` | 地点照片，自动下载 |
| `scripts/admin.py` | 本地 Admin UI 服务器 |
| `scripts/enrich_places.py` | Places API 数据拉取（增量） |
| `scripts/build_site.py` | HTML 生成脚本 |
| `update.sh` | 一键 enrich + build + push |
| `.env` | API Key 和密码（不进 git） |

---

*最后更新：2026-03-16*
