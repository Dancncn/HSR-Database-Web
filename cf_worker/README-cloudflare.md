# HSR Database API - Cloudflare 部署说明

---

## 一、当前项目状态说明

- 当前项目已成功部署为 Cloudflare Worker API。
- 使用 Cloudflare D1 作为数据库。
- API 已对公网开放。
- 已验证所有核心接口 200 OK。
- Pages 前端尚未部署（API 独立可用）。
- 本地 D1 不完整会导致 500，这是开发阶段常见问题。
- 某些网络可能无法访问 `*.workers.dev`（需更换网络或使用自定义域名）。

当前 API 访问地址格式示例：

`https://<worker-name>.<subdomain>.workers.dev`

当前主要 API 路由：

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

## 二、项目架构说明

```text
Client
  ↓
Cloudflare Worker
  ↓
D1 Database
```

- Worker 负责路由与查询。
- D1 存储结构化数据。
- 无服务器架构。
- 全球 CDN 分发。
- 自动扩展。

---

## 三、如何从零部署到 Cloudflare

### 1. 前置条件

- Node.js
- npm
- Cloudflare 账号
- 已安装 wrangler

安装命令示例：

```bash
npm install -g wrangler
```

登录：

```bash
wrangler login
```

---

### 2. 创建 D1 数据库

示例命令：

```bash
wrangler d1 create hsrdb
```

在 wrangler 配置中添加：

```toml
[[d1_databases]]
binding = "DB"
database_name = "hsrdb"
database_id = "<your-database-id>"
```

---

### 3. 导入数据库结构与数据

```bash
wrangler d1 execute hsrdb --file schema.sql
wrangler d1 execute hsrdb --file seed.sql
```

---

### 4. 本地开发验证

```bash
wrangler dev
```

验证接口：

```bash
curl http://127.0.0.1:8787/__health
```

说明：

- 本地 D1 不完整会导致 500。
- 可以使用远程 D1 进行开发。

---

### 5. 部署上线

```bash
wrangler deploy
```

说明：

- 发布成功后即可通过 workers.dev 访问。
- 可通过 `wrangler tail` 查看实时日志。

---

### 6. 常见问题

- workers.dev 无法访问（网络屏蔽问题）。
- `wrangler dev --remote` 连接超时。
- 本地 D1 与线上 D1 不一致导致 500。
- SQL 语法错误导致 `SQLITE_ERROR`。
- `204` 响应必须使用 `Response(null, { status: 204 })`。

---

## 四、当前可对外提供的能力

- 当前 API 已可对外接入。
- 支持跨域（CORS）。
- 可用于前端网站查询。
- 可被第三方程序调用。
- 后续可增加 API Key 或 Rate Limit。

---

## 五、后续计划

- 部署 Cloudflare Pages 前端。
- 绑定自定义域名。
- 添加访问控制。
- 优化查询性能。
- 增加缓存策略。

---
## 六、数据库文件如何上传到 Cloudflare D1

### 1. 为什么不应把 dump_all.sql 等大文件提交到 GitHub

- GitHub 对单文件有 100MB 限制，超限文件无法正常推送。
- 数据库 dump 文件属于部署产物，不是源码本身。
- 这类产物不应纳入源码管理，应通过部署流程导入目标环境。

### 2. 正确上传方式

#### 方式一：使用 wrangler 执行 SQL 文件

```bash
wrangler d1 execute hsrdb --remote --file dump_all.sql
```

说明：

- `--remote` 表示执行到线上数据库。
- 如果是本地开发环境可去掉 `--remote`。
- 大文件执行时间可能较长，需等待命令完成。

### 3. SQL 文件过大时的处理方式

建议拆分为多个文件：

- `dump_schema.sql`
- `dump_data_part1.sql`
- `dump_data_part2.sql`

分别执行：

```bash
wrangler d1 execute hsrdb --remote --file dump_schema.sql
wrangler d1 execute hsrdb --remote --file dump_data_part1.sql
wrangler d1 execute hsrdb --remote --file dump_data_part2.sql
```

### 4. 验证数据是否成功导入

```bash
wrangler d1 execute hsrdb --remote --command="SELECT COUNT(*) FROM sqlite_master;"
```

或：

```bash
wrangler d1 execute hsrdb --remote --command="SELECT COUNT(*) FROM <table_name>;"
```

### 5. 当前项目采用的实际方式

- 本项目数据库通过 `dump_all.sql` 文件导入。
- 未将 dump 文件提交到 GitHub。
- 数据已成功写入 Cloudflare D1。

---
