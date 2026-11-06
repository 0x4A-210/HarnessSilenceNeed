# Eight-case Hold-out: Exact Inputs and Outputs

All eight outputs were produced once with the frozen prompt, schema, model, and parameters. GPT saw only the exact linked input file for that case; it did not receive this mapping, any degradation result, H1/harness diff, pilot answer, or error analysis.

Strict result against the phase-1 confirmed-positive labels: **3/8 YES (TP), 5/8 NO (FN)**.

The complete input is not abbreviated in this report: each link points to the byte-for-byte UTF-8 text piped to `codex exec`, including the fixed prompt, anonymous case, and boundary markers. The same eight input/output pairs are also embedded in machine-readable `results/input_output_pairs.jsonl`.

## C106: tidy-html5

- Commit: `c8fbde59031ebe2bf11154a24a88d6bb12af2bbd`
- Label / prediction: Positive / **NO (FN)**
- Confidence: 96
- Exact GPT input: [`inputs/C106.txt`](../inputs/C106.txt) (`sha256:77954bdc4458aae03891d9637df24d29f843113ececfdb32d7724ae02623a74a`)
- Exact raw output: [`results/raw/C106.json`](../results/raw/C106.json)
- Positive mechanism observability: `partial`
- Post-run audit: The NO answer correctly traces H0 into the rewritten parser and finds no caller-visible protocol change. It misses the historical degradation because the fixed maintenance definition and static input provide no runtime throughput or complexity evidence.

Exact JSON returned by GPT:

```json
{
  "case_id": "C106",
  "maintenance_needed": false,
  "confidence": 96,
  "change_types": [
    "internal parser refactor",
    "parser control-flow and state-management changes",
    "bug fixes and defensive checks"
  ],
  "affected_functions": [
    "ParseHTMLWithNode",
    "TY_(ParseBlock)",
    "TY_(ParseBody)",
    "TY_(ParseColGroup)",
    "TY_(ParseDatalist)",
    "TY_(ParseDefList)",
    "TY_(ParseFrameSet)",
    "TY_(ParseHead)",
    "TY_(ParseHTML)",
    "TY_(ParseInline)",
    "TY_(ParseList)",
    "TY_(InitParserStack)",
    "growParserStack",
    "GetParserForNode"
  ],
  "reason": "The commit substantially refactors existing HTML parsing from recursive ParseTag dispatch toward a heap-backed parser-memory stack and re-entrant parser functions, but it does not introduce a new public entry point, configuration requirement, initialization protocol, or input constraint. The existing fuzzers already drive the changed parser through tidyParseBuffer, tidyParseString, and tidyParseFile, with cleanup, diagnostics, output generation, and varied boolean options. Thus the changed internal control flow remains reachable with fuzz-controlled markup under adequate document state.",
  "evidence": [
    "tidy_fuzzer invokes tidyParseBuffer followed by tidyCleanAndRepair, tidyRunDiagnostics, and tidySaveBuffer.",
    "tidy_parse_string_fuzzer and tidy_xml_fuzzer pass fuzz-controlled strings to tidyParseString; tidy_parse_file_fuzzer and tidy_general_fuzzer also exercise tidyParseFile.",
    "tidy_general_fuzzer varies the output mode and a broad bool_options array before parsing fuzz-controlled data.",
    "The diff changes internal dispatch in ParseHTMLWithNode and converts parsers such as TY_(ParseBlock), TY_(ParseBody), and TY_(ParseInline) to return nodes and preserve state with TidyParserMemory.",
    "Parser-stack initialization remains internal to document parsing; changes such as increasing default_size from 16 to 32 and using doc->allocator impose no new harness-side setup.",
    "The defensive GetParserForNode check changes `node->tag == NULL` to `!node || node->tag == NULL`, without altering the public parsing API."
  ],
  "recommended_action": "Keep the existing harnesses unchanged; they already exercise the affected high-level parsing paths with fuzz-controlled HTML/XML content and configuration choices."
}
```

## C107: leptonica

- Commit: `f201a12680befcf6f49877f3cd1aba2c18c00301`
- Label / prediction: Positive / **NO (FN)**
- Confidence: 99
- Exact GPT input: [`inputs/C107.txt`](../inputs/C107.txt) (`sha256:e18f8c28c1b3ef0fb0a7812e96c69ac7d90b7f4a0e31bfce089c59f6db76e0bf`)
- Exact raw output: [`results/raw/C107.json`](../results/raw/C107.json)
- Positive mechanism observability: `none`
- Post-run audit: Only the unrelated cleanpdf production diff remained. The answer correctly identifies it as an always-true preprocessor cleanup outside the supplied H0 targets. The true cause is not inferable from the allowed evidence.

Exact JSON returned by GPT:

```json
{
  "case_id": "C107",
  "maintenance_needed": false,
  "confidence": 99,
  "change_types": [
    "comment clarification",
    "dead conditional-compilation cleanup"
  ],
  "affected_functions": [
    "main"
  ],
  "reason": "The commit does not introduce or modify runtime functionality relevant to the existing fuzz targets. It clarifies a comment and removes `#if 1` wrappers around code that was already compiled and executed. The existing harnesses target in-memory image-processing and barcode APIs, while the changed file is the standalone `cleanpdf` program; no entry point, API contract, initialization requirement, configuration, or input constraint used by those harnesses changes.",
  "evidence": [
    "`USE_PDFTOPPM` remains defined as `1`; only its comment changes from `pdftoppm` to `pdftoppm (recommended)`.",
    "Every removed conditional is `#if 1`, so the enclosed PDF discovery, rasterization, cleanup, and PDF-generation blocks remain active after preprocessing.",
    "The platform-specific `mkdir`/`_mkdir` conditional remains intact; only surrounding indentation and the always-true wrapper change.",
    "`pix3_fuzzer.cc` invokes image APIs after `pixReadMemSpix`, and `barcode_fuzzer.cc` invokes `pixProcessBarcodes`; neither calls `cleanpdf`'s `main` or any changed code."
  ],
  "recommended_action": "No fuzz-harness maintenance is required for this commit."
}
```

## C108: wuffs

- Commit: `f6f2ac4206d9d90cd13f905ac84fdcfe1b7ed801`
- Label / prediction: Positive / **YES (TP)**
- Confidence: 98
- Exact GPT input: [`inputs/C108.txt`](../inputs/C108.txt) (`sha256:2c6e47fd36fe3342cde4f540146befc8f0ea1c24e81a58cad6cdaf054096033e`)
- Exact raw output: [`results/raw/C108.json`](../results/raw/C108.json)
- Positive mechanism observability: `yes`
- Post-run audit: The YES answer identifies the new BMP header and 32-bpp pixel paths and contrasts them with the supplied GIF/zlib H0. The mechanism and cited code are aligned.

Exact JSON returned by GPT:

```json
{
  "case_id": "C108",
  "maintenance_needed": true,
  "confidence": 98,
  "change_types": [
    "new input-format support",
    "attack-surface expansion",
    "new pixel-conversion paths"
  ],
  "affected_functions": [
    "decoder.decode_image_config?",
    "wuffs_base__pixel_swizzler__prepare",
    "wuffs_base__pixel_swizzler__prepare__bgra_nonpremul",
    "wuffs_base__composite_premul_nonpremul_u32_axxx"
  ],
  "reason": "The commit materially expands BMP decoding to accept BITMAPINFOHEADER sizes 40 and 108 in addition to 124, and adds 32-bpp BGRA_NONPREMUL decoding plus new swizzler/compositing paths. The supplied harnesses exercise only GIF and zlib entry points, so they do not provide input control over BMP headers, masks, compression normalization, or 32-bpp pixel data. The generic build loop does not establish that a BMP target exists because no BMP harness is supplied.",
  "evidence": [
    "`gif_fuzzer.c` initializes `wuffs_gif__decoder` and invokes only GIF decode methods.",
    "`zlib_fuzzer.c` initializes `wuffs_zlib__decoder` and invokes only `wuffs_zlib__decoder__transform_io`.",
    "`decoder.decode_image_config?` now accepts `bitmap_info_len` values 40, 108, and 124, whereas it previously accepted only 124.",
    "BMP decoding now accepts `bits_per_pixel == 32` and selects `BGRA_NONPREMUL` (`repr: 0x4500_8888`).",
    "The change parses `mask_r`, `mask_g`, `mask_b`, and `mask_a`, and conditionally converts BITFIELDS compression value 3 to uncompressed handling.",
    "`wuffs_base__pixel_swizzler__prepare` gains a `BGRA_NONPREMUL` branch with new SRC and SRC_OVER conversion implementations."
  ],
  "recommended_action": "Add or update a BMP fuzz target to drive the full image-config, frame-config, and frame-decode path with version 3/4/5 headers, 32-bpp data, explicit channel masks, and relevant destination pixel formats/blend modes."
}
```

## C109: jansson

- Commit: `50953fb1faccced4d80c02c17b076d5b06910f84`
- Label / prediction: Positive / **NO (FN)**
- Confidence: 97
- Exact GPT input: [`inputs/C109.txt`](../inputs/C109.txt) (`sha256:e8ead93f99f73fd43bbf846c8a3d2eb112894e970a5cfcf648a1bac75d04fd8c`)
- Exact raw output: [`results/raw/C109.json`](../results/raw/C109.json)
- Positive mechanism observability: `ambiguous`
- Post-run audit: The answer correctly observes that H0 already parses reals and calls both dump paths that reach jsonp_dtostr/dtoa_r. The phase-1 coverage-ratio positive does not by itself prove a new semantic harness requirement, so the NO is defensible under the frozen prompt despite being an FN against the historical label.

Exact JSON returned by GPT:

```json
{
  "case_id": "C109",
  "maintenance_needed": false,
  "confidence": 97,
  "change_types": [
    "internal numeric-conversion implementation change",
    "buffer-size adjustment"
  ],
  "affected_functions": [
    "json_loadb",
    "json_dumps",
    "json_dump_callback",
    "jsonp_strtod",
    "jsonp_dtostr",
    "dtoa_r"
  ],
  "reason": "The commit replaces the internal floating-point formatting path with dtoa-based logic, but it does not introduce a new public entry point, protocol, initialization requirement, or input constraint. The existing harness already sends arbitrary bytes through json_loadb, which can create real values, and then serializes successful values through both json_dumps and json_dump_callback with fuzz-controlled dump flags, including JSON_REAL_PRECISION. Those high-level paths invoke the changed jsonp_dtostr/dtoa_r implementation, so no harness maintenance is required.",
  "evidence": [
    "The harness calls json_loadb(text, size, load_flags, &error) on the fuzz-controlled payload.",
    "After a successful load, the harness calls either json_dumps(jobj, dump_flags & ~JSON_MAX_INDENT) or json_dump_callback(jobj, json_dump_counter, &counter, dump_flags).",
    "dump_flags are derived directly from fuzz input and include the JSON_REAL_PRECISION field shown by ((dump_flags >> 11) & 0x1F) << 11.",
    "src/strconv.c changes jsonp_dtostr internally to call dtoa_r when DTOA_ENABLED; no new caller-facing arguments or setup are added.",
    "src/dump.c only reduces MAX_INTEGER_STR_LENGTH and MAX_REAL_STR_LENGTH from 100 to 25."
  ],
  "recommended_action": "Keep the existing harness unchanged; it already exercises the modified real-number parsing and serialization paths with fuzz-controlled JSON data and formatting flags."
}
```

## C110: meshoptimizer

- Commit: `1296f84bc719a2be75088650681c6390e079fdc0`
- Label / prediction: Positive / **NO (FN)**
- Confidence: 100
- Exact GPT input: [`inputs/C110.txt`](../inputs/C110.txt) (`sha256:e87546dd7879ca6cb5abf427ccf061f2141bcdd6ff9df8b4e5dd3b4a83a91ad1`)
- Exact raw output: [`results/raw/C110.json`](../results/raw/C110.json)
- Positive mechanism observability: `none`
- Post-run audit: The exact allowed Source Change was empty, and the answer explicitly based NO on that absence. No model can recover the hidden harness-surface reduction from this input alone.

Exact JSON returned by GPT:

```json
{
  "case_id": "C110",
  "maintenance_needed": false,
  "confidence": 100,
  "change_types": [],
  "affected_functions": [],
  "reason": "No production-source changes are present in the supplied diff. Therefore, there is no evidence of any new or modified functionality, entry point, API protocol, initialization/state requirement, configuration, input constraint, or attack surface that would make the existing harness inadequate.",
  "evidence": [
    "The S0 -> S1 production-source diff is empty.",
    "The existing harness already invokes meshopt_decodeIndexBuffer, meshopt_decodeIndexSequence, and meshopt_decodeVertexBuffer with their documented supported stride variants, but the commit supplies no change requiring those calls or their setup to be revised."
  ],
  "recommended_action": "Keep the existing fuzz harness unchanged."
}
```

## C111: h2o

- Commit: `93af1383b248e9284ba5f63211b4fbb4c828d060`
- Label / prediction: Positive / **YES (TP)**
- Confidence: 99
- Exact GPT input: [`inputs/C111.txt`](../inputs/C111.txt) (`sha256:afac02cc66c1d7d99549a55805c1f18ebab3a0abd1ca065c61afe4889b02738d`)
- Exact raw output: [`results/raw/C111.json`](../results/raw/C111.json)
- Positive mechanism observability: `yes`
- Post-run audit: The YES answer identifies the new external protocol surface, its state/setup requirements, and the absence of an HTTP/3 route in H0.

Exact JSON returned by GPT:

```json
{
  "case_id": "C111",
  "maintenance_needed": true,
  "confidence": 99,
  "change_types": [
    "new_protocol_entry_point",
    "attack_surface_expansion",
    "new_initialization_and_state_requirements",
    "new_input_format"
  ],
  "affected_functions": [
    "h2o_http3_read_socket",
    "h2o_http3_server_accept",
    "h2o_http3_read_frame",
    "h2o_http3_handle_settings_frame",
    "h2o_qpack_parse_request",
    "h2o_qpack_decoder_handle_input"
  ],
  "reason": "The commit adds an HTTP/3-over-QUIC server/client stack and QPACK parsing, but the existing network harness is compiled for exactly one of HTTP1 or HTTP2 and invokes only h2o_http1_accept or h2o_http2_accept over a SOCK_STREAM socketpair. Arbitrary harness bytes therefore cannot enter the new QUIC datagram, HTTP/3 frame, control-stream, or QPACK paths. Exercising this new externally supplied protocol surface also requires HTTP/3 and QUIC context, socket, connection, and stream state that the current initialization does not create. This is a substantive new fuzz-harness maintenance need, not merely a refactor of an already-covered high-level path.",
  "evidence": [
    "fuzz/driver.cc rejects configurations without HTTP1 or HTTP2 and requires exactly one of those macros.",
    "create_accepted constructs H2O_SOCKET_FLAG_IS_ACCEPTED_CONNECTION and calls only h2o_http1_accept or h2o_http2_accept.",
    "The harness transports fuzz input through AF_UNIX/SOCK_STREAM, whereas the new HTTP/3 code introduces QUIC packet handling through h2o_http3_read_socket and server acceptance through h2o_http3_server_accept.",
    "New h2o_http3_init_context and h2o_http3_init_conn APIs require HTTP/3 context, QUIC context, socket, callback, connection, and stream initialization absent from the harness.",
    "New input-facing parsers include h2o_http3_read_frame, h2o_http3_decode_priority_frame, h2o_http3_handle_settings_frame, h2o_qpack_decoder_handle_input, and h2o_qpack_parse_request.",
    "fuzz/driver_url.cc calls only h2o_url_parse and does not reach HTTP/3 or QPACK processing."
  ],
  "recommended_action": "Add a dedicated HTTP/3 fuzz target and OSS-Fuzz build/corpus wiring that initializes the required QUIC and h2o_http3 contexts and feeds controlled datagram/stream input through the HTTP/3 server path. Consider separate stateful targets for HTTP/3 frame/control-stream and QPACK decoding if full QUIC setup cannot efficiently expose those parsers."
}
```

## C112: c-ares

- Commit: `955df983d7f643d1b00aa433f31ca3ec7f86b4bd`
- Label / prediction: Positive / **NO (FN)**
- Confidence: 96
- Exact GPT input: [`inputs/C112.txt`](../inputs/C112.txt) (`sha256:7a110d4ec4ffdd6e9adff6f002ad53a2064c9830ea6618d7b7b0278518bbb036`)
- Exact raw output: [`results/raw/C112.json`](../results/raw/C112.json)
- Positive mechanism observability: `ambiguous`
- Post-run audit: H0 directly feeds arbitrary names to changed ares_create_query, including the new .onion branch. Other changed lookup APIs remain outside H0, but no new caller protocol is introduced. The NO is semantically plausible even though it misses the phase-1 coverage label.

Exact JSON returned by GPT:

```json
{
  "case_id": "C112",
  "maintenance_needed": false,
  "confidence": 96,
  "change_types": [
    "input validation",
    "internal helper addition"
  ],
  "affected_functions": [
    "ares_create_query",
    "ares_gethostbyname",
    "file_lookup",
    "ares_search",
    "ares__is_onion_domain"
  ],
  "reason": "The commit adds a case-insensitive `.onion`/`.onion.` rejection check but does not add a public entry point, alter an API protocol, or require new initialization or configuration. The existing `ares_create_query_fuzzer` already passes an arbitrary, NUL-terminated fuzz-controlled name to `ares_create_query`, so it can exercise both the new rejection branch and the existing query-creation path. The additional checks in `ares_gethostbyname`, `file_lookup`, and `ares_search` apply the same validation policy and do not make the existing harness inadequate for the changed query-creation functionality.",
  "evidence": [
    "`ares-test-fuzz-name.c` copies all input bytes into `name`, appends `name[size] = '\\0'`, and calls `ares_create_query(name, ...)`.",
    "`ares_create_query` now calls `ares__is_onion_domain(name)` and returns `ARES_ENOTFOUND` for matching names; its signature and calling requirements are unchanged.",
    "`ares__is_onion_domain` is an internal helper declared in `ares_private.h`, not a new public fuzzing entry point.",
    "The other modified paths only add early `.onion` validation and introduce no new state, configuration, or input representation requirements."
  ],
  "recommended_action": "Keep the existing harness unchanged; optional `.onion` corpus inputs may improve branch discovery speed but are not required maintenance."
}
```

## C113: libplist

- Commit: `3aa5f6a3a663a5f2694ec6fc8cdf9744b616e15e`
- Label / prediction: Positive / **YES (TP)**
- Confidence: 99
- Exact GPT input: [`inputs/C113.txt`](../inputs/C113.txt) (`sha256:412d76efb3fa89e2cc5f7d718c66ccd9342778440345988e549b25d659cf84d8`)
- Exact raw output: [`results/raw/C113.json`](../results/raw/C113.json)
- Positive mechanism observability: `yes`
- Post-run audit: The YES answer correctly identifies the new public writers, format/options dispatch, and the parser-only behavior of both supplied harnesses.

Exact JSON returned by GPT:

```json
{
  "case_id": "C113",
  "maintenance_needed": true,
  "confidence": 99,
  "change_types": [
    "new public API entry points",
    "new output formats",
    "new configuration options",
    "attack-surface expansion"
  ],
  "affected_functions": [
    "plist_write_to_string",
    "plist_write_to_stream",
    "plist_write_to_file",
    "plist_print",
    "plist_write_to_string_default",
    "plist_write_to_string_limd",
    "plist_write_to_string_plutil"
  ],
  "reason": "The commit adds a substantial serialization surface that the existing parser-only harnesses do not invoke. The harnesses stop after plist_from_bin or plist_from_xml and plist_free, so they cannot exercise the new format dispatch, write options, output-size estimation, recursive node serialization, or stream-writing implementations.",
  "evidence": [
    "bplist_fuzzer.cc only calls plist_from_bin(data, size, &root_node) and plist_free(root_node).",
    "xplist_fuzzer.cc only calls plist_from_xml(data, size, &root_node) and plist_free(root_node).",
    "The public header adds plist_write_to_string, plist_write_to_stream, plist_write_to_file, and plist_print.",
    "The new plist_format_t introduces PLIST_FORMAT_PRINT, PLIST_FORMAT_LIMD, and PLIST_FORMAT_PLUTIL, backed by three new output-only serializer files.",
    "The new plist_write_options_t exposes PLIST_OPT_COMPACT, PLIST_OPT_PARTIAL_DATA, PLIST_OPT_NO_NEWLINE, and PLIST_OPT_INDENT, including a fuzz-controllable indentation level.",
    "plist_write_to_string dispatches among XML, JSON, OpenStep, PRINT, LIMD, and PLUTIL implementations, none of which is reached by the shown harnesses."
  ],
  "recommended_action": "Extend or add a harness that obtains a valid plist tree from fuzz input and invokes plist_write_to_string across the supported formats and fuzz-controlled option combinations, freeing returned buffers with plist_mem_free. Also exercise plist_write_to_stream with a safe temporary or memory-backed stream if practical; avoid arbitrary-path testing of plist_write_to_file."
}
```

