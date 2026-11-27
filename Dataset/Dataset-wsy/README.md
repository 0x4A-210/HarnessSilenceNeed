# OSS-Fuzz Harness 退化数据集

## 数据集概述

本数据集包含 **13 个真实的 OSS-Fuzz C/C++ 项目的 harness 退化案例**，分为两批：

### 第一批（REAL-01 ~ REAL-07）- 原始案例
1. **REAL-01_input_format_libplist_429cbc660a** - libplist JSON 格式支持
2. **REAL-02_api_c-ares_7d3591ee8a** - c-ares API 变更
3. **REAL-03_api_json-c_538b046884** - json-c API 添加
4. **REAL-04_state_json-c_a68566bf6a** - json-c 状态管理
5. **REAL-05_lifecycle_c-ares_dbd4c441f0** - c-ares 生命周期
6. **REAL-06_configuration_inih_1e80a47dff** - inih 配置
7. **REAL-07_mix_expat_b1d03960** - expat Billion Laughs 攻击防护 (mix 类型)

### 第二批（REAL-01-B ~ REAL-06-B）- 新增案例
1. **REAL-01-B_input_format_libtiff_b0469e81** - libtiff WebP tile/strip 维度验证
2. **REAL-02-B_api_tcpdump_4e2e9c24** - tcpdump OpenFlow 解析 API 重构
3. **REAL-03-B_state_libtiff_2e822691** - libtiff TIFFStartStrip() 状态检查
4. **REAL-04-B_lifecycle_tcpdump_e1c739a8** - tcpdump Juniper 结构体初始化
5. **REAL-05-B_configuration_flac_d52921bc** - flac sanitizer 配置宏
6. **REAL-06-B_mix_flac_21ffc935** - flac 命令行工具 fuzzer (mix 类型)

## 覆盖的项目

- **libtiff** - 2 个案例 (input_format, state)
- **tcpdump** - 2 个案例 (api, lifecycle)
- **flac** - 2 个案例 (configuration, mix)
- **libplist** - 1 个案例 (input_format)
- **c-ares** - 2 个案例 (api, lifecycle)
- **json-c** - 2 个案例 (api, state)
- **inih** - 1 个案例 (configuration)
- **expat** - 1 个案例 (mix)

## 覆盖的退化类型

| 类型 | 案例 | 描述 |
|------|------|------|
| input_format | REAL-01, REAL-01-B | 库增加输入格式支持/验证，harness 未更新输入生成 |
| api | REAL-02, REAL-03, REAL-02-B | 库 API 变更，harness 调用方式未同步更新 |
| state | REAL-04, REAL-03-B | 库增加状态管理，harness 未测试状态转换 |
| lifecycle | REAL-05, REAL-04-B | 库改进资源生命周期，harness 未验证改进 |
| configuration | REAL-06, REAL-05-B | 库增加配置选项，harness 未测试不同配置 |
| mix | REAL-07, REAL-06-B | 多个维度同时退化，需同时修复 |

## 每个案例的文件结构

```
REAL-XX_[type]_[project]_[hash]/
├── NOTES.md              # 详细说明（中英文）
├── label.json            # 退化类型标签和证据
├── case.json             # 案例基本信息
├── meta.json             # 提交元数据
└── input/
    ├── change.diff       # 完整 git diff（包含所有文件变更）
    ├── source/           # 核心源文件
    │   ├── *.c / *.cc    # 修改后的源文件
    │   ├── *_old.c       # 修改前的源文件
    │   └── ...
    └── harness/
        └── oss-fuzz/     # OSS-Fuzz 配置（部分案例）
            ├── build.sh
            ├── project.yaml
            └── ...
```

## 文件完整性说明

### 第一批案例 (REAL-01 ~ REAL-07)
- ✅ NOTES.md, label.json, case.json, meta.json
- ⚠️  input/change.diff - 完整 diff
- ⏳ input/source/ - 源文件补充中
- ⏳ input/harness/oss-fuzz/ - 配置文件补充中

### 第二批案例 (REAL-01-B ~ REAL-06-B)
- ✅ NOTES.md, label.json, case.json, meta.json
- ✅ input/change.diff - 完整 diff
- ✅ input/source/ - 核心源文件完整
  - 修改后的文件 (e.g., tif_webp.c)
  - 修改前的文件 (e.g., tif_webp_old.c)
  - 完整 diff 文件
- ⏳ input/harness/oss-fuzz/ - 配置文件补充中

## 数据集统计

| 指标 | 数值 |
|------|------|
| 总案例数 | 13 |
| 不同项目数 | 8 |
| 总 diff 行数 | ~3000+ |
| 源文件数量 | ~40+ |
| 类型覆盖 | 6/6 (100%) |

## 使用方式

### 1. 研究模式
用于学习 harness 退化的具体案例：
```bash
cd REAL-XX_[type]_[project]_[hash]
cat NOTES.md        # 阅读案例说明
cat label.json      # 查看退化分析
diff -u input/source/*_old.c input/source/*.c  # 对比代码变更
```

### 2. 评估模式
用于评估 harness 更新方案：
```bash
# 查看完整变更
cat input/change.diff
# 分析源文件
cat input/source/*.c
```

### 3. 重现模式
用于验证退化情况：
```bash
# 获取 OSS-Fuzz 配置
cp -r input/harness/oss-fuzz/* /path/to/oss-fuzz/projects/[project]/

# 使用提交前后的源文件对比
# 在提交前后编译 harness，对比覆盖率
```

## 关键观察

1. **input_format 类型**：通常涉及 ~10-50 行代码，新增的输入验证/处理
2. **api 类型**：通常涉及 ~200-500 行代码，API 签名或调用方式变更
3. **state 类型**：通常涉及 ~10-50 行代码，新增状态检查或管理
4. **lifecycle 类型**：通常涉及 ~10-20 行代码，资源初始化/清理逻辑
5. **configuration 类型**：通常涉及 ~5-10 行代码，配置开关或宏定义
6. **mix 类型**：通常涉及 ~100+ 行代码，同时涉及多个维度

## 数据来源

- OSS-Fuzz GitHub: https://github.com/google/oss-fuzz
- CISPA 研究论文: https://github.com/CISPA-SysSec/fuzz-harness-degradation
- 各项目官方仓库 (GitHub/GitLab)

## 注意事项

1. 所有提交均来自真实的开源项目
2. 所有案例均经过代码分析验证
3. 提交哈希值可直接用于 git 检出
4. 源文件已完整导出（包含完整注释和格式）

