import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from ..core.models import NcmInfo

class DatabaseManager:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self.lock, self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_path TEXT UNIQUE,
                    output_path TEXT,
                    format TEXT,
                    music_id INTEGER,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    bitrate INTEGER,
                    duration INTEGER,
                    publish_time INTEGER,
                    alias TEXT,
                    trans_names TEXT,
                    album_pic_url TEXT,
                    has_lyric INTEGER DEFAULT 0,
                    convert_time DATETIME
                )
            """)

    def _clean_artist(self, artist_raw) -> str:
        if not artist_raw:
            return ""
        if isinstance(artist_raw, str):
            return artist_raw
        if isinstance(artist_raw, list):
            names = []
            for item in artist_raw:
                if isinstance(item, list) and len(item) > 0:
                    names.append(str(item[0]))
                elif isinstance(item, dict) and "name" in item:
                    names.append(str(item["name"]))
                else:
                    names.append(str(item))
            return "/".join(names)
        return str(artist_raw)

    def is_converted(self, original_path: str) -> bool:
        with self.lock:
            cursor = self.conn.execute("SELECT 1 FROM songs WHERE original_path = ?", (original_path,))
            return cursor.fetchone() is not None

    def add_record(self, original_path: str, output_path: str, info: NcmInfo):
        artist_str = self._clean_artist(info.artist)
        alias_str = json.dumps(info.alias, ensure_ascii=False) if info.alias else ""
        trans_str = json.dumps(info.trans_names, ensure_ascii=False) if info.trans_names else ""
        has_lyric_val = info.has_lyric if info.has_lyric is not None else 0
        
        with self.lock, self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO songs (
                    original_path, output_path, format, music_id,
                    title, artist, album, bitrate, duration,
                    publish_time, alias, trans_names, album_pic_url, has_lyric, convert_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                original_path, output_path, info.format, info.music_id,
                info.music_name, artist_str, info.album, info.bitrate, info.duration,
                info.publish_time, alias_str, trans_str, info.album_pic_url, has_lyric_val, datetime.now()
            ))

    def delete_record(self, original_path: str):
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM songs WHERE original_path = ?", (original_path,))

    def close(self):
        self.conn.close()
