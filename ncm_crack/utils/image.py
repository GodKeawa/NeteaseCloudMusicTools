import time
import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
)

def download_image(url: str, save_path: str, max_retries: int = 3) -> bool:
    """下载图片并保存"""
    headers = {"User-Agent": DEFAULT_USER_AGENT}

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                f.write(response.content)
            return True

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"图片下载失败: {e}")
                return False

    return False
