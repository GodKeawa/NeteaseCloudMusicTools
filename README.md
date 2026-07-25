# Netease Cloud Music Tools

提供一系列从网易云音乐解密到元数据完善的自动化本地音乐库工具。

## NCM Cracker & Metadata Manager
将网易云音乐加密的 `.ncm` 文件转换为标准音频格式（MP3/FLAC），并提供一套基于 Streamlit 的现代化 Web UI，用于管理元数据、全自动刮削并无损内嵌双语歌词。

### 功能特性

- **模块化解密**：核心解密、元数据解析、文件系统操作分离。支持递归处理文件夹，完整保留目录结构。
- **自动格式识别**：根据文件头自动检测输出格式（MP3 或 FLAC）。
- **完整元数据写入**：自动提取加密文件中的元数据并无损嵌入。默认自动下载并嵌入专辑封面，支持关闭。
- **SQLite 索引与管理**：全自动构建本地音乐库的 SQLite 索引（`ncm_index.db`），包含详细的转换路径与原始网易云 `MusicId`。
- **现代化 Web UI**：通过 Streamlit 提供直观的表格管理页面，支持鼠标点选、实时修改元数据及直接写入物理音频文件。
- **智能网易云 API 刮削**：
  - **单曲精刮**：针对无 `MusicId` 的本地音频，支持关键字定向搜索并绑定正确的网易云 ID，自动补全流派、发行年份等原生 API 信息。
  - **双语歌词内嵌**：支持一键获取精确对齐的时间轴双语歌词。
  - **批量全自动处理**：侧边栏提供“批量任务”，支持一键为库中所有具备 ID 的歌曲拉取双语歌词。内置防封印（退避休眠）机制与智能跳过功能（如遇到纯音乐会自动放行）。
- **强制覆盖机制**：支持全局强制覆盖转换，或仅指定若干文件进行重新转换。
- **多线程处理**：利用多核 CPU 提升转换速度。

### 使用方法

推荐使用 `uv` 进行依赖管理与执行：

#### 1. 启动 Web UI (推荐)

启动基于 Streamlit 的图形化元数据管理界面：

```bash
uv run streamlit run ncm_crack/ui/app.py
```
> 您可以在界面内直接管理解析好的音频，一键刮削网易云信息并下载双语歌词。

#### 2. 命令行自动解密与转换

```bash
# 默认路径（/home/godke/Data/Music -> /home/godke/Data/MusicDB）
uv run python -m ncm_crack

# 指定输入与输出文件夹
uv run python -m ncm_crack -p ./MyMusic -o ./ConvertedMusic

# 启用全局覆写模式（重新处理所有已存在的文件）
uv run python -m ncm_crack -f

# 仅针对部分特定文件进行覆写（传入文件名列表）
uv run python -m ncm_crack -f 1.ncm 2.ncm

# 添加自定义黑名单
uv run python -m ncm_crack -b demo test

# 关闭封面下载功能
uv run python -m ncm_crack --no-cover
```

### 依赖说明

主要依赖库：
- `streamlit` & `pandas` - Web UI 构建与数据展示
- `pycryptodome` - AES 解密算法
- `mutagen` - 音频元数据无损处理（支持 MP3 的 `USLT`/`COMM` 与 FLAC 的 `LYRICS`/Vorbis Comment）
- `eyed3` - MP3 标签支持
- `requests` - 专辑封面与 API 请求
- `tqdm` - 命令行进度条显示
- `psutil` - CPU 使用率监控

安装依赖与运行：
```bash
uv sync
uv run python -m ncm_crack
```

## Local Music Tag Web (Complementary Tool)
Music Tag Web 的增强版，支持 `ncm_crack` 解析出的歌曲 Id 以及网易云的 163 Key。

> 对于网易云中本身不存在的曲目。可以搭配 `Music-tag-web` 从其他数据源抓取封面和标签。

### Link
- https://github.com/GodKeawa/music_tag_web.git