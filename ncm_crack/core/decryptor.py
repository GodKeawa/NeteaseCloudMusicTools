import binascii
import struct
from pathlib import Path
from typing import Tuple

from Crypto.Util.strxor import strxor

from .crypto import CHUNK_SIZE, NCM_HEADER, create_decryption_mask
from .models import NcmInfo

def detect_audio_format(data: bytes) -> str:
    """通过文件头检测音频格式"""
    if len(data) >= 4 and data.startswith(b"fLaC"):
        return "flac"
    elif len(data) >= 3 and data.startswith(b"ID3"):
        return "mp3"
    elif len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    return "mp3"  # 默认

class NcmDecryptor:
    """NCM 文件解密器"""

    def __init__(self, input_path: str | Path, ncm_info: NcmInfo):
        self.input_path = Path(input_path)
        self.ncm_info = ncm_info

    def _skip_image_data(self, file):
        """跳过嵌入的图片数据"""
        file.read(4)  # CRC32
        file.seek(5, 1)  # 跳过5字节
        image_size = struct.unpack("<I", file.read(4))[0]
        file.seek(image_size, 1)  # 跳过图片数据

    def decrypt(self, output_path: str | Path) -> str:
        """解密 NCM 文件
        
        Args:
            output_path: 输出文件路径（可能会根据实际格式调整扩展名）
            
        Returns:
            最终输出文件的路径字符串
        """
        if not self.ncm_info.key_box:
            raise ValueError("NcmInfo 缺少 key_box，无法解密")

        with open(self.input_path, "rb") as f:
            # 验证文件头
            header = f.read(8)
            if binascii.b2a_hex(header) != NCM_HEADER:
                raise ValueError("不是有效的 NCM 文件")

            # 定位到图片数据之前 (跳过密钥和元数据块)
            f.seek(10, 1)  # 跳过开头的 10 字节? 其实前面的 header 已经读了
            # NCM 结构:
            # HEADER (8)
            # 2 bytes gap
            # key length (4)
            # key data (key length)
            # meta length (4)
            # meta data (meta length)
            
            # 为了可靠跳过，我们需要重新读取前面的长度
            f.seek(8) # 从 header 后面开始
            f.seek(2, 1)
            key_len = struct.unpack("<I", f.read(4))[0]
            f.seek(key_len, 1)
            
            meta_len = struct.unpack("<I", f.read(4))[0]
            f.seek(meta_len, 1)

            # 跳过图片数据
            self._skip_image_data(f)

            # 创建解密掩码
            full_mask = create_decryption_mask(self.ncm_info.key_box)

            # 解密音频数据
            output_path = Path(output_path)
            temp_path = output_path.with_suffix(".tmp")
            actual_format = self.ncm_info.format

            with open(temp_path, "wb") as out:
                first_chunk = True

                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    chunk_len = len(chunk)
                    decrypted = strxor(chunk, full_mask[:chunk_len])

                    if first_chunk:
                        actual_format = detect_audio_format(decrypted)
                        first_chunk = False

                    out.write(decrypted)

            # 重命名为正确的扩展名
            final_path = output_path.with_suffix(f".{actual_format}")
            if final_path.exists():
                final_path.unlink()
            temp_path.rename(final_path)

            return str(final_path)
