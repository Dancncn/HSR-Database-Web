# 一、项目简介与架构

本项目将 HSR 数据查询服务部署为 Cloudflare Worker API，数据库使用 Cloudflare D1。

- 运行形态：`Client -> Worker -> D1`
- 接口类型：REST 风格 `GET /api/*`
- 调试接口：`/__health`、`/__debug`
- 访问地址格式：`https://<worker-name>.<subdomain>.workers.dev`

架构图：

```text
Client
  ↓
Cloudflare Worker
  ↓
D1 Database
```

API 功能概览：

- `GET /api/stats`
- `GET /api/search/dialogue`
- `GET /api/dialogue/<TalkSentenceID>/refs`
- `GET /api/search/mission`
- `GET /api/mission/<MainMissionID>`
- `GET /api/search/avatar`
- `GET /api/avatar/<AvatarID>`
- `GET /api/search/item`
- `GET /api/item/<ItemID>`
- `GET /api/item/facets`
- `GET /api/search/monster`
- `GET /api/monster/<MonsterID>`
- `GET /api/monster/facets`
- `GET /api/term/explain`
- `GET /api/search/text`
- `GET /__health`
- `GET /__debug`

---

# 二、从零开始部署（核心流程）

## Step 1: 安装环境（Node、wrangler、登录）

```cmd
npm install -g wrangler
wrangler login
```

前置条件：

- Node.js
- npm
- Cloudflare 账号

## Step 2: 构建本地数据库（build_db.py 等）

在仓库根目录执行：

```cmd
cd /d E:\PROJECT2\HSR-Database-Web
python build_db.py
python build_module_dbs.py
```

说明：

- 会生成本地 `*.db` / `*.sqlite3` 数据库文件。
- 目的：把原始资源整合为可查询的关系型结构。

## Step 3: 导出 dump_all.sql

推荐方式（已安装 sqlite3 CLI）：

```cmd
sqlite3 <your_db_file>.sqlite3 ".dump" > dump_all.sql
```

说明：

- `dump_all.sql` 用于可重复导入 D1。
- 避免提交二进制数据库文件。
- 便于审计和环境迁移。
- 如未安装 sqlite3 CLI，请先安装后执行。

## Step 4: 生成 dump_all_d1.sql（说明精简原因）

使用仓库脚本：

```cmd
python scripts\export_sqlite_dump.py
```

说明：

- 脚本会输出 `dump_all.sql` 与 D1 兼容版 `dump_all_d1.sql`。
- `dump_all_d1.sql` 会做 D1 兼容处理与结构裁剪（去除不兼容/中间构建对象）。

## Step 5: 创建 D1 数据库

```cmd
wrangler d1 create hsrdb
wrangler d1 list
```

从输出中记录：

- `database_name`
- `database_id`

## Step 6: 修改 wrangler.jsonc（必须修改 name / database_id）

编辑 `cf_worker/wrangler.jsonc`，至少确认以下字段：

- `name`：替换为你的 Worker 名称
- `main`：应为 `src/entry.py`
- `d1_databases[0].binding`：必须与代码 `env.DB` 一致（`DB`）
- `d1_databases[0].database_name`：你的 D1 名称
- `d1_databases[0].database_id`：替换为你自己的 ID

可用配置检查命令：

```cmd
cd /d E:\PROJECT2\HSR-Database-Web\cf_worker
wrangler --config wrangler.jsonc d1 list
```

## Step 7: 导入 dump_all_d1.sql

```cmd
cd /d E:\PROJECT2\HSR-Database-Web
wrangler --config cf_worker\wrangler.jsonc d1 execute hsrdb --remote --file=.\dump_all_d1.sql
```

如文件很大可拆分执行：

```cmd
wrangler d1 execute hsrdb --remote --file dump_schema.sql
wrangler d1 execute hsrdb --remote --file dump_data_part1.sql
wrangler d1 execute hsrdb --remote --file dump_data_part2.sql
```

## Step 8: 本地开发测试

```cmd
cd /d E:\PROJECT2\HSR-Database-Web\cf_worker
wrangler --config wrangler.jsonc dev --ip 127.0.0.1 --port 8787
```

另开 CMD 验证：

```cmd
curl -i http://127.0.0.1:8787/__health
curl -i http://127.0.0.1:8787/api/stats
```

## Step 9: wrangler deploy 部署

```cmd
cd /d E:\PROJECT2\HSR-Database-Web\cf_worker
wrangler --config wrangler.jsonc deploy
```

查看日志：

```cmd
wrangler --config wrangler.jsonc tail --format pretty
```

## Step 10: 使用 curl 验证接口

```cmd
curl -i https://<worker>.<subdomain>.workers.dev/__health
curl -i https://<worker>.<subdomain>.workers.dev/api/stats
curl -i "https://<worker>.<subdomain>.workers.dev/api/search/dialogue?q=test&lang=CHS&page=1&page_size=5"
curl -i "https://<worker>.<subdomain>.workers.dev/api/avatar/1001?lang=CHS"
```

导入结果核验：

```cmd
wrangler d1 execute hsrdb --remote --command="SELECT COUNT(*) AS tables FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
wrangler d1 execute hsrdb --remote --command="SELECT type, COUNT(*) AS cnt FROM sqlite_master GROUP BY type ORDER BY cnt DESC;"
```

---

# 三、本地全量数据库 vs 线上精简数据库说明

- 本地全量数据库规模：约 165 张表。
- 线上 D1 实际业务结构：约 66 张业务表（统计时排除 `sqlite_%`）。
- 差异原因：上线前会移除构建中间表、冗余表、临时表、非 API 必需表，并保留可服务接口的最终查询表与索引。
- 结论：精简版并非数据缺失，而是结构裁剪与部署适配。

已测线上统计结果：

- `SELECT COUNT(*) AS tables FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';` -> `66`
- `SELECT type, COUNT(*) AS cnt FROM sqlite_master GROUP BY type ORDER BY cnt DESC;` -> `table 67, index 65`

---

# 四、常见问题与排障

## 1) workers.dev 无法访问

- 可能是网络屏蔽导致。
- 处理：更换网络或绑定自定义域名。

## 2) wrangler dev --remote 超时

- 常见于网络质量或 Cloudflare API 连接不稳定。
- 处理：重试、切换网络、临时使用本地模式调试。

## 3) 本地 D1 与线上 D1 不一致导致 500

- 本地数据不完整或表结构未同步会导致接口报错。
- 处理：优先以 `dump_all_d1.sql` 重新导入远程 D1，再联调。

## 4) SQL 语法或对象错误（SQLITE_ERROR）

- 常见原因：导入了未适配 D1 的 SQL（事务、触发器、FTS、不兼容语句等）。
- 处理：使用仓库脚本生成的 D1 兼容 dump，并重新导入。

## 5) 204 响应写法

- 对于 OPTIONS 预检等场景，需使用：

```python
Response(null, { status: 204 })
```

## 6) wrangler-account.json 是否需要手动改

- 不需要，也不建议手动编辑。
- 它是 Wrangler/Pages 本地缓存与账户文件，不应提交到 Git。
- 正确做法：`wrangler login`（CI 中使用 API Token）。
- 排障时可删除该缓存文件让 Wrangler 重新生成。

## 7) 为什么 dump_all.sql 不应提交 GitHub

- GitHub 单文件有 100MB 限制。
- dump/db 文件属于部署产物，不属于源码。
- 正确做法：通过导入命令注入 D1，不把大产物入库。

---

# 五、当前线上部署状态（附录）

- 当前项目已成功部署为 Cloudflare Worker API。
- 使用 Cloudflare D1 作为数据库。
- API 已对公网开放。
- 已验证所有核心接口 200 OK。
- Pages 前端尚未部署（API 独立可用）。
- 本地 D1 不完整会导致 500，这是开发阶段常见问题。
- 某些网络可能无法访问 `*.workers.dev`（需更换网络或使用自定义域名）。

当前地址格式示例：

`https://<worker-name>.<subdomain>.workers.dev`

---
