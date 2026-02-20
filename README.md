# HSR Resources Database

This folder contains a local SQLite builder and a lightweight web UI for querying:

- Dialogue text and speaker lines (`TalkSentenceConfig + TextMap`)
- Story reference locations (`Story/` + `Config/Level/` JSON scans)
- Main/sub mission text and mission-pack mapping
- Avatar base info, promotion values, skill text, rank metadata
- Item metadata from `ItemConfig*.json` (name, description, type, rarity, purpose)

## 1) Build database

Run from repository root:

```powershell
python hsrdb/build_db.py --force
```

Optional flags:

- `--db-path hsrdb/hsr_resources.db`
- `--langs CHS,EN`
- `--skip-level-config` (faster, scans only `Story/` references)

## 2) Start query server

```powershell
python hsrdb/serve.py
```

Open:

- `http://127.0.0.1:8787`

Frontend now uses 4 paged groups:

- `Character Information`
- `Dialogue Text Search`
- `Main Quest Search`
- `Item Search`
- `Monster Search`

## API quick list

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
- `GET /api/search/text?q=...&lang=CHS&page=1&page_size=20`

## Notes
- You need download the Resources from 
- [Dim](https://github.com/DimbreathBot/TurnBasedGameData) or 
- [Mirror](https://gitlab.com/Dimbreath/turnbasedgamedata) to run this script.
Thank for all contributions and support to this project.