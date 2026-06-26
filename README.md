# Netease Cloud Music Tools

## NCM Cracker
将网易云音乐加密的 `.ncm` 文件转换为标准音频格式（MP3/FLAC），并保留元数据。采用模块化架构设计，支持递归处理文件夹，完整保留目录结构。

### 功能特性

- **模块化架构**：核心解密、元数据解析、文件系统操作分离，易于维护与扩展。
- **自动格式识别**：根据文件头自动检测输出格式（MP3 或 FLAC）。
- **完整元数据**：自动提取并写入歌曲名、艺术家、专辑、年份等信息。默认自动下载并嵌入专辑封面，您也可以选择关闭此功能交由第三方工具处理。
- **智能目录识别**：专门针对网易云下载目录 `VipSongsDownload` 进行解密处理，其他目录及非 NCM 文件则直接复制，完美保留层级。
- **强制覆盖机制**：支持全局强制覆盖转换，或仅指定若干文件进行重新转换。
- **多线程处理**：利用多核 CPU 提升转换速度。
- **黑名单机制**：跳过特定文件夹（如系统文件夹、缓存等）。

### 使用方法

推荐使用 `uv` 进行依赖管理与执行：

#### 基本用法

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

#### 参数说明

- `-p, --path`：输入目录路径（默认：`/home/godke/Data/Music`）
- `-o, --output`：输出目录路径（默认：`/home/godke/Data/MusicDB`）
- `-b, --blacklist`：要跳过的文件夹名称列表（空格分隔）
- `-f, --overwrite`：强制覆盖。如果不提供参数则覆盖所有文件，提供具体文件名则仅覆盖列表中的文件。
- `--no-cover`：不下载并嵌入封面图片（默认会下载并嵌入封面）。

### 依赖说明

主要依赖库：
- `pycryptodome` - AES 解密算法
- `mutagen` - 音频元数据处理（支持 MP3 和 FLAC）
- `eyed3` - MP3 标签支持
- `requests` - 专辑封面下载
- `tqdm` - 进度条显示
- `psutil` - CPU 使用率监控

安装依赖与运行：
```bash
uv sync
uv run python -m ncm_crack
```

## Local Music Tag Web
Music Tag Web的增强版，支持ncm_crack解析出的歌曲Id以及网易云的163 Key，提供定向解析。

### Link
- https://github.com/GodKeawa/music_tag_web.git 