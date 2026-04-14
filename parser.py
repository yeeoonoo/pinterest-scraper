"""
Pinterest API 응답(JSON) 파싱 모듈.

Playwright로 네트워크 응답을 가로채어 Pinterest 내부 API의
핀 데이터를 파싱한다. DOM 파싱보다 안정적이며,
개별 핀 상세 페이지 진입 없이 saves/hearts를 수집할 수 있다.
"""

import logging
import re
from typing import Any

from models import Pin

logger = logging.getLogger(__name__)

# 매칭 시 무시할 불용어 (너무 짧거나 의미 없는 단어)
_STOPWORDS = {"a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "with"}

# Pinterest 내부 검색 API 응답 경로
_SEARCH_RESOURCE = "BaseSearchResource"
_RELATED_RESOURCE = "RelatedModulesResource"


def extract_pins_from_response(data: dict, keyword: str) -> tuple[list[Pin], dict[str, dict]]:
    """
    Pinterest API JSON 응답에서 Pin 목록과 원본 항목 dict 추출.
    반환: (pins, {pin_id: raw_item}) — raw_item은 키워드 필터링에 사용
    """
    results = _find_results(data)
    pins = []
    raw_items = {}
    for item in results:
        pin = _parse_item(item, keyword)
        if pin:
            pins.append(pin)
            raw_items[pin.pin_id] = item
    return pins, raw_items


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


def filter_by_keyword(pins: list[Pin], keyword: str, raw_items: dict[str, dict]) -> list[Pin]:
    """
    키워드 토큰 기준으로 관련 없는 핀 제거.

    매칭 방식: 키워드 토큰이 메타데이터 단어에 포함되거나(부분 일치),
    메타데이터 단어가 키워드 토큰에 포함되면 해당 토큰은 매칭된 것으로 간주.

    예) 키워드 "french work jacket", 제목 "french workwear jacket"
        - "french" ↔ "french" → ✓
        - "work"   ↔ "workwear" → ✓ (work ⊂ workwear)
        - "jacket" ↔ "jacket"  → ✓

    키워드 토큰 중 하나라도 매칭되지 않으면 제외.
    메타데이터가 아예 없는 핀은 통과시킴 (텍스트 없는 핀 보호).
    """
    tokens = _keyword_tokens(keyword)
    if not tokens:
        return pins

    result = []
    for pin in pins:
        item = raw_items.get(pin.pin_id, {})
        text = _extract_metadata_text(item)
        if not text or _matches(tokens, text):
            result.append(pin)
        else:
            logger.debug("필터 제외: pin_id=%s, 텍스트=%s", pin.pin_id, text[:80])

    logger.info("키워드 필터: %d개 → %d개 (제외 %d개)", len(pins), len(result), len(pins) - len(result))
    return result


def _keyword_tokens(keyword: str) -> list[str]:
    """키워드를 소문자 토큰 리스트로 변환, 불용어 및 2자 미만 제거"""
    tokens = re.findall(r"[a-zA-Z가-힣0-9]+", keyword.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) >= 2]


def _extract_metadata_text(item: dict) -> str:
    """핀 메타데이터에서 검색 가능한 텍스트 추출"""
    parts = [
        item.get("title") or "",
        item.get("description") or "",
        item.get("grid_title") or "",
        (item.get("board") or {}).get("name") or "",
    ]
    return " ".join(filter(None, parts)).lower()


def _matches(tokens: list[str], text: str) -> bool:
    """모든 키워드 토큰이 텍스트에서 부분 일치하는지 확인"""
    text_words = re.findall(r"[a-zA-Z가-힣0-9]+", text)
    for token in tokens:
        matched = any(token in word or word in token for word in text_words)
        if not matched:
            return False
    return True


def deduplicate(pins: list[Pin]) -> list[Pin]:
    """같은 pin_id 중복 제거 (점수 높은 것 유지)"""
    seen: dict[str, Pin] = {}
    for pin in pins:
        if pin.pin_id not in seen or pin.score > seen[pin.pin_id].score:
            seen[pin.pin_id] = pin
    return list(seen.values())
