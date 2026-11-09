# 当前方案：Dataset-v7 评测结果

本报告由本目录新运行并冻结的预测计算。
共 48 条样本。模型、推理配置、证据和原始响应均保存在本目录。
类型和显/隐、本次/非本次分组来自数据集真值，不代表检测器额外预测了这些类型。

## 总体指标

ACC 是准确率；P 是精确率。维护模块只有 needs_update 记为告警，unknown 记为未告警，因此阴性上的 unknown 可计入告警口径 TN，但不代表已经证明 satisfied_in_scope。

时间指标仅评估具有时间真值的真实阳性，以 introduced（本次）为正类。真实本次的 unknown/no_gap 计 FN；真实非本次的 unknown/no_gap 不计 TN 或 FP，但仍计入 ACC 和误报率的分母。阴性没有本次/非本次真值，其伪缺口另列。综合严格口径要求阳性同时告警且归因正确，阴性不告警。

| 判断 | ACC | P | 召回率 | 误报率 | 漏报率 | F1 | TP/FP/TN/FN |
|---|---:|---:|---:|---:|---:|---:|---|
| 阳性/阴性 | 83.33% | 86.36% | 79.17% | 12.50% | 20.83% | 82.61% | 19/3/21/5 |
| 本次/非本次 | 70.83% | 90.91% | 83.33% | 8.33% | 16.67% | 86.96% | 10/1/7/2 |
| 综合严格口径 | 79.17% | 85.00% | 70.83% | 12.50% | 29.17% | 77.27% | 17/3/21/7 |

## 未决与确认阴性

| 真值 | needs_update | satisfied_in_scope | unknown |
|---|---:|---:|---:|
| 阳性 | 19 | 2 | 3 |
| 阴性 | 3 | 15 | 6 |

维护严格已证实判断准确率（unknown 均记错）：70.83%。
时间模块：真实阳性中未决或 no_gap 共 6 条，已决但归因错误 1 条；真实阴性上报出缺口 3 条。

## 维护判断：类型 × 六维

阳性格：检出/总数；阴性格：未告警/总数（可能含 unknown）。

| 类型 | 阳-显-本次 | 阳-显-非本次 | 阳-隐-本次 | 阳-隐-非本次 | 阴-显 | 阴-隐 |
|---|---:|---:|---:|---:|---:|---:|
| api | 1/1 | 1/1 | 1/1 | 1/1 | 1/2 | 2/2 |
| configuration | 1/1 | 1/1 | 1/1 | 1/1 | 2/2 | 2/2 |
| input_format | 1/1 | 1/1 | 1/1 | 0/1 | 2/2 | 2/2 |
| state | 1/1 | 0/1 | 1/1 | 0/1 | 2/2 | 1/2 |
| lifecycle | 1/1 | 1/1 | 0/1 | 0/1 | 2/2 | 1/2 |
| mix | 1/1 | 1/1 | 1/1 | 1/1 | 2/2 | 2/2 |
| 合计 | 6/6 | 5/6 | 5/6 | 3/6 | 11/12 | 10/12 |

## 时间判断：类型 × 六维

阳性格：正确/错误/未决；阴性格：伪缺口/no_gap/unknown，不参与时间准确率。

| 类型 | 阳-显-本次 | 阳-显-非本次 | 阳-隐-本次 | 阳-隐-非本次 | 阴-显 | 阴-隐 |
|---|---:|---:|---:|---:|---:|---:|
| api | 1/0/0 | 1/0/0 | 1/0/0 | 1/0/0 | 1/0/0 | 0/0/0 |
| configuration | 0/0/1 | 1/0/0 | 1/0/0 | 1/0/0 | 0/0/0 | 0/0/1 |
| input_format | 1/0/0 | 1/0/0 | 1/0/0 | 0/0/1 | 0/0/1 | 0/0/0 |
| state | 1/0/0 | 0/0/1 | 1/0/0 | 0/0/1 | 0/0/0 | 1/0/0 |
| lifecycle | 1/0/0 | 0/1/0 | 0/0/1 | 0/0/1 | 0/0/0 | 1/0/0 |
| mix | 1/0/0 | 1/0/0 | 1/0/0 | 1/0/0 | 0/0/0 | 0/0/0 |
| 合计 | 5/0/1 | 4/1/1 | 5/0/1 | 3/0/3 | 1/0/1 | 2/0/1 |

## 综合判断：类型 × 六维

阳性格：告警且归因正确/总数；阴性格：未告警/总数。

| 类型 | 阳-显-本次 | 阳-显-非本次 | 阳-隐-本次 | 阳-隐-非本次 | 阴-显 | 阴-隐 |
|---|---:|---:|---:|---:|---:|---:|
| api | 1/1 | 1/1 | 1/1 | 1/1 | 1/2 | 2/2 |
| configuration | 0/1 | 1/1 | 1/1 | 1/1 | 2/2 | 2/2 |
| input_format | 1/1 | 1/1 | 1/1 | 0/1 | 2/2 | 2/2 |
| state | 1/1 | 0/1 | 1/1 | 0/1 | 2/2 | 1/2 |
| lifecycle | 1/1 | 0/1 | 0/1 | 0/1 | 2/2 | 1/2 |
| mix | 1/1 | 1/1 | 1/1 | 1/1 | 2/2 | 2/2 |
| 合计 | 5/6 | 4/6 | 5/6 | 3/6 | 11/12 | 10/12 |

## 维护判断逐条对照

| 样本 | 项目 | 类型 | 六维分组 | 真值 | 输出 | 对照 |
|---|---|---|---|---|---|---|
| [V3-01](../workspace/runs/task4-b/samples/case-9362b95da229/report.md) | zlib | api | 阳-显-本次 | 阳性 | needs_update | TP |
| [V3-02](../workspace/runs/task4-b/samples/case-48cd1b0e3de2/report.md) | c-ares | configuration | 阳-显-本次 | 阳性 | needs_update | TP |
| [V3-03](../workspace/runs/task4-b/samples/case-f0c7266fa426/report.md) | jq | configuration | 阳-显-非本次 | 阳性 | needs_update | TP |
| [V3-04](../workspace/runs/task4-b/samples/case-720846f31f54/report.md) | json-c | api | 阳-显-非本次 | 阳性 | needs_update | TP |
| [V3-05](../workspace/runs/task4-b/samples/case-5ea785f20901/report.md) | libucl | lifecycle | 阳-显-非本次 | 阳性 | needs_update | TP |
| [V3-06](../workspace/runs/task4-b/samples/case-98cf1124b75c/report.md) | mbedtls | mix | 阳-显-本次 | 阳性 | needs_update | TP |
| [V3-07](../workspace/runs/task4-b/samples/case-55fddd3f3d09/report.md) | lz4 | input_format | 阳-显-非本次 | 阳性 | needs_update | TP |
| [V3-08](../workspace/runs/task4-b/samples/case-929c63b63c1e/report.md) | unbound | mix | 阳-显-非本次 | 阳性 | needs_update | TP |
| [V3-09](../workspace/runs/task4-b/samples/case-f684e4780588/report.md) | pcre2 | configuration | 阳-隐-本次 | 阳性 | needs_update | TP |
| [V3-10](../workspace/runs/task4-b/samples/case-531d200d7aea/report.md) | libyaml | api | 阳-隐-非本次 | 阳性 | needs_update | TP |
| [V3-11](../workspace/runs/task4-b/samples/case-ad1f75179672/report.md) | utf8proc | input_format | 阳-隐-非本次 | 阳性 | unknown | FN |
| [V3-12](../workspace/runs/task4-b/samples/case-d02a8dd46ded/report.md) | inih | configuration | 阳-隐-非本次 | 阳性 | needs_update | TP |
| [V3-13](../workspace/runs/task4-b/samples/case-8ddb3482b851/report.md) | flac | state | 阳-显-非本次 | 阳性 | satisfied_in_scope | FN |
| [V3-14](../workspace/runs/task4-b/samples/case-dd5ddb375e2b/report.md) | xz | state | 阳-隐-非本次 | 阳性 | satisfied_in_scope | FN |
| [V3-15](../workspace/runs/task4-b/samples/case-87647660f78d/report.md) | zstd | input_format | 阳-隐-本次 | 阳性 | needs_update | TP |
| [V3-16](../workspace/runs/task4-b/samples/case-ecabeec74a73/report.md) | json-c | state | 阳-隐-本次 | 阳性 | needs_update | TP |
| [V3-17](../workspace/runs/task4-b/samples/case-14cbc0b6f269/report.md) | libpng | lifecycle | 阳-隐-非本次 | 阳性 | unknown | FN |
| [V3-18](../workspace/runs/task4-b/samples/case-4ba76669b198/report.md) | libxml2 | lifecycle | 阳-隐-本次 | 阳性 | unknown | FN |
| [V3-19](../workspace/runs/task4-b/samples/case-59cd4b778248/report.md) | utf8proc | mix | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-20](../workspace/runs/task4-b/samples/case-e45091d010ae/report.md) | pugixml | api | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-21](../workspace/runs/task4-b/samples/case-43385d78a54b/report.md) | jansson | api | 阴-显 | 阴性 | needs_update | FP |
| [V3-22](../workspace/runs/task4-b/samples/case-079603c8fa56/report.md) | cjson | lifecycle | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-23](../workspace/runs/task4-b/samples/case-7c1a7c227273/report.md) | libyaml | input_format | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-24](../workspace/runs/task4-b/samples/case-c2b21fc2d45e/report.md) | libcbor | input_format | 阴-显 | 阴性 | unknown | TN（未告警） |
| [V3-25](../workspace/runs/task4-b/samples/case-3a2f77555482/report.md) | cmark | configuration | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-26](../workspace/runs/task4-b/samples/case-dd185ff920a7/report.md) | lz4 | state | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-27](../workspace/runs/task4-b/samples/case-4f4c1a7bf85d/report.md) | miniz | lifecycle | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-28](../workspace/runs/task4-b/samples/case-0d9cd17c5534/report.md) | zstd | configuration | 阴-显 | 阴性 | unknown | TN（未告警） |
| [V3-29](../workspace/runs/task4-b/samples/case-0cba5366c40e/report.md) | tinyxml2 | mix | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-30](../workspace/runs/task4-b/samples/case-5af186a5e247/report.md) | md4c | mix | 阴-隐 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-31](../workspace/runs/task4-b/samples/case-60bc56d39296/report.md) | libxml2 | api | 阴-隐 | 阴性 | unknown | TN（未告警） |
| [V3-32](../workspace/runs/task4-b/samples/case-807a401437f5/report.md) | fmt | configuration | 阴-隐 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-33](../workspace/runs/task4-b/samples/case-a7275273276f/report.md) | zlib | configuration | 阴-隐 | 阴性 | unknown | TN（未告警） |
| [V3-34](../workspace/runs/task4-b/samples/case-10b0ecd21840/report.md) | tinyobjloader | input_format | 阴-隐 | 阴性 | unknown | TN（未告警） |
| [V3-35](../workspace/runs/task4-b/samples/case-a44709ea23b0/report.md) | libspng | input_format | 阴-隐 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-36](../workspace/runs/task4-b/samples/case-8e17f102011e/report.md) | expat | state | 阴-隐 | 阴性 | needs_update | FP |
| [V3-37](../workspace/runs/task4-b/samples/case-2e94b9ee2b64/report.md) | jansson | lifecycle | 阴-隐 | 阴性 | needs_update | FP |
| [V3-38](../workspace/runs/task4-b/samples/case-6bb735ce9ae5/report.md) | pugixml | mix | 阴-隐 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-39](../workspace/runs/task4-b/samples/case-2db22624a88e/report.md) | cjson | lifecycle | 阴-隐 | 阴性 | unknown | TN（未告警） |
| [V3-40](../workspace/runs/task4-b/samples/case-f07e053d05dc/report.md) | cmark | api | 阴-隐 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-41](../workspace/runs/task4-b/samples/case-cc734d8e8b80/report.md) | libyaml | state | 阴-隐 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-42](../workspace/runs/task4-b/samples/case-32a86b1d427a/report.md) | zlib | state | 阴-显 | 阴性 | satisfied_in_scope | TN（未告警） |
| [V3-43](../workspace/runs/task4-b/samples/case-77bf5e715662/report.md) | expat | api | 阳-隐-本次 | 阳性 | needs_update | TP |
| [V3-44](../workspace/runs/task4-b/samples/case-76def44d8ebf/report.md) | libspng | mix | 阳-隐-非本次 | 阳性 | needs_update | TP |
| [V3-45](../workspace/runs/task4-b/samples/case-babb42aa9538/report.md) | nghttp2 | mix | 阳-隐-本次 | 阳性 | needs_update | TP |
| [V3-46](../workspace/runs/task4-b/samples/case-b0ee88561b76/report.md) | nlohmann-json | input_format | 阳-显-本次 | 阳性 | needs_update | TP |
| [V3-47](../workspace/runs/task4-b/samples/case-f3b33d8d34cc/report.md) | postgresql | lifecycle | 阳-显-本次 | 阳性 | needs_update | TP |
| [V3-48](../workspace/runs/task4-b/samples/case-c6c7e6649c46/report.md) | binutils-gas | state | 阳-显-本次 | 阳性 | needs_update | TP |

## 时间判断逐条对照

| 样本 | 项目 | 类型 | 六维分组 | 真值 | 输出 | 对照 |
|---|---|---|---|---|---|---|
| [V3-01](../workspace/runs/task4-b/samples/case-9362b95da229/report.md) | zlib | api | 阳-显-本次 | introduced | introduced | 正确 |
| [V3-02](../workspace/runs/task4-b/samples/case-48cd1b0e3de2/report.md) | c-ares | configuration | 阳-显-本次 | introduced | unknown | 未决/无缺口 |
| [V3-03](../workspace/runs/task4-b/samples/case-f0c7266fa426/report.md) | jq | configuration | 阳-显-非本次 | preexisting | preexisting | 正确 |
| [V3-04](../workspace/runs/task4-b/samples/case-720846f31f54/report.md) | json-c | api | 阳-显-非本次 | preexisting | preexisting | 正确 |
| [V3-05](../workspace/runs/task4-b/samples/case-5ea785f20901/report.md) | libucl | lifecycle | 阳-显-非本次 | preexisting | introduced | 错误 |
| [V3-06](../workspace/runs/task4-b/samples/case-98cf1124b75c/report.md) | mbedtls | mix | 阳-显-本次 | introduced | introduced | 正确 |
| [V3-07](../workspace/runs/task4-b/samples/case-55fddd3f3d09/report.md) | lz4 | input_format | 阳-显-非本次 | preexisting | preexisting | 正确 |
| [V3-08](../workspace/runs/task4-b/samples/case-929c63b63c1e/report.md) | unbound | mix | 阳-显-非本次 | preexisting | preexisting | 正确 |
| [V3-09](../workspace/runs/task4-b/samples/case-f684e4780588/report.md) | pcre2 | configuration | 阳-隐-本次 | introduced | introduced | 正确 |
| [V3-10](../workspace/runs/task4-b/samples/case-531d200d7aea/report.md) | libyaml | api | 阳-隐-非本次 | preexisting | preexisting | 正确 |
| [V3-11](../workspace/runs/task4-b/samples/case-ad1f75179672/report.md) | utf8proc | input_format | 阳-隐-非本次 | preexisting | not_applicable | 未决/无缺口 |
| [V3-12](../workspace/runs/task4-b/samples/case-d02a8dd46ded/report.md) | inih | configuration | 阳-隐-非本次 | preexisting | preexisting | 正确 |
| [V3-13](../workspace/runs/task4-b/samples/case-8ddb3482b851/report.md) | flac | state | 阳-显-非本次 | preexisting | not_applicable | 未决/无缺口 |
| [V3-14](../workspace/runs/task4-b/samples/case-dd5ddb375e2b/report.md) | xz | state | 阳-隐-非本次 | preexisting | not_applicable | 未决/无缺口 |
| [V3-15](../workspace/runs/task4-b/samples/case-87647660f78d/report.md) | zstd | input_format | 阳-隐-本次 | introduced | introduced | 正确 |
| [V3-16](../workspace/runs/task4-b/samples/case-ecabeec74a73/report.md) | json-c | state | 阳-隐-本次 | introduced | introduced | 正确 |
| [V3-17](../workspace/runs/task4-b/samples/case-14cbc0b6f269/report.md) | libpng | lifecycle | 阳-隐-非本次 | preexisting | not_applicable | 未决/无缺口 |
| [V3-18](../workspace/runs/task4-b/samples/case-4ba76669b198/report.md) | libxml2 | lifecycle | 阳-隐-本次 | introduced | not_applicable | 未决/无缺口 |
| [V3-19](../workspace/runs/task4-b/samples/case-59cd4b778248/report.md) | utf8proc | mix | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-20](../workspace/runs/task4-b/samples/case-e45091d010ae/report.md) | pugixml | api | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-21](../workspace/runs/task4-b/samples/case-43385d78a54b/report.md) | jansson | api | 阴-显 | 不适用 | preexisting | 伪缺口 |
| [V3-22](../workspace/runs/task4-b/samples/case-079603c8fa56/report.md) | cjson | lifecycle | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-23](../workspace/runs/task4-b/samples/case-7c1a7c227273/report.md) | libyaml | input_format | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-24](../workspace/runs/task4-b/samples/case-c2b21fc2d45e/report.md) | libcbor | input_format | 阴-显 | 不适用 | unknown | 无时间真值 |
| [V3-25](../workspace/runs/task4-b/samples/case-3a2f77555482/report.md) | cmark | configuration | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-26](../workspace/runs/task4-b/samples/case-dd185ff920a7/report.md) | lz4 | state | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-27](../workspace/runs/task4-b/samples/case-4f4c1a7bf85d/report.md) | miniz | lifecycle | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-28](../workspace/runs/task4-b/samples/case-0d9cd17c5534/report.md) | zstd | configuration | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-29](../workspace/runs/task4-b/samples/case-0cba5366c40e/report.md) | tinyxml2 | mix | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-30](../workspace/runs/task4-b/samples/case-5af186a5e247/report.md) | md4c | mix | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-31](../workspace/runs/task4-b/samples/case-60bc56d39296/report.md) | libxml2 | api | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-32](../workspace/runs/task4-b/samples/case-807a401437f5/report.md) | fmt | configuration | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-33](../workspace/runs/task4-b/samples/case-a7275273276f/report.md) | zlib | configuration | 阴-隐 | 不适用 | unknown | 无时间真值 |
| [V3-34](../workspace/runs/task4-b/samples/case-10b0ecd21840/report.md) | tinyobjloader | input_format | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-35](../workspace/runs/task4-b/samples/case-a44709ea23b0/report.md) | libspng | input_format | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-36](../workspace/runs/task4-b/samples/case-8e17f102011e/report.md) | expat | state | 阴-隐 | 不适用 | introduced | 伪缺口 |
| [V3-37](../workspace/runs/task4-b/samples/case-2e94b9ee2b64/report.md) | jansson | lifecycle | 阴-隐 | 不适用 | introduced | 伪缺口 |
| [V3-38](../workspace/runs/task4-b/samples/case-6bb735ce9ae5/report.md) | pugixml | mix | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-39](../workspace/runs/task4-b/samples/case-2db22624a88e/report.md) | cjson | lifecycle | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-40](../workspace/runs/task4-b/samples/case-f07e053d05dc/report.md) | cmark | api | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-41](../workspace/runs/task4-b/samples/case-cc734d8e8b80/report.md) | libyaml | state | 阴-隐 | 不适用 | not_applicable | 无时间真值 |
| [V3-42](../workspace/runs/task4-b/samples/case-32a86b1d427a/report.md) | zlib | state | 阴-显 | 不适用 | not_applicable | 无时间真值 |
| [V3-43](../workspace/runs/task4-b/samples/case-77bf5e715662/report.md) | expat | api | 阳-隐-本次 | introduced | introduced | 正确 |
| [V3-44](../workspace/runs/task4-b/samples/case-76def44d8ebf/report.md) | libspng | mix | 阳-隐-非本次 | preexisting | preexisting | 正确 |
| [V3-45](../workspace/runs/task4-b/samples/case-babb42aa9538/report.md) | nghttp2 | mix | 阳-隐-本次 | introduced | introduced | 正确 |
| [V3-46](../workspace/runs/task4-b/samples/case-b0ee88561b76/report.md) | nlohmann-json | input_format | 阳-显-本次 | introduced | introduced | 正确 |
| [V3-47](../workspace/runs/task4-b/samples/case-f3b33d8d34cc/report.md) | postgresql | lifecycle | 阳-显-本次 | introduced | introduced | 正确 |
| [V3-48](../workspace/runs/task4-b/samples/case-c6c7e6649c46/report.md) | binutils-gas | state | 阳-显-本次 | introduced | introduced | 正确 |

## 综合判断逐条对照

| 样本 | 项目 | 类型 | 六维分组 | 真值 | 输出 | 对照 |
|---|---|---|---|---|---|---|
| [V3-01](../workspace/runs/task4-b/samples/case-9362b95da229/report.md) | zlib | api | 阳-显-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-02](../workspace/runs/task4-b/samples/case-48cd1b0e3de2/report.md) | c-ares | configuration | 阳-显-本次 | 阳性/introduced | 告警/unknown | 综合漏判 |
| [V3-03](../workspace/runs/task4-b/samples/case-f0c7266fa426/report.md) | jq | configuration | 阳-显-非本次 | 阳性/preexisting | 告警/preexisting | 正确 |
| [V3-04](../workspace/runs/task4-b/samples/case-720846f31f54/report.md) | json-c | api | 阳-显-非本次 | 阳性/preexisting | 告警/preexisting | 正确 |
| [V3-05](../workspace/runs/task4-b/samples/case-5ea785f20901/report.md) | libucl | lifecycle | 阳-显-非本次 | 阳性/preexisting | 告警/introduced | 综合漏判 |
| [V3-06](../workspace/runs/task4-b/samples/case-98cf1124b75c/report.md) | mbedtls | mix | 阳-显-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-07](../workspace/runs/task4-b/samples/case-55fddd3f3d09/report.md) | lz4 | input_format | 阳-显-非本次 | 阳性/preexisting | 告警/preexisting | 正确 |
| [V3-08](../workspace/runs/task4-b/samples/case-929c63b63c1e/report.md) | unbound | mix | 阳-显-非本次 | 阳性/preexisting | 告警/preexisting | 正确 |
| [V3-09](../workspace/runs/task4-b/samples/case-f684e4780588/report.md) | pcre2 | configuration | 阳-隐-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-10](../workspace/runs/task4-b/samples/case-531d200d7aea/report.md) | libyaml | api | 阳-隐-非本次 | 阳性/preexisting | 告警/preexisting | 正确 |
| [V3-11](../workspace/runs/task4-b/samples/case-ad1f75179672/report.md) | utf8proc | input_format | 阳-隐-非本次 | 阳性/preexisting | 未告警 | 综合漏判 |
| [V3-12](../workspace/runs/task4-b/samples/case-d02a8dd46ded/report.md) | inih | configuration | 阳-隐-非本次 | 阳性/preexisting | 告警/preexisting | 正确 |
| [V3-13](../workspace/runs/task4-b/samples/case-8ddb3482b851/report.md) | flac | state | 阳-显-非本次 | 阳性/preexisting | 未告警 | 综合漏判 |
| [V3-14](../workspace/runs/task4-b/samples/case-dd5ddb375e2b/report.md) | xz | state | 阳-隐-非本次 | 阳性/preexisting | 未告警 | 综合漏判 |
| [V3-15](../workspace/runs/task4-b/samples/case-87647660f78d/report.md) | zstd | input_format | 阳-隐-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-16](../workspace/runs/task4-b/samples/case-ecabeec74a73/report.md) | json-c | state | 阳-隐-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-17](../workspace/runs/task4-b/samples/case-14cbc0b6f269/report.md) | libpng | lifecycle | 阳-隐-非本次 | 阳性/preexisting | 未告警 | 综合漏判 |
| [V3-18](../workspace/runs/task4-b/samples/case-4ba76669b198/report.md) | libxml2 | lifecycle | 阳-隐-本次 | 阳性/introduced | 未告警 | 综合漏判 |
| [V3-19](../workspace/runs/task4-b/samples/case-59cd4b778248/report.md) | utf8proc | mix | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-20](../workspace/runs/task4-b/samples/case-e45091d010ae/report.md) | pugixml | api | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-21](../workspace/runs/task4-b/samples/case-43385d78a54b/report.md) | jansson | api | 阴-显 | 阴性 | 告警/preexisting | 误报 |
| [V3-22](../workspace/runs/task4-b/samples/case-079603c8fa56/report.md) | cjson | lifecycle | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-23](../workspace/runs/task4-b/samples/case-7c1a7c227273/report.md) | libyaml | input_format | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-24](../workspace/runs/task4-b/samples/case-c2b21fc2d45e/report.md) | libcbor | input_format | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-25](../workspace/runs/task4-b/samples/case-3a2f77555482/report.md) | cmark | configuration | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-26](../workspace/runs/task4-b/samples/case-dd185ff920a7/report.md) | lz4 | state | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-27](../workspace/runs/task4-b/samples/case-4f4c1a7bf85d/report.md) | miniz | lifecycle | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-28](../workspace/runs/task4-b/samples/case-0d9cd17c5534/report.md) | zstd | configuration | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-29](../workspace/runs/task4-b/samples/case-0cba5366c40e/report.md) | tinyxml2 | mix | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-30](../workspace/runs/task4-b/samples/case-5af186a5e247/report.md) | md4c | mix | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-31](../workspace/runs/task4-b/samples/case-60bc56d39296/report.md) | libxml2 | api | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-32](../workspace/runs/task4-b/samples/case-807a401437f5/report.md) | fmt | configuration | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-33](../workspace/runs/task4-b/samples/case-a7275273276f/report.md) | zlib | configuration | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-34](../workspace/runs/task4-b/samples/case-10b0ecd21840/report.md) | tinyobjloader | input_format | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-35](../workspace/runs/task4-b/samples/case-a44709ea23b0/report.md) | libspng | input_format | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-36](../workspace/runs/task4-b/samples/case-8e17f102011e/report.md) | expat | state | 阴-隐 | 阴性 | 告警/introduced | 误报 |
| [V3-37](../workspace/runs/task4-b/samples/case-2e94b9ee2b64/report.md) | jansson | lifecycle | 阴-隐 | 阴性 | 告警/introduced | 误报 |
| [V3-38](../workspace/runs/task4-b/samples/case-6bb735ce9ae5/report.md) | pugixml | mix | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-39](../workspace/runs/task4-b/samples/case-2db22624a88e/report.md) | cjson | lifecycle | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-40](../workspace/runs/task4-b/samples/case-f07e053d05dc/report.md) | cmark | api | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-41](../workspace/runs/task4-b/samples/case-cc734d8e8b80/report.md) | libyaml | state | 阴-隐 | 阴性 | 未告警 | 正确 |
| [V3-42](../workspace/runs/task4-b/samples/case-32a86b1d427a/report.md) | zlib | state | 阴-显 | 阴性 | 未告警 | 正确 |
| [V3-43](../workspace/runs/task4-b/samples/case-77bf5e715662/report.md) | expat | api | 阳-隐-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-44](../workspace/runs/task4-b/samples/case-76def44d8ebf/report.md) | libspng | mix | 阳-隐-非本次 | 阳性/preexisting | 告警/preexisting | 正确 |
| [V3-45](../workspace/runs/task4-b/samples/case-babb42aa9538/report.md) | nghttp2 | mix | 阳-隐-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-46](../workspace/runs/task4-b/samples/case-b0ee88561b76/report.md) | nlohmann-json | input_format | 阳-显-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-47](../workspace/runs/task4-b/samples/case-f3b33d8d34cc/report.md) | postgresql | lifecycle | 阳-显-本次 | 阳性/introduced | 告警/introduced | 正确 |
| [V3-48](../workspace/runs/task4-b/samples/case-c6c7e6649c46/report.md) | binutils-gas | state | 阳-显-本次 | 阳性/introduced | 告警/introduced | 正确 |

## 结果边界

这些结果来自同一开发数据集，不能作为独立测试集的泛化结论。本次整理保持推理提示词、判断逻辑与有效预算；未针对样本标签改变判断。代码使用语法解析和符号搜索补读证据，不包含完整控制流图、符号执行或编译级数据流证明。
