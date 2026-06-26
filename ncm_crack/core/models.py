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
