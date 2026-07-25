import re
import json
import base64
import binascii
from pathlib import Path
from typing import Optional
from Crypto.Cipher import AES
import mutagen

from .models import NcmInfo

def unpad(data: bytes) -> bytes:
    padding_len = data[-1] if isinstance(data[-1], int) else ord(data[-1])
    return data[:-padding_len]

def parse_163_key_from_file(file_path: str | Path) -> Optional[NcmInfo]:
    """尝试从普通的 mp3/flac 文件中读取 163 key，并解密返回 NcmInfo。"""
    try:
        audio = mutagen.File(str(file_path))
        if not audio or not audio.tags:
            return None
    except Exception:
        return None

    # 将所有标签的值拼接到一起，方便暴力正则匹配
    comment_str = ""
    try:
        for key, value in audio.tags.items():
            if isinstance(value, list):
                for item in value:
                    comment_str += f" {item}"
            else:
                # 针对 ID3 的各种 Frame (比如 COMM, TXXX)
                if hasattr(value, 'text'):
                    comment_str += f" {' '.join(value.text)}"
                elif hasattr(value, 'desc'):
                    comment_str += f" {value.desc}"
                else:
                    comment_str += f" {value}"
    except Exception:
        pass

    if not comment_str:
        return None

    # 1. 直接匹配明文的 163_key (单纯是数字 ID)
    match = re.search(r"163_key:\s*(\d+)", comment_str)
    if match:
        netease_id = int(match.group(1))
        # 这种情况下只有 ID，没有完整元数据
        return NcmInfo(music_id=netease_id, format=Path(file_path).suffix.lower()[1:])

    # 2. 匹配加密的 163 key
    matches = re.findall(r"163 key\(Don't modify\):([A-Za-z0-9+/=]+)", comment_str)
    if not matches:
        return None

    # 有些文件可能会被重复写入产生多个，或者因为截断导致短的无效，按长度排序取最长的
    matches.sort(key=len, reverse=True)
    
    for b64_str in matches:
        try:
            meta_data = base64.b64decode(b64_str)
            META_KEY = binascii.a2b_hex("2331346C6A6B5F215C5D2630553C2728")
            cipher = AES.new(META_KEY, AES.MODE_ECB)
            
            decrypted = cipher.decrypt(meta_data)
            meta_json_str = unpad(decrypted).decode("utf-8")
            
            if meta_json_str.startswith("music:"):
                meta_json_str = meta_json_str[6:]
                meta_json = json.loads(meta_json_str)
                return NcmInfo.from_dict(meta_json)
                
            elif meta_json_str.startswith("dj:"):
                meta_json_str = meta_json_str[3:]
                meta_json = json.loads(meta_json_str)
                
                # DJ 节目的特殊处理
                raw_id = meta_json.get("mainMusic", {}).get("track", {}).get("id")
                if not raw_id:
                    raw_id = meta_json.get("mainMusic", {}).get("mainTrackId")
                
                # 尽量复用 NcmInfo
                info = NcmInfo(
                    music_id=raw_id,
                    music_name=meta_json.get("mainMusic", {}).get("name") or meta_json.get("name"),
                    album=meta_json.get("mainMusic", {}).get("album") or meta_json.get("brand"),
                    artist=meta_json.get("mainMusic", {}).get("artists") or meta_json.get("dj", {}).get("nickname"),
                    bitrate=meta_json.get("mainMusic", {}).get("bMusic", {}).get("bitrate") or meta_json.get("bitrate"),
                    duration=meta_json.get("mainMusic", {}).get("bMusic", {}).get("playTime") or meta_json.get("duration"),
                    album_pic_url=meta_json.get("coverUrl"),
                    format=Path(file_path).suffix.lower()[1:]
                )
                return info
            else:
                meta_json = json.loads(meta_json_str)
                return NcmInfo.from_dict(meta_json)
                
        except Exception:
            continue

    return None
