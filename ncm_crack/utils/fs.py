import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from typing import Optional, Tuple, Set

import psutil
from tqdm import tqdm

from ..core.parser import NcmParser
from ..core.decryptor import NcmDecryptor
from ..metadata.writer import set_audio_metadata
from ..metadata.fixer import fix_audio_metadata
from .db import DatabaseManager

MAX_CPU_PERCENT = 100

import threading

class BatchConverter:
    """批量转换 NCM 文件，支持特定目录 (VipSongsDownload) 及文件复制"""

    DEFAULT_BLACKLIST = {
        "__pycache__", ".git", ".svn", ".hg", "node_modules", ".idea", ".vscode", "Output"
    }

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        folder_blacklist: Optional[set] = None,
        overwrite: bool = False,
        overwrite_files: Optional[Set[str]] = None,
        download_cover: bool = True
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.folder_blacklist = self.DEFAULT_BLACKLIST.copy()
        if folder_blacklist:
            self.folder_blacklist.update(folder_blacklist)

        self.overwrite = overwrite
        self.overwrite_files = overwrite_files or set()
        self.download_cover = download_cover
        
        self.db = DatabaseManager(self.output_dir / "ncm_index.db")
        self.fs_lock = threading.Lock()

    def _get_relative_output_path(self, input_file: Path) -> Path:
        rel_path = input_file.relative_to(self.input_dir)
        parts = list(rel_path.parts)
        if "VipSongsDownload" in parts:
            parts.remove("VipSongsDownload")
            rel_path = Path(*parts)
        return self.output_dir / rel_path

    def _is_already_converted(self, ncm_path: Path, output_path: Path, base_name: str) -> bool:
        should_overwrite = self.overwrite or (ncm_path.name in self.overwrite_files)
        if should_overwrite:
            return False

        rel_path_str = str(ncm_path.relative_to(self.input_dir))

        if self.db.is_converted(rel_path_str):
            return True

        # 如果数据库中没有记录，即使磁盘上有文件，我们也返回 False 强制重新解析。
        # 这样可以保证数据库的完整性，并且会触发元数据的清理和回写。
        return False

    def _convert_single_file(self, ncm_path: Path, output_path: Path, max_retries: int = 3) -> Optional[bool]:
        base_name = ncm_path.stem
        if self._is_already_converted(ncm_path, output_path, base_name):
            return None

        with self.fs_lock:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(max_retries):
            try:
                import tempfile
                import shutil
                while psutil.cpu_percent(1) > MAX_CPU_PERCENT:
                    time.sleep(0.5)

                parser = NcmParser(ncm_path)
                ncm_info = parser.parse()

                # 为了避免在目标盘上频繁做临时文件的读写, 我们先在系统本地临时目录（/tmp）下完成一切操作，最后再一次性完整拷入目标盘
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_output = Path(temp_dir) / f"{base_name}.mp3"
                    decryptor = NcmDecryptor(ncm_path, ncm_info)
                    
                    # 在临时目录解密并重命名正确的后缀
                    final_temp_path = Path(decryptor.decrypt(temp_output))
                    
                    # 在临时目录应用元数据（包含下载封面、mutagen写入等）
                    set_audio_metadata(final_temp_path, ncm_info, download_cover=self.download_cover)
                    
                    # 全部操作完成后，将最终成品安全复制到目标盘
                    final_dest = output_path.parent / final_temp_path.name
                    with self.fs_lock:
                        if final_dest.exists():
                            final_dest.unlink()
                        shutil.copy(final_temp_path, final_dest)
                    
                    # 写入数据库记录
                    rel_ncm_path = str(ncm_path.relative_to(self.input_dir))
                    rel_out_path = str(final_dest.relative_to(self.output_dir))
                    self.db.add_record(rel_ncm_path, rel_out_path, ncm_info)

                return True

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    print(f"转换失败: {ncm_path} - {e}")
                    return False

        return False

    def _copy_single_file(self, src_path: Path, dst_path: Path) -> Optional[bool]:
        try:
            rel_src_path_str = str(src_path.relative_to(self.input_dir))
            
            should_overwrite = self.overwrite or (src_path.name in self.overwrite_files)
            
            is_audio = src_path.suffix.lower() in [".mp3", ".flac"]
            
            # 非音频文件（如 lrc, txt）直接跳过已存在的文件
            if not is_audio:
                if dst_path.exists() and not should_overwrite:
                    return None
            else:
                if dst_path.exists() and not should_overwrite:
                    if self.db.is_converted(rel_src_path_str):
                        return None
                        
                if self.db.is_converted(rel_src_path_str) and not should_overwrite:
                    return None

            if is_audio:
                from ..core.key_parser import parse_163_key_from_file
                from ..core.models import NcmInfo
                import mutagen
                import tempfile
                
                ncm_info = parse_163_key_from_file(src_path)
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_file = Path(temp_dir) / src_path.name
                    shutil.copy(src_path, temp_file)
                    
                    if ncm_info:
                        # 从原生文件提取到了 163 key，使用完整元数据写入
                        set_audio_metadata(temp_file, ncm_info, download_cover=self.download_cover)
                    else:
                        # 没有提取到 163 key，尝试从原生标签构建 ncm_info 以存入数据库
                        fix_audio_metadata(temp_file)
                        ncm_info = NcmInfo()
                        try:
                            audio = mutagen.File(str(temp_file))
                            if audio is not None:
                                if "TIT2" in audio or "title" in audio:
                                    ncm_info.music_name = str(audio.get("TIT2", audio.get("title", [None])[0]))
                                if "TPE1" in audio or "artist" in audio:
                                    ncm_info.artist = str(audio.get("TPE1", audio.get("artist", [None])[0]))
                                if "TALB" in audio or "album" in audio:
                                    ncm_info.album = str(audio.get("TALB", audio.get("album", [None])[0]))
                        except Exception:
                            pass
                        
                        # Fallback to filename if no tags
                        if not ncm_info.music_name:
                            ncm_info.music_name = src_path.stem

                    # 复制回目标盘
                    with self.fs_lock:
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        if dst_path.exists():
                            dst_path.unlink()
                        shutil.copy(temp_file, dst_path)
                        
                    rel_out_path = str(dst_path.relative_to(self.output_dir))
                    self.db.add_record(rel_src_path_str, rel_out_path, ncm_info)
            else:
                with self.fs_lock:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src_path, dst_path)

            return True

        except Exception as e:
            print(f"复制文件失败: {src_path} -> {dst_path}: {e}")
            return False

    def _is_blacklisted(self, path: Path) -> bool:
        for part in path.parts:
            if part in self.folder_blacklist:
                return True
        return False

    def _collect_all_files(self) -> Tuple[list, list]:
        ncm_files = []
        other_files = []

        for file_path in self.input_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.input_dir)
                if self._is_blacklisted(rel_path):
                    continue

                # 仅当位于 VipSongsDownload 下的 ncm 才转换，其他目录全部视为复制文件 (或忽略)
                is_in_vip = "VipSongsDownload" in file_path.parts
                
                if file_path.suffix.lower() == ".ncm":
                    if is_in_vip:
                        ncm_files.append(file_path)
                    else:
                        other_files.append(file_path)
                else:
                    other_files.append(file_path)

        return ncm_files, other_files

    def convert_all(self, max_workers: Optional[int] = None) -> dict:
        print("正在扫描文件...")
        ncm_files, other_files = self._collect_all_files()

        total_files = len(ncm_files) + len(other_files)
        stats = {
            "ncm_success": 0, "ncm_failed": 0, "ncm_skipped": 0,
            "copy_success": 0, "copy_failed": 0, "copy_skipped": 0,
            "updated_files": []
        }
        
        if total_files == 0:
            print(f"在 {self.input_dir} 中未找到任何文件")
            return stats

        print(f"找到 {len(ncm_files)} 个 NCM 文件，{len(other_files)} 个其他文件")
        print()

        if max_workers is None:
            cpu_count = os.cpu_count() or 1
            max_workers = max(1, int(cpu_count * 0.8))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            for ncm_file in ncm_files:
                output_path = self._get_relative_output_path(ncm_file)
                future = executor.submit(self._convert_single_file, ncm_file, output_path)
                futures.append(("ncm", future, ncm_file.name))

            for other_file in other_files:
                dst_path = self._get_relative_output_path(other_file)
                future = executor.submit(self._copy_single_file, other_file, dst_path)
                futures.append(("copy", future, other_file.name))

            with tqdm(total=len(futures), desc="处理进度", unit="文件") as pbar:
                for _, future, _ in futures:
                    future.add_done_callback(lambda _: pbar.update(1))
                wait([f for _, f, _ in futures])

            for file_type, future, filename in futures:
                result = future.result()
                if file_type == "ncm":
                    if result is True:
                        stats["ncm_success"] += 1
                        stats["updated_files"].append(filename)
                    elif result is False:
                        stats["ncm_failed"] += 1
                    else:
                        stats["ncm_skipped"] += 1
                else:
                    if result is True:
                        stats["copy_success"] += 1
                        stats["updated_files"].append(filename)
                    elif result is False:
                        stats["copy_failed"] += 1
                    else:
                        stats["copy_skipped"] += 1

        return stats
