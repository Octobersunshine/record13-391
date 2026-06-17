import os
import sys
import shutil
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

import chardet

ENCODING_FAMILY = {
    'gb18030': ['gb18030', 'gbk', 'gb2312'],
    'gbk': ['gbk', 'gb18030', 'gb2312'],
    'gb2312': ['gb2312', 'gbk', 'gb18030'],
    'big5': ['big5', 'big5hkscs'],
    'euc_kr': ['euc_kr', 'cp949'],
    'euc_jp': ['euc_jp', 'shift_jis', 'cp932'],
    'shift_jis': ['shift_jis', 'cp932', 'euc_jp'],
}


def detect_encoding(file_path: str, sample_size: int = 100000) -> Tuple[str, float]:
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)
    result = chardet.detect(raw_data)
    return result['encoding'], result['confidence']


def _try_decode(content: bytes, encoding: str) -> bool:
    try:
        content.decode(encoding, errors='strict')
        return True
    except (UnicodeDecodeError, LookupError):
        return False


def _resolve_encoding(file_path: str, content: bytes, detected_encoding: str, confidence: float, min_confidence: float) -> Tuple[str, float]:
    if confidence >= min_confidence:
        return detected_encoding, confidence

    key = detected_encoding.lower().replace('-', '_') if detected_encoding else ''
    family = ENCODING_FAMILY.get(key, [])

    for candidate in family:
        if _try_decode(content, candidate):
            return candidate, confidence

    return detected_encoding, confidence


def convert_file(
    file_path: str,
    target_encoding: str = 'utf-8',
    backup: bool = True,
    min_confidence: float = 0.5,
    source_encoding: Optional[str] = None
) -> Tuple[bool, str, float]:
    if source_encoding is not None:
        resolved_encoding = source_encoding
        detected_confidence = 1.0
    else:
        detected_encoding, detected_confidence = detect_encoding(file_path)
        if detected_encoding is None:
            return False, 'unknown', 0.0

        with open(file_path, 'rb') as f:
            content = f.read()

        resolved_encoding, detected_confidence = _resolve_encoding(
            file_path, content, detected_encoding, detected_confidence, min_confidence
        )

    if resolved_encoding.lower().replace('-', '_') == target_encoding.lower().replace('-', '_'):
        return True, resolved_encoding, detected_confidence

    if backup:
        backup_path = file_path + '.bak'
        shutil.copy2(file_path, backup_path)

    try:
        with open(file_path, 'rb') as f:
            content = f.read()

        text = content.decode(resolved_encoding, errors='replace')

        with open(file_path, 'w', encoding=target_encoding, newline='') as f:
            f.write(text)

        return True, resolved_encoding, detected_confidence
    except (UnicodeDecodeError, UnicodeEncodeError, LookupError) as e:
        return False, resolved_encoding, detected_confidence


def find_files(
    directory: str,
    extensions: Optional[List[str]] = None,
    recursive: bool = True
) -> List[str]:
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
    min_confidence: float = 0.5,
    source_encoding: Optional[str] = None
) -> dict:
    files = find_files(directory, extensions, recursive)
    results = {
        'total': len(files),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }

    for file_path in files:
        success, src_enc, confidence = convert_file(
            file_path, target_encoding, backup, min_confidence, source_encoding
        )

        if success and src_enc.lower().replace('-', '_') != target_encoding.lower().replace('-', '_'):
            results['success'] += 1
            status = 'converted'
        elif success and src_enc.lower().replace('-', '_') == target_encoding.lower().replace('-', '_'):
            results['skipped'] += 1
            status = 'already_utf8'
        else:
            results['failed'] += 1
            status = 'failed'

        results['details'].append({
            'file': file_path,
            'source_encoding': src_enc,
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
        '-s', '--source-encoding',
        default=None,
        help='手动指定源编码，跳过自动检测（如 gbk、big5）'
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
    source_encoding = args.source_encoding
    extensions = args.extensions
    recursive = not args.no_recursive
    backup = not args.no_backup
    min_confidence = args.min_confidence
    detect_only = args.detect_only
    verbose = args.verbose

    if os.path.isfile(path):
        if detect_only:
            if source_encoding:
                encoding = source_encoding
                confidence = 1.0
            else:
                encoding, confidence = detect_encoding(path)
            print(f'文件: {path}')
            print(f'编码: {encoding} (置信度: {confidence:.2f})')
        else:
            success, src_enc, confidence = convert_file(
                path, target_encoding, backup, min_confidence, source_encoding
            )
            print(f'文件: {path}')
            encoding_label = source_encoding if source_encoding else src_enc
            print(f'编码: {encoding_label} (置信度: {confidence:.2f})')
            if success:
                if src_enc.lower().replace('-', '_') == target_encoding.lower().replace('-', '_'):
                    print(f'状态: 已经是 {target_encoding} 编码')
                else:
                    print(f'状态: 转换成功 {src_enc} → {target_encoding}')
            else:
                print('状态: 转换失败')
    elif os.path.isdir(path):
        if detect_only:
            files = find_files(path, extensions, recursive)
            print(f'找到 {len(files)} 个文件\n')
            for file_path in files:
                if source_encoding:
                    enc = source_encoding
                    conf = 1.0
                else:
                    enc, conf = detect_encoding(file_path)
                print(f'{file_path}: {enc} ({conf:.2f})')
        else:
            results = batch_convert(
                path, target_encoding, extensions, recursive, backup,
                min_confidence, source_encoding
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
