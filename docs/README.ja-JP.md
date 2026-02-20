# HSR Database ドキュメント（日本語）

## クイックリンク
- メインガイド：[HSRメインガイド](../README.md)
- 中国語：[简体中文](README.zh-CN.md)
- 英語：[English](README.en-US.md)
- 韓国語：[한국어](README.ko-KR.md)

## デフォルトDBディレクトリ
DBファイルの出力先は `hsrdb/database/` です。

- `hsrdb/database/hsr_resources.db`
- `hsrdb/database/hsr_resources_lite.db`
- `hsrdb/database/hsr_resources_avatar.db`
- `hsrdb/database/hsr_resources_dialogue.db`
- `hsrdb/database/hsr_resources_mission.db`
- `hsrdb/database/hsr_resources_item.db`
- `hsrdb/database/hsr_resources_monster.db`

## よく使うコマンド
フルDB作成：
```powershell
python hsrdb/build_db.py --profile full --force
```

Lite DB作成：
```powershell
python hsrdb/build_db.py --profile lite --force
```

モジュール分割：
```powershell
python hsrdb/build_module_dbs.py --force
```

サーバー起動：
```powershell
python hsrdb/serve.py --db-path hsrdb/database/hsr_resources_lite.db
```


