# HSR Database Docs (English)

## Quick Links
- Main guide: [HSR Main Guide](../README.md)
- Chinese: [简体中文](README.zh-CN.md)
- Japanese: [日本語](README.ja-JP.md)
- Korean: [한국어](README.ko-KR.md)

## Default Database Directory
Database files are now generated under `hsrdb/database/`

- `hsrdb/database/hsr_resources.db`
- `hsrdb/database/hsr_resources_lite.db`
- `hsrdb/database/hsr_resources_avatar.db`
- `hsrdb/database/hsr_resources_dialogue.db`
- `hsrdb/database/hsr_resources_mission.db`
- `hsrdb/database/hsr_resources_item.db`
- `hsrdb/database/hsr_resources_monster.db`

## Common Commands
Build full DB:
```powershell
python hsrdb/build_db.py --profile full --force
```

Build lite DB:
```powershell
python hsrdb/build_db.py --profile lite --force
```

Split module DBs:
```powershell
python hsrdb/build_module_dbs.py --force
```

Run server:
```powershell
python hsrdb/serve.py --db-path hsrdb/database/hsr_resources_lite.db
```


