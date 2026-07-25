import requests
import time
import json
import base64
import binascii
from hashlib import md5
from os import urandom
from typing import Optional, Dict, Any, List
from Crypto.Cipher import AES

MODULUS = (
    "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7"
    "b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280"
    "104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932"
    "575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b"
    "3ece0462db0a22b8e7"
)
PUBKEY = "010001"
NONCE = b"0CoJUm6Qyw8W8jud"
LINUXKEY = b"rFgB&h#%2?^eDg:Q"

def create_key(size):
    return binascii.hexlify(urandom(size))[:16]

def aes_encrypt(text: bytes, key: bytes, mode, iv=None):
    pad = 16 - len(text) % 16
    text = text + bytearray([pad] * pad)
    if mode == AES.MODE_CBC:
        encryptor = AES.new(key, mode, iv)
    else:
        encryptor = AES.new(key, mode)
    return encryptor.encrypt(text)

def rsa_encrypt(text: bytes, pubkey: str, modulus: str):
    text = text[::-1]
    rs = pow(int(binascii.hexlify(text), 16), int(pubkey, 16), int(modulus, 16))
    return format(rs, "x").zfill(256)

def weapi_encrypt(text: dict):
    data = json.dumps(text).encode("utf-8")
    secret = create_key(16)
    
    params = aes_encrypt(data, NONCE, AES.MODE_CBC, b"0102030405060708")
    params = base64.b64encode(params)
    params = aes_encrypt(params, secret, AES.MODE_CBC, b"0102030405060708")
    params = base64.b64encode(params).decode('utf-8')
    
    encseckey = rsa_encrypt(secret, PUBKEY, MODULUS)
    return {"params": params, "encSecKey": encseckey}

def linuxapi_encrypt(text: dict):
    data = json.dumps(text).encode('utf-8')
    ciphertext = aes_encrypt(data, LINUXKEY, AES.MODE_ECB)
    return {"eparams": binascii.hexlify(ciphertext).decode('utf-8').upper()}

class NeteaseClient:
    BASE_URL = "https://music.163.com/"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36",
            "Referer": self.BASE_URL,
            "Content-Type": "application/x-www-form-urlencoded"
        })

    def _post(self, path: str, data: dict, encrypt_method="weapi"):
        if encrypt_method == "linuxapi":
            url = self.BASE_URL + "api/linux/forward"
            payload = linuxapi_encrypt({"method": "POST", "url": self.BASE_URL + path, "params": data})
        else:
            url = self.BASE_URL + path
            payload = weapi_encrypt(data)

        try:
            resp = self.session.post(url, data=payload, timeout=10)
            result = resp.json()
            print(f"[{path}] API Response: {json.dumps(result, ensure_ascii=False)}")
            return result
        except Exception as e:
            print(f"API 请求失败: {e}")
            return {}

    def fetch_lyric(self, music_id: int) -> str:
        """获取原版歌词内容（如果存在）"""
        data = self._post("api/song/lyric?lv=-1&kv=-1&tv=-1", {"id": music_id}, "linuxapi")
        return data.get("lrc", {}).get("lyric", "")

    def fetch_bilingual_lyric(self, music_id: int) -> str:
        """获取双语歌词（将翻译歌词和原版歌词按时间轴合并）"""
        data = self._post("api/song/lyric?lv=-1&kv=-1&tv=-1", {"id": music_id}, "linuxapi")
        lrc = data.get("lrc", {}).get("lyric", "")
        tlyric = data.get("tlyric", {}).get("lyric", "")
        
        if not tlyric:
            return lrc
            
        import re
        pattern = re.compile(r'\[(\d{2}:\d{2}\.\d+)\](.*)')
        
        lrc_dict = {}
        # 提取 metadata 标签如 [by:xxx] 等没有秒级时间戳的行
        meta_lines = []
        
        for line in lrc.splitlines():
            match = pattern.match(line)
            if match:
                ts, text = match.groups()
                lrc_dict[ts] = [text]
            else:
                if line.strip():
                    meta_lines.append(line)
                    
        for line in tlyric.splitlines():
            match = pattern.match(line)
            if match:
                ts, text = match.groups()
                if ts in lrc_dict and text.strip():
                    lrc_dict[ts].append(text)
            else:
                if line.strip() and not line.startswith("[by:"):
                    meta_lines.append(line)
                    
        merged = []
        merged.extend(meta_lines)
        
        for ts in sorted(lrc_dict.keys()):
            for text in lrc_dict[ts]:
                merged.append(f"[{ts}]{text}")
                
        return "\n".join(merged)

    def fetch_song_detail(self, music_id: int) -> Optional[Dict[str, Any]]:
        """获取歌曲详细信息，返回兼容 NcmInfo 的字段字典"""
        data = self._post("api/song/detail", {"ids": f"[{music_id}]"}, "linuxapi")
        songs = data.get("songs", [])
        if not songs:
            return None
            
        song = songs[0]
        
        artists = []
        if song.get("artists"):
            artists = [ar.get("name") for ar in song.get("artists")]
            
        album = song.get("album", {}).get("name", "")
        album_pic_url = song.get("album", {}).get("picUrl", "")
        
        year = None
        if song.get("album", {}).get("publishTime"):
            # publishTime 是毫秒时间戳
            import datetime
            year = datetime.datetime.fromtimestamp(song["album"]["publishTime"] / 1000).year

        return {
            "musicId": music_id,
            "musicName": song.get("name"),
            "artist": artists,
            "album": album,
            "alias": song.get("alias", []),
            "transNames": song.get("transNames", []),
            "publishTime": year,
            "albumPic": album_pic_url,
            "duration": song.get("duration"),
            "raw_data": song,
        }

    def search_song(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索歌曲"""
        data = self._post("weapi/cloudsearch/get/web", {'s': keyword, 'type': '1', 'limit': '10', 'offset': '0'}, "weapi")
        songs = data.get("result", {}).get("songs", [])
        results = []
        for song in songs:
            artists = [ar.get("name") for ar in song.get("ar", [])]
            results.append({
                "musicId": song.get("id"),
                "musicName": song.get("name"),
                "artist": artists,
                "album": song.get("al", {}).get("name", ""),
                "alias": song.get("alia", []),
                "raw_data": song,
            })
        return results
