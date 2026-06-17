import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from encoding_converter import (
    detect_encoding,
    convert_file,
    find_files,
    batch_convert
)

CHINESE_LONG_TEXT = """
这是一段用于测试编码检测的中文长文本。为了确保编码检测的准确性，
我们需要提供足够多的中文内容，这样chardet才能给出较高的置信度。
GBK、GB2312、GB18030都是中文编码，其中GB18030是最新的标准，
向下兼容GBK和GB2312。在进行编码检测时，这些编码经常会被互相识别。
为了测试文件编码转换工具的正确性，我们需要准备各种不同编码的文件，
包括UTF-8、GBK、GB2312等常见的中文编码格式。
编码转换是软件开发中经常遇到的问题，特别是在处理中文环境下，
很多历史文件可能使用的是GBK编码，需要统一转换为UTF-8编码。
这个工具的目的就是帮助用户批量完成这样的转换工作，
自动检测文件编码并将其转换为目标编码格式。
"""


class TestEncodingConverter(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix='enc_test_')
        self.sub_dir = os.path.join(self.test_dir, 'subdir')
        os.makedirs(self.sub_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_file(self, path, content, encoding):
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)

    def test_detect_encoding_utf8(self):
        file_path = os.path.join(self.test_dir, 'utf8.txt')
        self._create_file(file_path, '你好世界 Hello World', 'utf-8')
        encoding, confidence = detect_encoding(file_path)
        self.assertIn(encoding.lower(), ['utf-8', 'ascii'])
        self.assertGreater(confidence, 0.5)

    def test_detect_encoding_gbk(self):
        file_path = os.path.join(self.test_dir, 'gbk.txt')
        self._create_file(file_path, CHINESE_LONG_TEXT, 'gbk')
        encoding, confidence = detect_encoding(file_path)
        self.assertIn(encoding.lower(), ['gb2312', 'gbk', 'cp936', 'gb18030'])
        self.assertGreater(confidence, 0.5)

    def test_convert_file_gbk_to_utf8(self):
        file_path = os.path.join(self.test_dir, 'convert_gbk.txt')
        original_content = CHINESE_LONG_TEXT
        self._create_file(file_path, original_content, 'gbk')

        success, source_encoding, confidence = convert_file(
            file_path, 'utf-8', backup=True
        )

        self.assertTrue(success)

        with open(file_path, 'r', encoding='utf-8') as f:
            converted_content = f.read()
        self.assertEqual(converted_content, original_content)

        backup_path = file_path + '.bak'
        self.assertTrue(os.path.exists(backup_path))

    def test_convert_file_already_utf8(self):
        file_path = os.path.join(self.test_dir, 'already_utf8.txt')
        content = 'UTF-8 content 中文'
        self._create_file(file_path, content, 'utf-8')

        success, source_encoding, confidence = convert_file(
            file_path, 'utf-8', backup=False
        )

        self.assertTrue(success)

        with open(file_path, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), content)

    def test_convert_file_no_backup(self):
        file_path = os.path.join(self.test_dir, 'no_backup.txt')
        self._create_file(file_path, CHINESE_LONG_TEXT, 'gbk')

        success, _, _ = convert_file(file_path, 'utf-8', backup=False)
        self.assertTrue(success)
        self.assertFalse(os.path.exists(file_path + '.bak'))

    def test_find_files_recursive(self):
        self._create_file(os.path.join(self.test_dir, 'a.txt'), 'a', 'utf-8')
        self._create_file(os.path.join(self.test_dir, 'b.csv'), 'b', 'utf-8')
        self._create_file(os.path.join(self.sub_dir, 'c.txt'), 'c', 'utf-8')
        self._create_file(os.path.join(self.sub_dir, 'd.md'), 'd', 'utf-8')

        all_files = find_files(self.test_dir, recursive=True)
        self.assertEqual(len(all_files), 4)

        txt_files = find_files(self.test_dir, extensions=['.txt'], recursive=True)
        self.assertEqual(len(txt_files), 2)

    def test_find_files_non_recursive(self):
        self._create_file(os.path.join(self.test_dir, 'a.txt'), 'a', 'utf-8')
        self._create_file(os.path.join(self.sub_dir, 'b.txt'), 'b', 'utf-8')

        files = find_files(self.test_dir, recursive=False)
        self.assertEqual(len(files), 1)

    def test_batch_convert(self):
        self._create_file(os.path.join(self.test_dir, 'gbk1.txt'), CHINESE_LONG_TEXT, 'gbk')
        self._create_file(os.path.join(self.test_dir, 'gbk2.txt'), CHINESE_LONG_TEXT, 'gbk')
        self._create_file(os.path.join(self.test_dir, 'utf8.txt'), 'utf8内容', 'utf-8')
        self._create_file(os.path.join(self.sub_dir, 'gbk_sub.txt'), CHINESE_LONG_TEXT, 'gbk')

        results = batch_convert(
            self.test_dir,
            target_encoding='utf-8',
            extensions=['.txt'],
            recursive=True,
            backup=True
        )

        self.assertEqual(results['total'], 4)
        self.assertEqual(results['success'], 3)
        self.assertEqual(results['skipped'], 1)
        self.assertEqual(results['failed'], 0)

        for detail in results['details']:
            if detail['status'] == 'converted':
                self.assertTrue(os.path.exists(detail['file'] + '.bak'))

    def test_batch_convert_no_backup(self):
        self._create_file(os.path.join(self.test_dir, 'test.txt'), CHINESE_LONG_TEXT, 'gbk')

        results = batch_convert(
            self.test_dir,
            target_encoding='utf-8',
            backup=False
        )

        self.assertEqual(results['success'], 1)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, 'test.txt.bak')))

    def test_already_utf8_skipped(self):
        file_path = os.path.join(self.test_dir, 'utf8_file.txt')
        content = '这是UTF-8编码的文件内容'
        self._create_file(file_path, content, 'utf-8')

        success, source_encoding, confidence = convert_file(
            file_path, 'utf-8', backup=False
        )

        self.assertTrue(success)
        self.assertIn(source_encoding.lower(), ['utf-8', 'ascii'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
