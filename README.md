# HSR 资源数据库

本目录提供：

- SQLite 建库脚本（完整库 / Lite 库统一入口）
- 按模块拆分数据库脚本
- 本地查询服务和前端页面

## 文档导航

- 索引：[文档索引](docs/README.md)
- 中文：[简体中文](docs/README.zh-CN.md)
- English: [English](docs/README.en-US.md)
- 日本語：[日本語](docs/README.ja-JP.md)
- 한국어：[한국어](docs/README.ko-KR.md)

## 数据库目录

数据库文件默认放在仓库内 `hsrdb/database/`。

## 1) 准备资源

请先下载资源仓库（任选其一）：

- https://github.com/DimbreathBot/TurnBasedGameData
- https://gitlab.com/Dimbreath/turnbasedgamedata

并确保目录结构中包含 `ExcelOutput/`、`Story/`、`Config/`、`TextMap/`。
服务端动态语言加载使用 `hsrdb/TextMap/`。

## 2) 建库（统一脚本）

使用 `build_db.py`，通过 `--profile` 切换模式。

### 构建完整库（full）

```powershell
python hsrdb/build_db.py --profile full --force
```

常用参数：

- `--db-path hsrdb/database/hsr_resources.db`
- `--langs CHS,EN`
- `--skip-level-config`（只扫描 `Story/`，更快）

### 构建精简库（lite）

```powershell
python hsrdb/build_db.py --profile lite --force
```

默认输出：`hsrdb/database/hsr_resources_lite.db`  
默认来源：`hsrdb/database/hsr_resources.db`

Lite 默认策略：

- 只保留任务相关 `story_reference`
- 只保留被引用到的 `talk_sentence`
- `text_map` 仅保留查询与展示需要的哈希
- 默认语言：`CHS,EN,JP,KR`

Lite 常用参数：

- `--source-db hsrdb/database/hsr_resources.db`
- `--db-path hsrdb/database/hsr_resources_lite.db`
- `--langs CHS,EN`
- `--keep-all-story-refs`
- `--keep-all-talk`
- `--exclude-monster-text`
- `--no-vacuum`

## 3) 按模块拆分数据库

```powershell
python hsrdb/build_module_dbs.py --force
```

默认会压缩大模块体积：`dialogue` 和 `mission` 不内置 `text_map`（运行时按需加载）。

如需所有模块都内置 `text_map`：

```powershell
python hsrdb/build_module_dbs.py --text-map-modules avatar,dialogue,mission,item,monster --force
```

可选：手动指定源库（full 或 lite）：

```powershell
python hsrdb/build_module_dbs.py --source-db hsrdb/database/hsr_resources.db --force
```

```powershell
python hsrdb/build_module_dbs.py --source-db hsrdb/database/hsr_resources_lite.db --force
```

默认输出：

- `hsrdb/database/hsr_resources_avatar.db`
- `hsrdb/database/hsr_resources_dialogue.db`
- `hsrdb/database/hsr_resources_mission.db`
- `hsrdb/database/hsr_resources_item.db`
- `hsrdb/database/hsr_resources_monster.db`

## 4) 启动服务

使用完整库：

```powershell
python hsrdb/serve.py --db-path hsrdb/database/hsr_resources.db
```

使用 Lite 库：

```powershell
python hsrdb/serve.py --db-path hsrdb/database/hsr_resources_lite.db
```

使用分模块库：

```powershell
python hsrdb/serve.py `
  --db-path hsrdb/database/hsr_resources.db `
  --db-avatar hsrdb/database/hsr_resources_avatar.db `
  --db-dialogue hsrdb/database/hsr_resources_dialogue.db `
  --db-mission hsrdb/database/hsr_resources_mission.db `
  --db-item hsrdb/database/hsr_resources_item.db `
  --db-monster hsrdb/database/hsr_resources_monster.db
```

访问：

- `http://127.0.0.1:8787`

## 5) API 简表

- `GET /api/stats`
- `GET /api/search/dialogue?q=...&lang=CHS&page=1&page_size=20`
- `GET /api/dialogue/<TalkSentenceID>/refs?page=1&page_size=20`
- `GET /api/search/mission?q=...&lang=CHS&page=1&page_size=20`
- `GET /api/mission/<MainMissionID>?lang=CHS`
- `GET /api/search/avatar?q=...&lang=CHS&page=1&page_size=20`
- `GET /api/avatar/<AvatarID>?lang=CHS`
- `GET /api/search/item?q=...&lang=CHS&page=1&page_size=20&rarity=&item_main_type=&item_sub_type=`
- `GET /api/item/<ItemID>?lang=CHS`
- `GET /api/item/facets`
- `GET /api/search/monster?q=...&lang=CHS&page=1&page_size=20`
- `GET /api/monster/<MonsterID>?lang=CHS`
- `GET /api/monster/facets`
- `GET /api/term/explain?term=...&lang=CHS&limit=5`
- `GET /api/search/text?q=...&lang=CHS&page=1&page_size=20`

