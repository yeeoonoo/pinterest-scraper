"""
Pinterest API 응답(JSON) 파싱 모듈.

Playwright로 네트워크 응답을 가로채어 Pinterest 내부 API의
핀 데이터를 파싱한다. DOM 파싱보다 안정적이며,
개별 핀 상세 페이지 진입 없이 saves/hearts를 수집할 수 있다.
"""

import logging
from typing import Any

from models import Pin

logger = logging.getLogger(__name__)

# Pinterest 내부 검색 API 응답 경로
_SEARCH_RESOURCE = "BaseSearchResource"
_RELATED_RESOURCE = "RelatedModulesResource"


def extract_pins_from_response(data: dict, keyword: str) -> list[Pin]:
    """
    Pinterest API JSON 응답에서 Pin 목록 추출.
    응답 구조가 달라도 results 배열을 재귀 탐색하여 처리.
    """
    results = _find_results(data)
    pins = []
    for item in results:
        pin = _parse_item(item, keyword)
        if pin:
            pins.append(pin)
    return pins


def _find_results(data: dict) -> list[dict]:
    """응답 JSON에서 핀 배열 위치 탐색"""
    # 구조 1: resource_response.data.results
    try:
        return data["resource_response"]["data"]["results"]
    except (KeyError, TypeError):
        pass
    # 구조 2: resource_response.data (배열)
    try:
        items = data["resource_response"]["data"]
        if isinstance(items, list):
            return items
    except (KeyError, TypeError):
        pass
    return []


def _parse_item(item: Any, keyword: str) -> Pin | None:
    """핀 단일 항목 파싱"""
    if not isinstance(item, dict):
        return None

    pin_id = item.get("id") or item.get("pin_id")
    if not pin_id:
        return None

    image_url = _extract_image_url(item)
    if not image_url:
        return None

    source_url = f"https://www.pinterest.com/pin/{pin_id}/"
    saves = _extract_saves(item)
    hearts = _extract_hearts(item)

    return Pin(
        pin_id=str(pin_id),
        source_url=source_url,
        image_url=image_url,
        keyword=keyword,
        saves=saves,
        hearts=hearts,
    )


def _extract_image_url(item: dict) -> str:
    """이미지 URL 추출 (해상도 우선순위: orig > 736x > 474x)"""
    images = item.get("images", {})
    for key in ("orig", "736x", "474x", "236x"):
        img = images.get(key)
        if img and img.get("url"):
            return img["url"]
    return ""


def _extract_saves(item: dict) -> int:
    """저장수(repin_count) 추출"""
    val = item.get("repin_count") or item.get("save_count") or 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _extract_hearts(item: dict) -> int:
    """하트/반응수 추출"""
    # reaction_counts: {"1": N} 형태
    reaction_counts = item.get("reaction_counts") or {}
    if isinstance(reaction_counts, dict):
        total = sum(int(v) for v in reaction_counts.values() if str(v).isdigit())
        if total > 0:
            return total

    # aggregated_pin_data 내부에 있는 경우
    agg = item.get("aggregated_pin_data") or {}
    saves_from_agg = agg.get("saves") or 0
    try:
        return int(saves_from_agg)
    except (ValueError, TypeError):
        return 0


def sort_pins(pins: list[Pin], sort_by: str = "auto") -> list[Pin]:
    """
    핀 목록 정렬.
    - "saves": saves 기준
    - "hearts": hearts 기준
    - "auto": saves 우선, 없으면 hearts
    """
    if sort_by == "saves":
        key = lambda p: p.saves
    elif sort_by == "hearts":
        key = lambda p: p.hearts
    else:
        key = lambda p: p.score

    return sorted(pins, key=key, reverse=True)


def deduplicate(pins: list[Pin]) -> list[Pin]:
    """같은 pin_id 중복 제거 (점수 높은 것 유지)"""
    seen: dict[str, Pin] = {}
    for pin in pins:
        if pin.pin_id not in seen or pin.score > seen[pin.pin_id].score:
            seen[pin.pin_id] = pin
    return list(seen.values())
