import os
import time
import shutil
import tempfile
import sqlite3
import pandas as pd
import streamlit as st
from pathlib import Path
import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TIT2, TPE1, TALB

st.set_page_config(page_title="NCM Metadata Editor", layout="wide")

st.title("网易云音乐元数据管理")

output_dir_str = os.environ.get("NCM_CRACK_OUTPUT_DIR", "/home/godke/Music/MusicDB")
output_dir = st.sidebar.text_input("输出目录 (Output Directory)", value=output_dir_str)

if not output_dir or not Path(output_dir).exists():
    st.warning("请输入有效的输出目录，或者从命令行启动时提供参数。")
    st.stop()

db_path = Path(output_dir) / "ncm_index.db"
if not db_path.exists():
    st.error(f"未在 {output_dir} 找到 ncm_index.db")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📦 批量任务")
if st.sidebar.button("一键抓取并嵌入双语歌词"):
    with st.spinner("正在初始化批量任务..."):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("SELECT * FROM songs WHERE music_id IS NOT NULL AND has_lyric = 0")
            tasks = cursor.fetchall()
        except sqlite3.OperationalError:
            st.sidebar.error("数据库正在迁移，请重启应用或等待加载完成。")
            conn.close()
            tasks = []

        if not tasks:
            if conn:
                st.sidebar.info("当前没有需要拉取歌词的曲目。")
                conn.close()
        else:
            import random
            from ncm_crack.api.netease import NeteaseClient
            from ncm_crack.core.models import NcmInfo
            
            client = NeteaseClient()
            progress_bar = st.sidebar.progress(0)
            status_text = st.sidebar.empty()
            
            success_count = 0
            skip_count = 0
            fail_count = 0

            for idx, row in enumerate(tasks):
                row_dict = dict(row)
                db_id = row_dict["id"]
                music_id = row_dict["music_id"]
                output_path_rel = row_dict["output_path"]
                
                abs_path = Path(output_dir) / output_path_rel
                lrc_path = abs_path.with_suffix(".lrc")
                
                status_text.text(f"处理中 ({idx+1}/{len(tasks)}): {abs_path.name}")
                
                try:
                    time.sleep(random.uniform(1.0, 3.0))
                    lyric = client.fetch_bilingual_lyric(int(music_id))
                    
                    if not lyric:
                        conn.execute("UPDATE songs SET has_lyric = 1 WHERE id = ?", (db_id,))
                        skip_count += 1
                    else:
                        with open(lrc_path, "w", encoding="utf-8") as f:
                            f.write(lyric)
                        
                        info = NcmInfo.from_db_row(row_dict)
                        info.lyric = lyric
                        
                        if not abs_path.exists():
                            raise FileNotFoundError(f"文件丢失: {abs_path}")
                            
                        # Use inline update logic to avoid relying on update_audio_file which is defined later
                        from ncm_crack.metadata.writer import set_audio_metadata
                        with tempfile.TemporaryDirectory() as temp_dir:
                            temp_file = Path(temp_dir) / abs_path.name
                            shutil.copy(abs_path, temp_file)
                            set_audio_metadata(temp_file, info, download_cover=False)
                            if abs_path.exists():
                                abs_path.unlink()
                            shutil.copy(temp_file, abs_path)
                        
                        conn.execute("UPDATE songs SET has_lyric = 1 WHERE id = ?", (db_id,))
                        success_count += 1
                        
                    conn.commit()
                except Exception as e:
                    st.sidebar.error(f"处理 {abs_path.name} 失败: {e}")
                    fail_count += 1
                    time.sleep(5)
                    
                progress_bar.progress((idx + 1) / len(tasks))
                
            status_text.text(f"完成! 成功:{success_count}, 纯音乐/跳过:{skip_count}, 失败:{fail_count}")
            conn.close()

@st.cache_data(ttl=5)
def load_data():
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM songs", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

df = load_data()

st.subheader("已转换的音乐库")
event = st.dataframe(
    df, 
    use_container_width=True, 
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun"
)

selected_index = 0
if event and hasattr(event, "selection") and event.selection.rows:
    selected_index = event.selection.rows[0]

st.subheader("编辑元数据")

# 选择要编辑的文件
options = df["output_path"].tolist() if not df.empty else []
selected_path = st.selectbox(
    "选择要编辑的曲目 (按照相对路径)", 
    options=options,
    index=selected_index if selected_index < len(options) else 0
)

def update_audio_file(file_path: Path, info):
    """到 /tmp 下修改再拷贝回目标盘，避免在目标盘上频繁做临时文件的读写`"""
    if not file_path.exists():
        raise FileNotFoundError(f"找不到文件: {file_path}")
        
    from ncm_crack.metadata.writer import set_audio_metadata
        
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir) / file_path.name
        shutil.copy(file_path, temp_file)
        
        # 使用标准的 set_audio_metadata 进行原子级重写
        set_audio_metadata(temp_file, info, download_cover=False)
        
        # 复制回目标盘
        if file_path.exists():
            file_path.unlink()
        shutil.copy(temp_file, file_path)

if selected_path:
    row = df[df["output_path"] == selected_path].iloc[0]
    
    # Initialize session state for the selected file
    if "current_path" not in st.session_state or st.session_state.current_path != selected_path:
        from ncm_crack.core.models import NcmInfo
        info = NcmInfo.from_db_row(row.to_dict())
        st.session_state.current_path = selected_path
        st.session_state.music_id = str(info.music_id or "")
        st.session_state.title = info.music_name or ""
        
        # Clean artist format
        artist_val = info.artist
        if isinstance(artist_val, list):
            st.session_state.artist = "/".join([a[0] if isinstance(a, list) and a else str(a) for a in artist_val])
        else:
            st.session_state.artist = str(artist_val) if artist_val else ""
            
        st.session_state.album = info.album or ""
        st.session_state.alias = ", ".join(info.alias)
        st.session_state.trans_names = ", ".join(info.trans_names)
        st.session_state.year = str(info.publish_time or "")

    # Layout for API fetching
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 根据当前 MusicId 联网刮削 (网易云)"):
            if st.session_state.music_id:
                from ncm_crack.api.netease import NeteaseClient
                with st.spinner("正在请求网易云接口..."):
                    client = NeteaseClient()
                    detail = client.fetch_song_detail(int(st.session_state.music_id))
                    if detail:
                        st.session_state.fetched_detail_json = detail
                        st.session_state.title = detail.get("musicName", "")
                        st.session_state.artist = "/".join(detail.get("artist", []))
                        st.session_state.album = detail.get("album", "")
                        st.session_state.alias = ", ".join(detail.get("alias", []))
                        st.session_state.trans_names = ", ".join(detail.get("transNames", []))
                        st.session_state.year = str(detail.get("publishTime") or "")
                        st.success("抓取成功！已自动填入下方表单，请确认后点击保存。")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("未能获取到歌曲信息")
            else:
                st.warning("当前没有 MusicId，请先尝试搜索。")

    with col2:
        search_kw = st.text_input("关键词搜索 (针对无 Key 音频)", value=st.session_state.title)
        if st.button("🔍 搜索并绑定最匹配项"):
            if search_kw:
                from ncm_crack.api.netease import NeteaseClient
                with st.spinner("搜索中..."):
                    client = NeteaseClient()
                    results = client.search_song(search_kw)
                    if results:
                        detail = results[0] # Bind the first match
                        st.session_state.fetched_detail_json = detail
                        st.session_state.music_id = str(detail.get("musicId", ""))
                        st.session_state.title = detail.get("musicName", "")
                        st.session_state.artist = "/".join(detail.get("artist", []))
                        st.session_state.album = detail.get("album", "")
                        st.session_state.alias = ", ".join(detail.get("alias", []))
                        st.success(f"已绑定最佳匹配: {st.session_state.title} - {st.session_state.artist}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("搜索无结果")

    abs_path = Path(output_dir) / selected_path
    lrc_path = abs_path.with_suffix('.lrc')
    
    if "fetched_detail_json" not in st.session_state or st.session_state.get("detail_path") != selected_path:
        st.session_state.fetched_detail_json = {}
        st.session_state.detail_path = selected_path

    st.markdown("### 元数据编辑")
    
    meta_col1, meta_col2 = st.columns([2, 1])
    
    with meta_col2:
        st.markdown("**原始 API 响应数据**")
        if st.session_state.fetched_detail_json:
            st.json(st.session_state.fetched_detail_json.get("raw_data", st.session_state.fetched_detail_json), expanded=False)
        else:
            st.info("暂无数据，请点击上方的“刮削”或“搜索”。")
            
    with meta_col1:
        with st.form("edit_form"):
            st.text_input("MusicId (网易云ID)", key="music_id")
            st.text_input("标题 (Title)", key="title")
            st.text_input("艺术家 (Artist)", key="artist")
            st.text_input("专辑 (Album)", key="album")
            st.text_input("别名 (Alias, 逗号分隔)", key="alias")
            st.text_input("翻译名 (Trans Names, 逗号分隔)", key="trans_names")
            st.text_input("发行年份 (Year)", key="year")
            
            submitted = st.form_submit_button("保存修改并写入音频文件")
        
        if submitted:
            from ncm_crack.core.models import NcmInfo
            import json
            
            info = NcmInfo.from_db_row(row.to_dict())
            info.music_id = int(st.session_state.music_id) if st.session_state.music_id.isdigit() else None
            info.music_name = st.session_state.title
            info.artist = st.session_state.artist
            info.album = st.session_state.album
            info.alias = [a.strip() for a in st.session_state.alias.split(",")] if st.session_state.alias else []
            info.trans_names = [a.strip() for a in st.session_state.trans_names.split(",")] if st.session_state.trans_names else []
            info.publish_time = int(st.session_state.year) if st.session_state.year.isdigit() else None
            
            try:
                # 1. 更新物理文件
                update_audio_file(abs_path, info)
                
                # 2. 更新数据库
                artist_str = info.artist
                alias_str = json.dumps(info.alias, ensure_ascii=False) if info.alias else ""
                trans_str = json.dumps(info.trans_names, ensure_ascii=False) if info.trans_names else ""
                
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "UPDATE songs SET music_id = ?, title = ?, artist = ?, album = ?, alias = ?, trans_names = ?, publish_time = ? WHERE output_path = ?",
                    (info.music_id, info.music_name, artist_str, info.album, alias_str, trans_str, info.publish_time, selected_path)
                )
                conn.commit()
                conn.close()
                
                st.success("元数据更新成功！")
                import time
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"更新失败: {e}")

    st.markdown("### 歌词管理")
    
    local_lyric = ""
    if lrc_path.exists():
        with open(lrc_path, "r", encoding="utf-8") as f:
            local_lyric = f.read()
            
    if "fetched_lyric_edit" not in st.session_state or st.session_state.get("lyric_path") != selected_path:
        st.session_state.fetched_lyric_edit = ""
        st.session_state.lyric_path = selected_path

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("🌐 尝试拉取网易云双语歌词"):
            if st.session_state.music_id:
                from ncm_crack.api.netease import NeteaseClient
                with st.spinner("获取双语歌词中..."):
                    client = NeteaseClient()
                    lyric = client.fetch_bilingual_lyric(int(st.session_state.music_id))
                    if lyric:
                        st.session_state.fetched_lyric_edit = lyric
                        st.rerun()
                    else:
                        st.warning("该歌曲暂无歌词。")
            else:
                st.error("缺少 MusicId，请先刮削或搜索绑定。")

    with btn_col2:
        if st.button("💾 覆盖保存为本地 .lrc 文件"):
            if st.session_state.fetched_lyric_edit:
                try:
                    with open(lrc_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state.fetched_lyric_edit)
                    st.success(f"歌词已成功覆盖保存至 {lrc_path.name}")
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"写入歌词失败: {e}")
            else:
                st.warning("拉取文本框为空，无法保存。")

    lyric_col1, lyric_col2 = st.columns(2)
    with lyric_col1:
        st.text_area("本地已存歌词 (.lrc)", value=local_lyric, height=300, disabled=True)
    with lyric_col2:
        st.text_area("拉取的双语歌词 (可编辑)", height=300, key="fetched_lyric_edit")
