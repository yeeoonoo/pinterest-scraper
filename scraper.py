"""
Playwright 기반 Pinterest 스크래퍼.

네트워크 응답을 가로채어 Pinterest 내부 API JSON을 수집한다.
개별 핀 상세 페이지 방문 없이 hearts 수집 가능.

※ 비로그인 방식으로 동작: saves(repin_count)는 로그인 없이 제공되지 않으므로
  hearts(reaction_counts) 기준으로 정렬한다.
"""

import logging
import random
import time

from playwright.sync_api import Response, sync_playwright

import config
from models import Pin
from parser import deduplicate, extract_pins_from_response, filter_by_keyword, sort_pins

logger = logging.getLogger(__name__)

PINTEREST_SEARCH_URL = "https://www.pinterest.com/search/pins/?q={query}"


class PinterestScraper:
    def __init__(self):
        self._collected_pins: list[Pin] = []
        self._raw_items: dict[str, dict] = {}   # pin_id → 원본 API 응답 항목
        self._current_keyword: str = ""

    def scrape(self, keyword: str) -> list[Pin]:
        """키워드 검색 후 상위 N개 핀 반환."""
        self._collected_pins = []
        self._raw_items = {}
        self._current_keyword = keyword

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.SCRAPE["headless"])
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.on("response", self._on_response)

            self._search_and_scroll(page, keyword)

            context.close()
            browser.close()

        # 중복 제거 → 키워드 필터 → 정렬 → 상위 N개
        pins = deduplicate(self._collected_pins)
        pins = filter_by_keyword(pins, keyword, self._raw_items)
        pins = sort_pins(pins, config.SCRAPE["sort_by"])
        top_n = pins[: config.SCRAPE["top_n"]]

        logger.info(
            "[%s] 수집 완료: 전체 %d개 → 중복제거 후 %d개 → 필터 후 %d개 → 상위 %d개 선택",
            keyword,
            len(self._collected_pins),
            len(deduplicate(self._collected_pins)),
            len(pins),
            len(top_n),
        )
        return top_n

    # ------------------------------------------------------------------
    # 네트워크 인터셉트
    # ------------------------------------------------------------------

    def _on_response(self, response: Response) -> None:
        """Pinterest 검색 API 응답을 가로채어 핀 데이터 수집"""
        url = response.url
        if "BaseSearchResource" not in url and "RelatedModules" not in url:
            return
        if response.status != 200:
            return
        try:
            data = response.json()
            pins, raw_items = extract_pins_from_response(data, self._current_keyword)
            if pins:
                self._collected_pins.extend(pins)
                self._raw_items.update(raw_items)
                logger.debug("인터셉트: %d개 핀 추가 (누적 %d개)", len(pins), len(self._collected_pins))
        except Exception as e:
            logger.debug("응답 파싱 실패: %s", e)

    # ------------------------------------------------------------------
    # 검색 + 스크롤
    # ------------------------------------------------------------------

    def _search_and_scroll(self, page, keyword: str) -> None:
        """검색 페이지 이동 후 스크롤하며 핀 수집"""
        url = PINTEREST_SEARCH_URL.format(query=keyword.replace(" ", "+"))
        logger.info("검색 중: %s", keyword)
        page.goto(url, wait_until="domcontentloaded")
        self._delay()

        scroll_count = config.SCRAPE["scroll_count"]
        for i in range(scroll_count):
            page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            self._delay()
            logger.debug("스크롤 %d/%d (수집 중: %d개)", i + 1, scroll_count, len(self._collected_pins))

            # 충분히 수집되면 조기 종료
            if len(self._collected_pins) >= config.SCRAPE["top_n"] * 5:
                logger.debug("충분한 핀 수집, 스크롤 조기 종료")
                break

    # ------------------------------------------------------------------
    # 유틸
    # ------------------------------------------------------------------

    def _delay(self, min_sec: float | None = None, max_sec: float | None = None) -> None:
        """봇 감지 방지용 랜덤 딜레이"""
        lo = min_sec if min_sec is not None else config.SCRAPE["delay_min"]
        hi = max_sec if max_sec is not None else config.SCRAPE["delay_max"]
        time.sleep(random.uniform(lo, hi))
