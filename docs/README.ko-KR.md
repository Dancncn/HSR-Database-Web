# HSR Database 문서 (한국어)

## 빠른 링크
- 메인 가이드: [HSR 메인 가이드](../README.md)
- 중국어: [简体中文](README.zh-CN.md)
- 영어: [English](README.en-US.md)
- 일본어: [日本語](README.ja-JP.md)

## 기본 DB 디렉터리
DB 파일 기본 출력 경로는 `hsrdb/database/` 입니다.

- `hsrdb/database/hsr_resources.db`
- `hsrdb/database/hsr_resources_lite.db`
- `hsrdb/database/hsr_resources_avatar.db`
- `hsrdb/database/hsr_resources_dialogue.db`
- `hsrdb/database/hsr_resources_mission.db`
- `hsrdb/database/hsr_resources_item.db`
- `hsrdb/database/hsr_resources_monster.db`

## 자주 쓰는 명령
풀 DB 생성:
```powershell
python hsrdb/build_db.py --profile full --force
```

Lite DB 생성:
```powershell
python hsrdb/build_db.py --profile lite --force
```

모듈 분리:
```powershell
python hsrdb/build_module_dbs.py --force
```

서버 실행:
```powershell
python hsrdb/serve.py --db-path hsrdb/database/hsr_resources_lite.db
```


