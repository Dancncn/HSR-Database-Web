# HSR Database 文档（中文）

## 快速入口
- 主说明：[HSR 主说明](../README.md)
- 英文：[English](README.en-US.md)
- 日文：[日本語](README.ja-JP.md)
- 韩文：[한국어](README.ko-KR.md)

## 默认数据库目录
数据库文件默认输出到仓库内：`hsrdb/database/`

- `hsrdb/database/hsr_resources.db`
- `hsrdb/database/hsr_resources_lite.db`
- `hsrdb/database/hsr_resources_avatar.db`
- `hsrdb/database/hsr_resources_dialogue.db`
- `hsrdb/database/hsr_resources_mission.db`
- `hsrdb/database/hsr_resources_item.db`
- `hsrdb/database/hsr_resources_monster.db`

## 常用命令
构建完整库：
```powershell
python hsrdb/build_db.py --profile full --force
```

构建 Lite 库：
```powershell
python hsrdb/build_db.py --profile lite --force
```

拆分模块库：
```powershell
python hsrdb/build_module_dbs.py --force
```

启动服务：
```powershell
python hsrdb/serve.py --db-path hsrdb/database/hsr_resources_lite.db
```


