import os

# -------------------------------------------------------
# 수집 키워드 목록 (여러 개 추가 가능)
# -------------------------------------------------------
KEYWORDS = [
    "minimal interior",
    # "aesthetic room",
    # "dark academia",
]

# -------------------------------------------------------
# 스크래핑 설정
# ※ 비로그인 방식으로 동작: saves는 제공되지 않으므로 hearts 기준 정렬
# -------------------------------------------------------
SCRAPE = {
    "top_n": 40,            # 수집할 이미지 수
    "scroll_count": 20,     # 스크롤 횟수 (많을수록 더 많은 후보 수집)
    "sort_by": "hearts",    # "hearts" | "auto" (saves는 비로그인 시 미제공)
    "delay_min": 1.5,       # 액션 간 최소 딜레이 (초)
    "delay_max": 3.5,       # 액션 간 최대 딜레이 (초)
    "headless": True,       # False로 바꾸면 브라우저 창이 보임 (디버깅용)
}

# -------------------------------------------------------
# 경로 설정
# -------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(BASE_DIR, "pins.db")
LOG_PATH = os.path.join(BASE_DIR, "scraper.log")
