import os
import sys
import shutil
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

import chardet


def detect_encoding(file_path: str, sample_size: int = 100000) -> Tuple[str, float]:
    """
    检测文件编码

    Args:
        file_path: 文件路径
        sample_size: 用于检测的样本字节数

    Returns:
        (编码名称, 置信度)
    """
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)
    result = chardet.detect(raw_data)
    return result['encoding'], result['confidence']


def convert_file(
    file_path: str,
    target_encoding: str = 'utf-8',
    backup: bool = True,
    min_confidence: float = 0.5
) -> Tuple[bool, str, float]:
    """
    转换单个文件编码为目标编码

    Args:
        file_path: 文件路径
        target_encoding: 目标编码
        backup: 是否创建备份文件
        min_confidence: 最小置信度，低于此值则跳过

    Returns:
        (是否成功, 检测到的编码, 置信度)
    """
    source_encoding, confidence = detect_encoding(file_path)

    if source_encoding is None:
        return False, 'unknown', 0.0

    if confidence < min_confidence:
        return False, source_encoding, confidence

    if source_encoding.lower() == target_encoding.lower():
        return True, source_encoding, confidence

    if backup:
        backup_path = file_path + '.bak'
        shutil.copy2(file_path, backup_path)

    try:
        with open(file_path, 'rb') as f:
            content = f.read()

        text = content.decode(source_encoding, errors='replace')

        with open(file_path, 'w', encoding=target_encoding, newline='') as f:
            f.write(text)

        return True, source_encoding, confidence
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        return False, source_encoding, confidence


def find_files(
    directory: str,
    extensions: Optional[List[str]] = None,
    recursive: bool = True
) -> List[str]:
    """
    查找目录下的文件

    Args:
        directory: 目录路径
        extensions: 文件扩展名列表，如 ['.txt', '.csv']
        recursive: 是否递归子目录

    Returns:
        文件路径列表
    """
    file_list = []
    path = Path(directory)

    if not path.exists() or not path.is_dir():
        return file_list

    if recursive:
        iterator = path.rglob('*')
    else:
        iterator = path.glob('*')

    for file_path in iterator:
        if file_path.is_file():
            if extensions is None or len(extensions) == 0:
                file_list.append(str(file_path))
            else:
                if file_path.suffix.lower() in [ext.lower() if ext.startswith('.') else '.' + ext.lower() for ext in extensions]:
                    file_list.append(str(file_path))

    return file_list


def batch_convert(
    directory: str,
    target_encoding: str = 'utf-8',
    extensions: Optional[List[str]] = None,
    recursive: bool = True,
    backup: bool = True,
    min_confidence: float = 0.5
) -> dict:
    """
    批量转换目录下的文件编码

    Args:
        directory: 目录路径
        target_encoding: 目标编码
        extensions: 文件扩展名列表
        recursive: 是否递归子目录
        backup: 是否创建备份
        min_confidence: 最小置信度

    Returns:
        转换结果统计
    """
    files = find_files(directory, extensions, recursive)
    results = {
        'total': len(files),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }

    for file_path in files:
        success, source_encoding, confidence = convert_file(
            file_path, target_encoding, backup, min_confidence
        )

        if success and source_encoding.lower() != target_encoding.lower():
            results['success'] += 1
            status = 'converted'
        elif success and source_encoding.lower() == target_encoding.lower():
            results['skipped'] += 1
            status = 'already_utf8'
        else:
            results['failed'] += 1
            status = 'failed'

        results['details'].append({
            'file': file_path,
            'source_encoding': source_encoding,
            'confidence': confidence,
            'status': status
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description='文件编码批量转换工具 - 自动检测并转换为 UTF-8'
    )
    parser.add_argument(
        'path',
        help='文件或目录路径'
    )
    parser.add_argument(
        '-t', '--target',
        default='utf-8',
        help='目标编码（默认：utf-8）'
    )
    parser.add_argument(
        '-e', '--extensions',
        nargs='*',
        help='指定文件扩展名，如 .txt .csv（默认为所有文件）'
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='不递归子目录'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='不创建备份文件'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.5,
        help='最小检测置信度（默认：0.5）'
    )
    parser.add_argument(
        '--detect-only',
        action='store_true',
        help='仅检测编码，不进行转换'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='显示详细输出'
    )

    args = parser.parse_args()

    path = args.path
    target_encoding = args.target
    extensions = args.extensions
    recursive = not args.no_recursive
    backup = not args.no_backup
    min_confidence = args.min_confidence
    detect_only = args.detect_only
    verbose = args.verbose

    if os.path.isfile(path):
        if detect_only:
            encoding, confidence = detect_encoding(path)
            print(f'文件: {path}')
            print(f'检测编码: {encoding} (置信度: {confidence:.2f})')
        else:
            success, source_encoding, confidence = convert_file(
                path, target_encoding, backup, min_confidence
            )
            print(f'文件: {path}')
            print(f'检测编码: {source_encoding} (置信度: {confidence:.2f})')
            if success:
                if source_encoding.lower() == target_encoding.lower():
                    print(f'状态: 已经是 {target_encoding} 编码')
                else:
                    print(f'状态: 转换成功 {source_encoding} → {target_encoding}')
            else:
                print('状态: 转换失败')
    elif os.path.isdir(path):
        if detect_only:
            files = find_files(path, extensions, recursive)
            print(f'找到 {len(files)} 个文件\n')
            for file_path in files:
                encoding, confidence = detect_encoding(file_path)
                print(f'{file_path}: {encoding} ({confidence:.2f})')
        else:
            results = batch_convert(
                path, target_encoding, extensions, recursive, backup, min_confidence
            )
            print(f'总计: {results["total"]} 个文件')
            print(f'转换成功: {results["success"]} 个')
            print(f'已是 {target_encoding}: {results["skipped"]} 个')
            print(f'转换失败: {results["failed"]} 个')

            if verbose:
                print('\n详细信息:')
                for detail in results['details']:
                    status_map = {
                        'converted': '已转换',
                        'already_utf8': '已为UTF-8',
                        'failed': '失败'
                    }
                    print(
                        f'  [{status_map.get(detail["status"], detail["status"])}] '
                        f'{detail["file"]} '
                        f'({detail["source_encoding"]}, 置信度: {detail["confidence"]:.2f})'
                    )
    else:
        print(f'错误: 路径不存在 - {path}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
