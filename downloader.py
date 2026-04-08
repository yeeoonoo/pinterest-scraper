"""
이미지 비동기 다운로드 모듈.
httpx를 사용해 여러 이미지를 병렬로 다운로드한다.
"""

import asyncio
import logging
from datetime import date
from pathlib import Path

import httpx

import config
from models import Pin

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.pinterest.com/",
}
TIMEOUT = 30  # 초
MAX_CONCURRENT = 5  # 동시 다운로드 수


def download_images(pins: list[Pin], keyword: str, today: date | None = None) -> list[Pin]:
    """
    핀 목록의 이미지를 다운로드하고 image_path를 채운 뒤 반환.
    동기 진입점 — 내부적으로 async 실행.
    """
    return asyncio.run(_download_all(pins, keyword, today or date.today()))


async def _download_all(pins: list[Pin], keyword: str, today: date) -> list[Pin]:
    out_dir = _make_output_dir(keyword, today)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        tasks = [
            _download_one(client, semaphore, pin, out_dir, idx + 1)
            for idx, pin in enumerate(pins)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # 실패한 항목 로깅, 성공한 핀만 반환
    downloaded = []
    for pin, result in zip(pins, results):
        if isinstance(result, Exception):
            logger.warning("다운로드 실패 [%s]: %s", pin.pin_id, result)
        else:
            downloaded.append(result)

    logger.info("다운로드 완료: %d/%d장", len(downloaded), len(pins))
    return downloaded


async def _download_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    pin: Pin,
    out_dir: Path,
    idx: int,
) -> Pin:
    async with semaphore:
        ext = _guess_extension(pin.image_url)
        filename = f"img_{idx:03d}{ext}"
        save_path = out_dir / filename

        if save_path.exists():
            logger.debug("이미 존재, 스킵: %s", filename)
            pin.image_path = str(save_path)
            return pin

        response = await client.get(pin.image_url)
        response.raise_for_status()
        save_path.write_bytes(response.content)

        pin.image_path = str(save_path)
        logger.debug("저장: %s (%.1f KB)", filename, len(response.content) / 1024)
        return pin


def _make_output_dir(keyword: str, today: date) -> Path:
    safe_keyword = "".join(c if c.isalnum() or c in " _-" else "_" for c in keyword).strip()
    out_dir = Path(config.OUTPUT_DIR) / safe_keyword / str(today)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _guess_extension(url: str) -> str:
    url_path = url.split("?")[0].lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if url_path.endswith(ext):
            return ext
    return ".jpg"
