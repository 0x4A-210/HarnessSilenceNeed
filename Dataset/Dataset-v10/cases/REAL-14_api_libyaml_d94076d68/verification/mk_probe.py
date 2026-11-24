#!/usr/bin/env python3
"""给 libyaml harness 加计数桩，统计 gap 位置被执行的次数。

gap 位置：
  GAP_EMIT  —— yaml_emitter_emit() 调用处（旧版永远到不了）
  GAP_REPARSE —— 第二遍解析循环（旧版永远到不了）
  GAP_EQUAL  —— events_equal() 比较（旧版永远到不了）
"""
import re, sys

path = sys.argv[1]
out = sys.argv[2]
src = open(path, encoding="utf-8").read()

# 在文件头插入计数器声明
decl = """
/* ---- 探针：gap 计数（由 mk_probe.py 注入） ---- */
volatile unsigned long GAP_EMIT = 0;
volatile unsigned long GAP_REPARSE = 0;
volatile unsigned long GAP_EQUAL = 0;
volatile unsigned long PARSE_EVENTS = 0;
void gap_report(void);
"""
src = src.replace('#include "yaml_write_handler.h"',
                  '#include "yaml_write_handler.h"\n' + decl, 1)

# GAP_EMIT：yaml_emitter_emit 调用前
src = src.replace(
    "    if (!yaml_emitter_emit(&emitter, &event)) {",
    "    GAP_EMIT++;\n    if (!yaml_emitter_emit(&emitter, &event)) {", 1)

# PARSE_EVENTS：主解析循环每轮
src = src.replace(
    "    done = (event.type == YAML_STREAM_END_EVENT);\n    if (event_number >= MAX_EVENTS) {",
    "    PARSE_EVENTS++;\n    done = (event.type == YAML_STREAM_END_EVENT);\n    if (event_number >= MAX_EVENTS) {", 1)

# GAP_REPARSE + GAP_EQUAL：第二遍循环
src = src.replace(
    "  while (!done) {\n    if (!yaml_parser_parse(&parser, &event))\n      break;",
    "  GAP_REPARSE++;\n  while (!done) {\n    if (!yaml_parser_parse(&parser, &event))\n      break;", 1)
src = src.replace(
    "    if (events_equal(events + count, &event)) {",
    "    GAP_EQUAL++;\n    if (events_equal(events + count, &event)) {", 1)

# 报告函数
src = src.replace("delete_parser:\n", """delete_parser:

""", 1)
src += """
/* ---- 探针：输出统计 ---- */
#include <stdio.h>
void gap_report(void) {
  fprintf(stderr, "PROBE parse_events=%lu gap_emit=%lu gap_reparse=%lu gap_equal=%lu\\n",
          PARSE_EVENTS, GAP_EMIT, GAP_REPARSE, GAP_EQUAL);
}
"""

open(out, "w", encoding="utf-8").write(src)

# 校验注入点
n = 0
for i, line in enumerate(src.splitlines(), 1):
    if re.search(r"GAP_(EMIT|REPARSE|EQUAL)\+\+|PARSE_EVENTS\+\+", line):
        print(f"  {i}: {line.strip()}")
        n += 1
print(f"注入 {n} 处")
