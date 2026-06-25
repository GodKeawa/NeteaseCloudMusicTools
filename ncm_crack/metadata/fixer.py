import warnings
from pathlib import Path

from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.id3._frames import TPE1, TPE2
from mutagen.mp3 import MP3

def fix_mp3_artist_metadata(mp3_path: str) -> bool | None:
    """修正 MP3 文件中使用 / 或混合分隔符的艺术家元数据"""
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if audio.tags is None:
            return None

        modified = False

        def clean_artist_string(artist_text):
            artist_text = artist_text.strip().rstrip(";").strip()

            if "/" not in artist_text and "; " in artist_text:
                return None, artist_text

            if "/" in artist_text or ";" in artist_text:
                artist_text = artist_text.replace(";", "/")
                artists = [a.strip() for a in artist_text.split("/") if a.strip()]
                seen = set()
                unique_artists = []
                for artist in artists:
                    if artist not in seen:
                        seen.add(artist)
                        unique_artists.append(artist)
                return True, "; ".join(unique_artists)

            return None, artist_text

        if "TPE1" in audio.tags:
            artist_text = str(audio.tags["TPE1"].text[0])
            needs_fix, cleaned_text = clean_artist_string(artist_text)
            if needs_fix:
                audio.tags["TPE1"] = TPE1(encoding=3, text=cleaned_text)
                modified = True

        if "TPE2" in audio.tags:
            album_artist_text = str(audio.tags["TPE2"].text[0])
            needs_fix, cleaned_text = clean_artist_string(album_artist_text)
            if needs_fix:
                audio.tags["TPE2"] = TPE2(encoding=3, text=cleaned_text)
                modified = True

        if modified:
            audio.save()
            return True
        return None

    except Exception as e:
        warnings.warn(f"修正 MP3 元数据失败: {e}")
        return False

def fix_flac_artist_metadata(flac_path: str) -> bool | None:
    """修正 FLAC 文件中使用 / 或 ; 分隔的艺术家元数据"""
    try:
        audio = FLAC(flac_path)
        modified = False

        def clean_artist_list(artists_input):
            new_artists = []
            needs_fix = False

            for artist in artists_input:
                artist_cleaned = artist.strip().rstrip(";").strip()

                if "/" in artist_cleaned or ";" in artist_cleaned:
                    needs_fix = True
                    parts = artist_cleaned.split(";")
                    for part in parts:
                        sub_parts = part.split("/")
                        for sub_part in sub_parts:
                            cleaned = sub_part.strip()
                            if cleaned and cleaned not in new_artists:
                                new_artists.append(cleaned)
                else:
                    if artist_cleaned and artist_cleaned not in new_artists:
                        new_artists.append(artist_cleaned)

            return new_artists, needs_fix

        if "ARTIST" in audio:
            new_artists, needs_fix = clean_artist_list(audio["ARTIST"])
            if needs_fix:
                audio["ARTIST"] = new_artists
                modified = True

        if "ALBUMARTIST" in audio:
            new_album_artists, needs_fix = clean_artist_list(audio["ALBUMARTIST"])
            if needs_fix:
                audio["ALBUMARTIST"] = new_album_artists
                modified = True

        if modified:
            audio.save()
            return True
        return None

    except Exception as e:
        warnings.warn(f"修正 FLAC 元数据失败: {e}")
        return False

def fix_audio_metadata(audio_path: str | Path) -> bool | None:
    """修正音频文件中的艺术家元数据"""
    audio_path = Path(audio_path)
    file_format = audio_path.suffix.lower()[1:]

    try:
        if file_format == "mp3":
            return fix_mp3_artist_metadata(str(audio_path))
        elif file_format == "flac":
            return fix_flac_artist_metadata(str(audio_path))
        else:
            return None
    except Exception as e:
        warnings.warn(f"修正元数据失败: {e}")
        return False
