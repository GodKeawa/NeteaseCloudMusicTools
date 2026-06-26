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

MAX_CPU_PERCENT = 100

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

    def _get_relative_output_path(self, input_file: Path) -> Path:
        rel_path = input_file.relative_to(self.input_dir)
        parts = list(rel_path.parts)
        if "VipSongsDownload" in parts:
            parts.remove("VipSongsDownload")
            rel_path = Path(*parts)
        return self.output_dir / rel_path

    def _is_already_converted(self, output_path: Path, base_name: str, original_filename: str) -> bool:
        if self.overwrite:
            return False
        if original_filename in self.overwrite_files:
            return False

        parent_dir = output_path.parent
        return (
            (parent_dir / f"{base_name}.mp3").exists()
            or (parent_dir / f"{base_name}.flac").exists()
        )

    def _convert_single_file(self, ncm_path: Path, output_path: Path, max_retries: int = 3) -> Optional[bool]:
        base_name = ncm_path.stem
        if self._is_already_converted(output_path, base_name, ncm_path.name):
            return None

        output_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(max_retries):
            try:
                while psutil.cpu_percent(1) > MAX_CPU_PERCENT:
                    time.sleep(0.5)

                parser = NcmParser(ncm_path)
                ncm_info = parser.parse()

                temp_output = output_path.parent / f"{base_name}.mp3"
                decryptor = NcmDecryptor(ncm_path, ncm_info)
                final_path = decryptor.decrypt(temp_output)

                set_audio_metadata(final_path, ncm_info, download_cover=self.download_cover)

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
            should_overwrite = self.overwrite or (src_path.name in self.overwrite_files)
            if dst_path.exists() and not should_overwrite:
                return None

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            is_audio = dst_path.suffix.lower() in [".mp3", ".flac"]

            shutil.copy2(src_path, dst_path)

            if is_audio:
                fix_audio_metadata(dst_path)

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
