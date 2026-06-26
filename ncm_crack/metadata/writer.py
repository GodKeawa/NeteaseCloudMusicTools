import warnings
from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3
from mutagen.id3._frames import TIT2, TPE1, TPE2, TALB, TDRC, COMM, TLEN, APIC
from mutagen.mp3 import MP3

from ..core.models import NcmInfo
from ..utils.image import download_image

def set_mp3_metadata(mp3_path: str, info: NcmInfo, cover_data: bytes | None = None) -> bool:
    """为 MP3 文件设置元数据"""
    try:
        audio: MP3 = MP3(mp3_path, ID3=ID3)
        try:
            audio.add_tags()
        except Exception:
            pass

        if info.music_name:
            audio.tags["TIT2"] = TIT2(encoding=3, text=info.music_name)

        if info.artist:
            artists = info.artist
            if isinstance(artists, list):
                artist_names = [a[0] if isinstance(a, list) and a else str(a) for a in artists]
                text = "; ".join(artist_names)
            else:
                text = str(artists)
            audio.tags["TPE1"] = TPE1(encoding=3, text=text)
            audio.tags["TPE2"] = TPE2(encoding=3, text=text)

        if info.album:
            audio.tags["TALB"] = TALB(encoding=3, text=info.album)

        if info.publish_time:
            year = str(info.publish_time)[:4]
            audio.tags["TDRC"] = TDRC(encoding=3, text=year)

        if info.duration:
            audio.tags["TLEN"] = TLEN(encoding=3, text=str(info.duration))

        comments = []
        if info.alias:
            comments.append("别名: " + "; ".join(info.alias))
        if info.trans_names:
            comments.append("翻译: " + "; ".join(info.trans_names))
        if info.music_id:
            comments.append(f"163_key: {info.music_id}")
        if comments:
            audio.tags["COMM"] = COMM(encoding=3, lang="chi", desc="", text="\n".join(comments))

        if cover_data:
            audio.tags["APIC"] = APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # Cover (front)
                desc="Cover",
                data=cover_data,
            )

        audio.save()
        return True
    except Exception as e:
        warnings.warn(f"设置 MP3 元数据失败: {e}")
        return False

def set_flac_metadata(flac_path: str, info: NcmInfo, cover_data: bytes | None = None) -> bool:
    """为 FLAC 文件设置元数据"""
    try:
        audio = FLAC(flac_path)

        if info.music_name:
            audio["TITLE"] = info.music_name

        if info.artist:
            artists = info.artist
            if isinstance(artists, list):
                artist_names = [a[0] if isinstance(a, list) and a else str(a) for a in artists]
                audio["ARTIST"] = artist_names
                audio["ALBUMARTIST"] = artist_names
            else:
                audio["ARTIST"] = str(artists)
                audio["ALBUMARTIST"] = str(artists)

        if info.album:
            audio["ALBUM"] = info.album

        if info.publish_time:
            year = str(info.publish_time)[:4]
            audio["DATE"] = year

        if info.alias:
            audio["SUBTITLE"] = info.alias

        if info.trans_names:
            audio["DESCRIPTION"] = info.trans_names

        comments = []
        if info.bitrate:
            comments.append(f"Bitrate: {info.bitrate // 1000} kbps")
        if info.duration:
            comments.append(f"Duration: {info.duration / 1000:.2f}s")
        if info.music_id:
            comments.append(f"163_key: {info.music_id}")
        if comments:
            audio["COMMENT"] = "; ".join(comments)

        if cover_data:
            picture = Picture()
            picture.type = 3  # Cover (front)
            picture.mime = "image/jpeg"
            picture.desc = "Cover"
            picture.data = cover_data

            audio.clear_pictures()
            audio.add_picture(picture)

        audio.save()
        return True
    except Exception as e:
        warnings.warn(f"设置 FLAC 元数据失败: {e}")
        return False

def set_audio_metadata(audio_path: str | Path, info: NcmInfo, download_cover: bool = True) -> bool:
    """为音频文件设置元数据"""
    audio_path = Path(audio_path)
    file_format = audio_path.suffix.lower()[1:]

    cover_data = None
    if download_cover and info.album_pic_url:
        temp_cover = audio_path.parent / f".temp_{audio_path.stem}_cover.jpg"
        try:
            if download_image(info.album_pic_url, str(temp_cover)):
                with open(temp_cover, "rb") as f:
                    cover_data = f.read()
                temp_cover.unlink()
        except Exception as e:
            warnings.warn(f"下载封面失败: {e}")
            if temp_cover.exists():
                temp_cover.unlink()

    try:
        if file_format == "mp3":
            return set_mp3_metadata(str(audio_path), info, cover_data)
        elif file_format == "flac":
            return set_flac_metadata(str(audio_path), info, cover_data)
        else:
            warnings.warn(f"不支持的音频格式: {file_format}")
            return False
    except Exception as e:
        warnings.warn(f"设置元数据失败: {e}")
        return False
