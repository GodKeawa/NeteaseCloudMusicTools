from dataclasses import dataclass, field
from typing import Optional, List, Union, Any

@dataclass
class NcmInfo:
    """NCM 文件元数据容器"""
    
    # 基础信息
    music_id: Optional[int] = None
    music_name: Optional[str] = None
    album: Optional[str] = None
    artist: Union[str, List[Any], None] = None
    
    # 附加信息
    bitrate: Optional[int] = None
    duration: Optional[int] = None  # 毫秒
    format: str = "mp3"
    publish_time: Optional[int] = None
    
    # 额外元数据
    alias: List[str] = field(default_factory=list)
    trans_names: List[str] = field(default_factory=list)
    lyric: Optional[str] = None
    has_lyric: Optional[int] = None
    
    # 封面 (不处理封面写入，解析出URL供参考)
    album_pic_url: Optional[str] = None
    
    # 解密所需的信息
    key_data: Optional[bytes] = None
    key_box: Optional[bytearray] = None
    
    @classmethod
    def from_dict(cls, data: dict, key_data: Optional[bytes] = None, key_box: Optional[bytearray] = None) -> "NcmInfo":
        """从解析的 JSON 数据构建"""
        return cls(
            music_id=data.get("musicId"),
            music_name=data.get("musicName"),
            album=data.get("album"),
            artist=data.get("artist"),
            bitrate=data.get("bitrate"),
            duration=data.get("duration"),
            format=data.get("format", "mp3"),
            publish_time=data.get("publishTime"),
            alias=data.get("alias", []),
            trans_names=data.get("transNames", []),
            album_pic_url=data.get("albumPic"),
            key_data=key_data,
            key_box=key_box,
        )

    @classmethod
    def from_db_row(cls, row: dict) -> "NcmInfo":
        """从 SQLite 数据库行中反序列化构建 NcmInfo"""
        import json
        
        alias = []
        if row.get("alias"):
            try:
                alias = json.loads(row["alias"])
            except Exception:
                alias = [row["alias"]]
                
        trans_names = []
        if row.get("trans_names"):
            try:
                trans_names = json.loads(row["trans_names"])
            except Exception:
                trans_names = [row["trans_names"]]
                
        return cls(
            music_id=row.get("music_id"),
            music_name=row.get("title"),
            album=row.get("album"),
            artist=row.get("artist"),
            bitrate=row.get("bitrate"),
            duration=row.get("duration"),
            format=row.get("format", "mp3"),
            publish_time=row.get("publish_time"),
            album_pic_url=row.get("album_pic_url"),
            alias=alias,
            trans_names=trans_names,
            has_lyric=row.get("has_lyric"),
        )
