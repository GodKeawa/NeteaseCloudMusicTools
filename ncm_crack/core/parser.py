import base64
import binascii
import json
import struct
from pathlib import Path
from typing import BinaryIO, Optional

from Crypto.Cipher import AES

from .crypto import CORE_KEY, META_KEY, NCM_HEADER, unpad, build_key_box
from .models import NcmInfo

class NcmParser:
    """NCM 文件解析器"""

    def __init__(self, input_path: str | Path):
        self.input_path = Path(input_path)

    def _read_key_data(self, file: BinaryIO) -> bytes:
        """读取并解密密钥数据"""
        file.seek(2, 1)  # 跳过2字节
        key_length = struct.unpack("<I", file.read(4))[0]

        # XOR 解密
        key_data = bytearray(file.read(key_length))
        for i in range(len(key_data)):
            key_data[i] ^= 0x64

        # AES 解密
        cipher = AES.new(CORE_KEY, AES.MODE_ECB)
        return unpad(cipher.decrypt(bytes(key_data)))[17:]

    def _read_metadata(self, file: BinaryIO) -> dict:
        """读取并解密元数据"""
        meta_length = struct.unpack("<I", file.read(4))[0]
        if meta_length == 0:
            return {}

        # XOR 解密
        meta_data = bytearray(file.read(meta_length))
        for i in range(len(meta_data)):
            meta_data[i] ^= 0x63

        # Base64 + AES 解密
        # 数据以 '163 key(Don\'t modify):' 开头，共22字节
        meta_data = base64.b64decode(bytes(meta_data)[22:])
        cipher = AES.new(META_KEY, AES.MODE_ECB)
        meta_json_str = unpad(cipher.decrypt(meta_data)).decode("utf-8")
        
        # 数据以 'music:' 开头，共6字节
        if meta_json_str.startswith("music:"):
            meta_json = meta_json_str[6:]
        else:
            meta_json = meta_json_str
            
        return json.loads(meta_json)

    def parse(self) -> NcmInfo:
        """解析 NCM 文件，提取信息"""
        with open(self.input_path, "rb") as f:
            # 验证文件头
            header = f.read(8)
            if binascii.b2a_hex(header) != NCM_HEADER:
                raise ValueError(f"不是有效的 NCM 文件: {self.input_path}")

            # 读取密钥
            key_data = self._read_key_data(f)
            key_box = build_key_box(key_data)
            
            # 读取元数据
            metadata_dict = self._read_metadata(f)
            
            # 返回包含了密钥的 NcmInfo 对象
            return NcmInfo.from_dict(metadata_dict, key_data=key_data, key_box=key_box)
