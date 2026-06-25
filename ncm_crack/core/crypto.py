import binascii
from Crypto.Cipher import AES

CORE_KEY = binascii.a2b_hex("687A4852416D736F356B496E62617857")
META_KEY = binascii.a2b_hex("2331346C6A6B5F215C5D2630553C2728")
NCM_HEADER = b"4354454e4644414d"
CHUNK_SIZE = 0x8000  # 32KB

def unpad(data: bytes) -> bytes:
    """移除 PKCS7 填充"""
    padding_len = data[-1] if isinstance(data[-1], int) else ord(data[-1])
    return data[:-padding_len]

def build_key_box(key_data: bytes) -> bytearray:
    """构建密钥盒"""
    key_box = bytearray(range(256))
    key_length = len(key_data)
    last_byte = 0
    key_offset = 0

    for i in range(256):
        swap = key_box[i]
        c = (swap + last_byte + key_data[key_offset]) & 0xFF
        key_offset = (key_offset + 1) % key_length
        key_box[i], key_box[c] = key_box[c], swap
        last_byte = c

    return key_box

def create_decryption_mask(key_box: bytearray) -> bytes:
    """创建解密掩码"""
    mask = bytearray(256)
    for i in range(256):
        j = (i + 1) & 0xFF
        mask[i] = key_box[
            (key_box[j] + key_box[(key_box[j] + j) & 0xFF]) & 0xFF
        ]
    return bytes(mask) * (CHUNK_SIZE // 256)
