"""
Pinterest Scraper 진입점.
Windows 작업 스케줄러가 매일 이 파일을 실행한다.

    python main.py                        # config.py의 KEYWORDS 사용
    python main.py "aesthetic room"       # 키워드 직접 지정
    python main.py "dark academia" "minimal interior"  # 여러 키워드
"""

import logging
import sys
from datetime import date

import config
import storage
from downloader import download_images
from scraper import PinterestScraper

# ------------------------------------------------------------------
# 로깅 설정
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run() -> None:
    today = date.today()
    logger.info("===== Pinterest Scraper 시작: %s =====", today)

    # 커맨드라인 인자가 있으면 우선 사용, 없으면 config.KEYWORDS
    keywords = sys.argv[1:] if len(sys.argv) > 1 else config.KEYWORDS

    storage.init_db()
    scraper = PinterestScraper()

    for keyword in keywords:
        logger.info("키워드 처리 시작: [%s]", keyword)
        try:
            _process_keyword(scraper, keyword, today)
        except Exception as e:
            logger.error("키워드 처리 중 오류 [%s]: %s", keyword, e, exc_info=True)

    logger.info("===== Pinterest Scraper 종료 =====")


def _process_keyword(scraper: PinterestScraper, keyword: str, today: date) -> None:
    # 1. 핀 수집 (네트워크 인터셉트 방식)
    pins = scraper.scrape(keyword)
    if not pins:
        logger.warning("[%s] 수집된 핀 없음", keyword)
        return

    # 2. 이미지 다운로드
    downloaded = download_images(pins, keyword, today)
    if not downloaded:
        logger.warning("[%s] 다운로드 성공한 이미지 없음", keyword)
        return

    # 4. DB 저장 + metadata.json 저장
    for pin in downloaded:
        storage.save_pin(pin)

    storage.save_metadata_json(downloaded, keyword, today)
    logger.info("[%s] 완료: %d장 저장", keyword, len(downloaded))


if __name__ == "__main__":
    run()
