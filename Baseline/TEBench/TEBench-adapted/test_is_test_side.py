#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路线 1 的测试侧判据回归：18 条边界用例（对应 VERIFY.md §5.0）。

背景：`is_test_side` 原来写成 `'fuzz' in p`，会把库里的 fuzzing.h、fuzz_helpers.h
误判成测试侧（库侧信号被丢掉），又漏判 tests/*_test.h（测试头函数污染 new_funcs）。
这条用例集把当时踩过的边界固定下来，改动判据前后各跑一次。

跑法：python test_is_test_side.py      （纯标准库，无依赖）
"""

import unittest

import classify_bsm_c as C


class TestIsTestSide(unittest.TestCase):
    # 应判为测试侧：测试目录、测试驱动、测试用头文件
    TRUE_CASES = [
        'tests/test1.c',                    # 测试目录
        'test/format-test.cc',              # 文件名 + 测试目录
        'api_test/main.c',                  # 目录名带后缀 _test
        'expat/tests/basic_tests.c',        # 嵌套测试目录
        'tests/nghttp2_frame_test.h',       # 测试头文件（旧实现漏判）
        'expat/tests/minicheck.h',          # 测试框架头（旧实现漏判）
        'tests/fuzzer.c',                   # 测试目录里的 fuzz 驱动
        'fuzz/fuzz_target.c',               # fuzz 目录
        'src/pcre2test.c',                  # 库内测试驱动（词尾 test）
        'src/latest.c',                     # 已知限制：词尾恰好是 test，v9 未出现
    ]

    # 不应判为测试侧：库侧源码 / 库内 fuzz 辅助头 / 非 C 文件
    FALSE_CASES = [
        'oss-fuzz/build.sh',                # 非 C/C++ 文件
        'src/fuzzing.h',                    # 旧实现 `'fuzz' in p` 的典型误伤
        'include/zstd/fuzz_helpers.h',      # 库内 fuzz 辅助头，不是测试
        'contrib/greatest.h',               # 含 "test" 子串但不是测试文件
        'src/decompress.c',                 # 普通库源码
        'lib/misc.c',                       # 普通库源码
        'src/streaming.h',                  # 普通库头
        'tests/data.json',                  # 测试目录里的非代码文件
    ]

    def test_true_cases(self):
        for p in self.TRUE_CASES:
            with self.subTest(path=p):
                self.assertTrue(C.is_test_side(p), '%s 应判为测试侧' % p)

    def test_false_cases(self):
        for p in self.FALSE_CASES:
            with self.subTest(path=p):
                self.assertFalse(C.is_test_side(p), '%s 不应判为测试侧' % p)

    def test_case_insensitive(self):
        self.assertTrue(C.is_test_side('Tests/Foo.c'))
        self.assertTrue(C.is_test_side('src\\test\\bar.c'))   # Windows 路径分隔符

    def test_count(self):
        """用例数量固定为 18：有人删用例时这里会失败。"""
        self.assertEqual(len(self.TRUE_CASES) + len(self.FALSE_CASES), 18)


if __name__ == '__main__':
    unittest.main(verbosity=2)
