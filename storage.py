import json
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

import config
from models import Pin

logger = logging.getLogger(__name__)


def init_db() -> None:
    """DB 및 테이블 초기화"""
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pins (
                pin_id      TEXT PRIMARY KEY,
                keyword     TEXT NOT NULL,
                image_url   TEXT,
                image_path  TEXT,
                saves       INTEGER DEFAULT 0,
                hearts      INTEGER DEFAULT 0,
                scraped_at  TEXT,
                source_url  TEXT
            )
        """)
        conn.commit()
    logger.info("DB 초기화 완료: %s", config.DB_PATH)


def is_duplicate(pin_id: str) -> bool:
    """해당 pin_id가 이미 DB에 존재하는지 확인"""
    with sqlite3.connect(config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM pins WHERE pin_id = ?", (pin_id,)
        ).fetchone()
    return row is not None


def filter_new_pins(pins: list[Pin]) -> list[Pin]:
    """DB에 없는 핀만 반환"""
    return [p for p in pins if not is_duplicate(p.pin_id)]


def save_pin(pin: Pin) -> None:
    """핀 메타데이터를 DB에 저장"""
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO pins
                (pin_id, keyword, image_url, image_path, saves, hearts, scraped_at, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pin.pin_id,
            pin.keyword,
            pin.image_url,
            pin.image_path,
            pin.saves,
            pin.hearts,
            str(pin.scraped_at),
            pin.source_url,
        ))
        conn.commit()
    logger.debug("DB 저장: %s (saves=%d, hearts=%d)", pin.pin_id, pin.saves, pin.hearts)


def save_metadata_json(pins: list[Pin], keyword: str, today: Optional[date] = None) -> None:
    """output/{keyword}/{date}/metadata.json 저장"""
    if today is None:
        today = date.today()

    out_dir = Path(config.OUTPUT_DIR) / _safe_dirname(keyword) / str(today)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = [
        {
            "pin_id": p.pin_id,
            "source_url": p.source_url,
            "image_url": p.image_url,
            "image_path": p.image_path,
            "saves": p.saves,
            "hearts": p.hearts,
            "score": p.score,
            "scraped_at": str(p.scraped_at),
        }
        for p in pins
    ]

    meta_path = out_dir / "metadata.json"
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("metadata.json 저장: %s", meta_path)


def _safe_dirname(name: str) -> str:
    """파일시스템에서 사용 불가한 문자 제거"""
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
