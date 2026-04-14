# Pinterest Scraper - 프로젝트 가이드

## 프로젝트 목적

특정 키워드로 Pinterest를 검색해 하트수(hearts/reactions) 기준 상위 40개 이미지를 매일 자동 수집하는 파이썬 스크래퍼.

---

## 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| 브라우저 자동화 | `playwright` |
| 이미지 다운로드 | `httpx` (async) |
| DB | `sqlite3` (내장) |
| 스케줄링 | Windows 작업 스케줄러 |
| 설정 관리 | `config.py` |

---

## 디렉토리 구조

```
pinterest_scraper/
├── main.py              # 진입점 (Task Scheduler가 실행)
├── config.py            # 키워드, 경로 설정
├── scraper.py           # Playwright 비로그인 + 핀 수집
├── parser.py            # 하트수 파싱 + 키워드 관련성 필터
├── downloader.py        # 이미지 비동기 다운로드
├── storage.py           # SQLite CRUD
├── models.py            # Pin 데이터 클래스
├── run.py               # 더블클릭 실행용 (한글 키워드 입력 지원)
├── run.bat              # run.py 호출 진입점
├── register_task.bat    # Windows 작업 스케줄러 등록 스크립트
├── requirements.txt
├── pins.db              # SQLite DB (자동 생성)
└── output/
    └── {keyword}/
        └── {YYYY-MM-DD}/
            ├── img_001.jpg
            ├── ...
            └── metadata.json
```

---

## 설정 (`config.py`)

```python
KEYWORDS = [
    "leather jacket",
    # 추가 키워드는 여기에
]

SCRAPE = {
    "top_n": 40,
    "scroll_count": 20,
    "sort_by": "hearts",   # saves는 비로그인 시 미제공
    "delay_min": 1.5,
    "delay_max": 3.5,
    "headless": True,      # False로 변경 시 브라우저 창 표시 (디버깅용)
}
```

---

## 실행 방법

| 방법 | 명령 | 용도 |
|------|------|------|
| 더블클릭 | `run.bat` | 평소 수동 실행 (한글 키워드 입력 가능) |
| 커맨드라인 | `python main.py "키워드"` | 키워드 직접 지정 |
| 자동화 | `register_task.bat` (관리자 권한) | 매일 오전 9시 자동 실행 |

`run.bat` 실행 시 키워드 입력 → 확인 → 오타면 `n` 입력 후 재입력.

---

## 실행 흐름

1. `main.py` 실행
2. `config.py`에서 키워드 목록 로드 (커맨드라인 인자 우선)
3. 키워드별 루프:
   - Playwright로 Pinterest 검색 페이지 접근 (비로그인)
   - 네트워크 인터셉트로 Pinterest 내부 API 응답 수집
   - 무한스크롤 반복 → 핀 데이터 축적
   - 1run 내 중복(`pin_id`) 제거
   - 키워드 관련성 필터링 (메타데이터 텍스트 부분 일치)
   - hearts 기준 상위 40개 선택
   - 이미지 병렬 다운로드
   - DB 및 `metadata.json` 기록

---

## 스크래핑 방식: 네트워크 인터셉트

DOM 파싱 대신 Pinterest 내부 API 응답을 직접 가로채는 방식을 사용한다.

- 대상 엔드포인트: `BaseSearchResource`, `RelatedModulesResource`
- 응답 JSON에서 `reaction_counts`(hearts), `images`, `id` 추출
- 핀 상세 페이지 진입 불필요 → 빠르고 안정적

**비로그인 시 수집 가능 여부:**

| 필드 | 비로그인 |
|------|---------|
| `reaction_counts` (hearts) | ✅ 수집 가능 |
| `repin_count` (saves) | ❌ 미제공 |
| 이미지 URL | ✅ 수집 가능 |

---

## 키워드 관련성 필터 (`parser.py`)

수집된 핀 중 키워드와 관련 없는 이미지를 메타데이터 텍스트 기반으로 필터링한다.

**매칭 방식: 부분 일치 (포함 관계)**

키워드 토큰이 핀의 `title`, `description`, `board_name` 단어에 포함되거나,
반대로 해당 단어가 키워드 토큰에 포함되면 매칭으로 간주한다.

```
키워드: "french work jacket"
토큰:   ["french", "work", "jacket"]

핀 title: "french workwear jacket"
  - "french" ↔ "french"   → ✓
  - "work"   ↔ "workwear"  → ✓ (work ⊂ workwear)
  - "jacket" ↔ "jacket"   → ✓
→ 통과
```

모든 토큰이 하나라도 매칭되지 않으면 제외. 메타데이터가 없는 핀은 통과 처리.

---

## DB 스키마

```sql
CREATE TABLE pins (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pin_id      TEXT NOT NULL,
    keyword     TEXT,
    image_url   TEXT,
    image_path  TEXT,
    saves       INTEGER,   -- 비로그인 시 항상 0
    hearts      INTEGER,
    scraped_at  DATE,
    source_url  TEXT
);
```

중복 제거 없음: 실행할 때마다 상위 N개를 전부 저장. 같은 날 여러 번 실행해도 매번 전량 기록됨.

---

## Windows 작업 스케줄러 등록

`register_task.bat`을 관리자 권한으로 실행하면 자동 등록된다.

```
작업명: PinterestScraper
트리거: 매일 오전 09:00
동작:   python "C:\path\to\pinterest_scraper\main.py"
```

수동 등록 시:
```
schtasks /create /tn "PinterestScraper" /tr "python C:\...\main.py" /sc daily /st 09:00 /rl highest /f
```

---

## 실측 실행 시간 (1회)

| 단계 | 소요 시간 |
|------|----------|
| 검색 페이지 로드 | ~3초 |
| 스크롤 20회 + 핀 수집 | ~20초 |
| 이미지 40장 병렬 다운로드 | ~5초 |
| **총합** | **약 30초** |

---

## 초기 설치

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

---

## 개발 시 주의사항

- Pinterest는 봇 감지가 있으므로 `delay_min` / `delay_max` 값을 낮추지 말 것
- `headless: False`로 설정하면 브라우저 창을 직접 확인할 수 있어 디버깅에 유용
- Pinterest API 응답 구조가 변경될 경우 `parser.py`의 `_find_results`, `_extract_*` 함수 수정 필요
- 키워드 필터 강도 조정이 필요하면 `parser.py`의 `_matches` 함수 수정
