import argparse
import os
from pathlib import Path
from typing import Set

from .utils.fs import BatchConverter

def main():
    """命令行主函数"""
    parser = argparse.ArgumentParser(
        description="NCM Cracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 默认路径
    default_input = Path("/home/godke/Data/Music")
    default_output = Path("/home/godke/Data/MusicDB")
    
    parser.add_argument(
        "-p",
        "--path",
        default=str(default_input),
        help=f"包含 NCM 文件的输入目录路径（默认: {default_input}）",
    )

    parser.add_argument(
        "-o",
        "--output",
        default=str(default_output),
        help=f"输出目录路径（默认: {default_output}）",
    )

    parser.add_argument(
        "-b",
        "--blacklist",
        nargs="*",
        help="要跳过的文件夹名称列表（空格分隔）。例如: -b temp cache backup",
    )

    parser.add_argument(
        "-f",
        "--overwrite",
        nargs="*",
        help="强制覆盖。如果不提供参数，则覆盖所有文件。如果提供文件名，则仅覆盖列表中的文件",
    )

    parser.add_argument(
        "--no-cover",
        action="store_true",
        help="不下载并嵌入封面图片（默认会下载封面）",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.path):
        print(f"错误: 路径不存在或不是目录: {args.path}")
        return

    print(f"输入目录: {args.path}")
    print(f"输出目录: {args.output}")

    custom_blacklist = set(args.blacklist) if args.blacklist else None
    
    # 处理强制覆盖逻辑
    overwrite_all = False
    overwrite_files: Set[str] = set()
    
    if args.overwrite is not None:
        if len(args.overwrite) == 0:
            overwrite_all = True
            print("覆写模式: 开启 (所有文件)")
        else:
            overwrite_files = set(args.overwrite)
            print(f"覆写模式: 开启 (指定文件: {', '.join(overwrite_files)})")
    else:
        print("覆写模式: 关闭")

    converter = BatchConverter(
        args.path, 
        args.output, 
        custom_blacklist, 
        overwrite=overwrite_all, 
        overwrite_files=overwrite_files,
        download_cover=not args.no_cover
    )

    print(f"黑名单文件夹: {', '.join(sorted(converter.folder_blacklist))}")
    print()

    stats = converter.convert_all()

    print(f"\n处理完成!")
    print(f"\nNCM 转换:")
    print(f"  成功: {stats['ncm_success']} 个文件")
    print(f"  失败: {stats['ncm_failed']} 个文件")
    print(f"  跳过: {stats['ncm_skipped']} 个文件")
    print(f"\n文件复制:")
    print(f"  成功: {stats['copy_success']} 个文件")
    print(f"  失败: {stats['copy_failed']} 个文件")
    print(f"  跳过: {stats['copy_skipped']} 个文件")


if __name__ == "__main__":
    main()
