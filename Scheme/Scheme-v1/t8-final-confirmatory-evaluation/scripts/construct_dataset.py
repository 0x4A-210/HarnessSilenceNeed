#!/usr/bin/env python3
"""Construct the pre-prediction Task-8 audit set from new commit identities.

The selection below is frozen by commit prefix before any Task-8 prediction is
run.  Positive cases require a real co-committed developer H1.  For negative
controls H1 is explicitly the no-change harness (H1 == H0), because the audited
maintenance decision is NO; no synthetic post-hoc harness is invented.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

from common import ROOT, REPOS, SPLITS, git, is_harness, is_production, sha256_file, utc_now, write_csv, write_json


# project, prefix, label, subtype, exact target, scope type, semantic scope,
# relevant H0 path suffix (blank means the co-evolved harness files).
SPECS = [
    # libarchive: genuine developer additions to test_fuzz's reference corpus.
    ("libarchive", "e58ec44597f9", "POSITIVE", "P3", "archive_read_support_format_7zip", "FORMAT_SUBSYSTEM", "7-Zip reader: COPY/Deflate/BZip2/LZMA/BCJ/Delta variants", ""),
    ("libarchive", "06e7b8231bfe", "POSITIVE", "P3", "decompress", "FORMAT_SUBSYSTEM", "7-Zip BCJ2 decoding", ""),
    ("libarchive", "3e7782c0de10", "POSITIVE", "P3", "cab_read_ahead_cfdata_lzx", "FORMAT_SUBSYSTEM", "CAB LZX decoder", ""),
    ("libarchive", "20732adb5b93", "POSITIVE", "P2", "archive_read_format_rar_read_data", "FORMAT_SUBSYSTEM", "RAR normal-compression and multi-LZSS-block decoding", ""),
    ("libarchive", "d483c48adade", "POSITIVE", "P2", "read_data_compressed", "FORMAT_SUBSYSTEM", "RAR PPMd-to-LZSS conversion", ""),
    ("libarchive", "4d2655110533", "POSITIVE", "P3", "decompress", "FORMAT_SUBSYSTEM", "7-Zip BCJ plus LZMA1 decoding", ""),
    ("libarchive", "d81916d0044e", "POSITIVE", "P3", "read_data_compressed", "FORMAT_SUBSYSTEM", "RAR good/best PPMd compression", ""),
    ("libarchive", "344711d5afb2", "POSITIVE", "P3", "archive_read_support_format_lha", "FORMAT_SUBSYSTEM", "LHA/LZH reader", ""),
    ("libarchive", "099075c11ce9", "POSITIVE", "P3", "archive_read_support_format_rar", "FORMAT_SUBSYSTEM", "initial RARv3 reader", ""),
    ("libarchive", "416694915449", "POSITIVE", "P2", "archive_read_format_rar_read_header", "FORMAT_SUBSYSTEM", "multi-volume RAR reader", ""),
    ("libarchive", "7b543b13d813", "POSITIVE", "P3", "archive_read_open_filenames", "API_PROTOCOL", "multi-data-object archive input API and callback lifecycle", ""),
    # The old name remains behind ARCHIVE_VERSION_NUMBER < 4000000, so the
    # frozen pre-change harness remains source-compatible at this revision.
    ("libarchive", "9890b31ffd24", "OTHER_NEGATIVE", "N2", "archive_read_free", "API_RENAME", "archive read finalization API rename with retained compatibility alias", ""),

    # libxml2: developer H1 changes add new engines, APIs, failure injection, or configuration.
    ("libxml2", "6c128fd58a0e", "POSITIVE", "P4", "xmlXIncludeProcessFlags", "STATE_CONFIG", "XInclude processing after XML/HTML parsing", ""),
    ("libxml2", "30d839776aae", "POSITIVE", "P4", "xmlCatalogSetDefaults", "STATE_CONFIG", "catalog initialization and external-catalog policy", ""),
    ("libxml2", "ee0c1f87c098", "POSITIVE", "P3", "LLVMFuzzerTestOneInput", "API_SUBSYSTEM", "tree API virtual-machine fuzzer", ""),
    ("libxml2", "f19a95108a32", "POSITIVE", "P4", "xmlErrMemory", "STATE_CONFIG", "parser allocation-failure reporting and injected OOM state", ""),
    ("libxml2", "da996c8d0f9f", "POSITIVE", "P4", "xmlParseURISafe", "STATE_CONFIG", "URI APIs under allocation-failure injection", ""),
    ("libxml2", "3f05508a53c2", "POSITIVE", "P2", "xmlNodeSetLang", "API_SUBSYSTEM", "tree attribute setters under allocation failure", ""),
    ("libxml2", "e632d9f02eab", "POSITIVE", "P4", "xmlXPathContextSetCache", "STATE_CONFIG", "XPath/XPointer cache and evaluation under OOM", ""),
    ("libxml2", "abd74186f972", "POSITIVE", "P4", "htmlCtxtReadMemory", "STATE_CONFIG", "HTML parser and serializer under allocation failure", ""),
    ("libxml2", "54c70ed57fbd", "POSITIVE", "P1", "xmlCtxtErrMemory", "API_RENAME", "parser-context memory-error API rename", ""),
    ("libxml2", "8af55c8d2071", "POSITIVE", "P1", "xmlNewInputFromMemory", "API_RENAME", "parser input API rename", ""),
    ("libxml2", "bfe6af2eed38", "POSITIVE", "P1", "xmllintMain", "BUILD_PROTOCOL", "xmllint fuzzer build boundary after lintmain split", ""),
    ("libxml2", "f96dca9c0e63", "POSITIVE", "P4", "xmlFuzzResourceLoader", "STATE_CONFIG", "xmllint resource-loader interception and external-resource state", ""),

    # simdjson: new dedicated fuzzers/branches plus API compatibility updates.
    ("simdjson", "0b39e3a6cfe9", "POSITIVE", "P3", "padded_string", "API_SUBSYSTEM", "padded_string constructors, loads, moves, and copies", ""),
    ("simdjson", "f1b4a54991b0", "POSITIVE", "P3", "element::tie", "API_SUBSYSTEM", "DOM element type/accessor and JSON Pointer operations", ""),
    ("simdjson", "9865bb69040a", "POSITIVE", "P4", "supported_by_runtime_system", "STATE_CONFIG", "runtime implementation capability filtering", ""),
    ("simdjson", "bddb23177e0c", "POSITIVE", "P3", "get_bigint", "API_SUBSYSTEM", "opt-in DOM BIGINT tape representation", ""),
    ("simdjson", "85001c55fb67", "OTHER_NEGATIVE", "N2", "validate_utf8", "ARCHITECTURE_SUBSYSTEM", "PPC64 UTF-8 validation already exercised by the existing entry point", "fuzz/fuzz_utf8.cpp"),
    ("simdjson", "94c429aa70d2", "POSITIVE", "P3", "parser::iterate_many", "API_PROTOCOL", "DOM and On-Demand streaming/document-stream API", ""),
    ("simdjson", "8ae818e17cf9", "POSITIVE", "P3", "parser::parse", "ENTRY_POINT", "initial OSS-Fuzz JSON parser entry point", ""),
    ("simdjson", "2a714f4e37fb", "POSITIVE", "P1", "value_unsafe", "API_RENAME", "simdjson_result access after removal of std::pair inheritance", ""),
    ("simdjson", "c6f9c93c33b4", "POSITIVE", "P1", "get_active_implementation", "API_RENAME", "runtime implementation globals converted to accessors", ""),
    ("simdjson", "8a8eea53a265", "POSITIVE", "P1", "SIMDJSON_UNUSED", "MACRO_RENAME", "public macro namespace prefixing", ""),
    ("simdjson", "a7fc7d4ffb66", "POSITIVE", "P1", "simdjson_result::get", "API_RENAME", "DOM result extraction protocol change", ""),

    # Solidity: generator state additions and compile-time API moves.
    ("solidity", "6b4ee52513d6", "POSITIVE", "P4", "EVMVersion::osaka", "STATE_CONFIG", "Osaka EVM-version generator state", ""),
    ("solidity", "8c1b4c983dbc", "POSITIVE", "P4", "EVMVersion::amsterdam", "STATE_CONFIG", "Amsterdam EVM-version generator state", ""),
    ("solidity", "a48b743e2465", "POSITIVE", "P4", "hasSlotNum", "STATE_CONFIG", "SLOTNUM opcode gated by EVM version", ""),
    ("solidity", "8407c8c615c3", "POSITIVE", "P4", "formatErrorInformation", "STATE_CONFIG", "source-reference formatter option combinations", ""),
    ("solidity", "cafa01cbf602", "POSITIVE", "P1", "suffixedVariableNameList", "API_RENAME", "SuffixHelper move to StringUtils namespace", ""),
    ("solidity", "3e7c68d9b09b", "POSITIVE", "P1", "contractIdentifiers", "API_RENAME", "compiler identifier-query API merge", ""),

    # h2o is a seen-project addition with new commits not used in development.
    ("h2o", "bc387c9660be", "POSITIVE", "P1", "h2o_qpack_flatten_request", "API_PROTOCOL", "QPACK request API gains the RFC 9298 :protocol argument", ""),
    ("h2o", "a1609928a2e6", "POSITIVE", "P1", "h2o_socketpool_create_target", "API_PROTOCOL", "socket-pool target constructor gains an explicit origin argument", ""),
    ("h2o", "22d186ca9bd3", "POSITIVE", "P1", "h2o_qpack_flatten_request", "API_PROTOCOL", "QPACK flatten API gains a caller-owned statistics accumulator", ""),
    ("h2o", "ca72d787e158", "POSITIVE", "P1", "h2o_socketpool_target_conf_t", "API_RENAME", "socket-pool target configuration inheritance", ""),
    ("h2o", "b235819d2681", "POSITIVE", "P1", "h2o_timer_t", "API_RENAME", "removal of h2o_timer_val", ""),
    ("h2o", "7999ee87437e", "POSITIVE", "P1", "h2o_timer_wheel_t", "API_RENAME", "timeout/timer API rename", ""),

    # N4 controls: target/subsystem was omitted by H0 in both snapshots; the
    # commit is an internal correction/refactor with no new harness control.
    ("c-ares", "c4764c2f28a9", "N4", "N4", "fake_hostent", "FUNCTION", "gethostbyname AF_UNSPEC lifecycle", "test/ares-test-fuzz-name.c"),
    ("c-ares", "2614afc55338", "N4", "N4", "ares_addr_equal", "FUNCTION", "cookie address comparison", "test/ares-test-fuzz.c"),
    ("c-ares", "2c1a20bbc43a", "N4", "N4", "ares_destroy", "FUNCTION", "channel destruction and config-monitor locking", "test/ares-test-fuzz.c"),
    ("c-ares", "42ddbc14ec00", "N4", "N4", "ares_rc4_generate_key", "FUNCTION", "random-state key generation", "test/ares-test-fuzz.c"),
    ("libplist", "d45396aad911", "N4", "N4", "plist_array_append_item", "API_SUBSYSTEM", "array/dictionary mutation APIs", "fuzz/bplist_fuzzer.cc"),
    ("libplist", "be567b3ac81c", "N4", "N4", "write_real", "FUNCTION", "binary-plist real/date writer", "fuzz/bplist_fuzzer.cc"),
    ("libplist", "e64fbba33a3c", "N4", "N4", "parse_arguments", "FUNCTION", "plistutil command-line parser", "fuzz/xplist_fuzzer.cc"),
    ("libspng", "c615712a82f1", "N4", "N4", "spng_encode_image", "API_SUBSYSTEM", "interlaced PNG encoder", "tests/spng_read_fuzzer.c"),
    ("libspng", "371a2f01ca5", "N4", "N4", "spng_encode_image", "API_SUBSYSTEM", "PNG encoder state machine", "tests/spng_read_fuzzer.c"),
    ("libspng", "8bc0cd7e8fb2", "N4", "N4", "spng_encode_image", "API_SUBSYSTEM", "PNG encoder state machine", "tests/spng_read_fuzzer.c"),
    ("meshoptimizer", "8954694c043c", "N4", "N4", "meshopt_remesh", "API_SUBSYSTEM", "remesher debug vertex placement", "tools/simplifyfuzz.cpp"),
    ("meshoptimizer", "4d0f34782d42", "N4", "N4", "meshopt_remesh", "API_SUBSYSTEM", "remesher triangle-capacity accounting", "tools/simplifyfuzz.cpp"),
    ("meshoptimizer", "ed23742e6c93", "N4", "N4", "rasterizeOpacityRec", "API_SUBSYSTEM", "opacity-map fixed-point sampling", "tools/clusterfuzz.cpp"),
    ("selinux", "ad198ecc37e5", "N4", "N4", "semanage_list_sort", "FUNCTION", "libsemanage list sorting", "libsepol/fuzz/secilc-fuzzer.c"),
    ("selinux", "ecdc170115f9", "N4", "N4", "security_compute_user_raw", "FUNCTION", "libselinux user-computation API", "libsepol/fuzz/secilc-fuzzer.c"),
    ("libarchive", "cac4cf6ded6d", "N4", "N4", "copy_file_data_block", "FUNCTION", "bsdtar data-read error reporting", "contrib/oss-fuzz/libarchive_fuzzer.cc"),
    ("libarchive", "ef959767db90", "N4", "N4", "mode_pass", "FUNCTION", "bsdcpio pass mode owner parsing", "contrib/oss-fuzz/libarchive_fuzzer.cc"),
    ("libarchive", "0da2e229b1c0", "N4", "N4", "list_item_verbose", "FUNCTION", "bsdtar time formatting", "contrib/oss-fuzz/libarchive_fuzzer.cc"),
    ("libxml2", "c63248941708", "N4", "N4", "xmlCatalogXMLResolve", "API_SUBSYSTEM", "XML catalog resolution", "fuzz/xml.c"),
    ("libxml2", "0fd00ec5f510", "N4", "N4", "xmlC14NProcessAttrsAxis", "API_SUBSYSTEM", "canonicalization attribute axis", "fuzz/xml.c"),
    ("libxml2", "28da8549a051", "N4", "N4", "xmlSchematronParseRule", "API_SUBSYSTEM", "Schematron rule parsing", "fuzz/schema.c"),
    ("simdjson", "769528b6c055", "N4", "N4", "auto_parser", "API_SUBSYSTEM", "C++ object conversion auto-parser", "fuzz/fuzz_parser.cpp"),
    ("simdjson", "bde288a6237e", "N4", "N4", "string_builder::operator std::string", "API_SUBSYSTEM", "On-Demand JSON string builder", "fuzz/fuzz_parser.cpp"),
    ("solidity", "49e295d3169e", "N4", "N4", "SMTEncoder::endVisit", "API_SUBSYSTEM", "SMT encoding of unary constant operands", "test/tools/ossfuzz/solc_ossfuzz.cpp"),
    ("solidity", "51be5c338dfa", "N4", "N4", "CommandLineParser::processArgs", "API_SUBSYSTEM", "CLI optimizer-runs option parsing", "test/tools/ossfuzz/solc_ossfuzz.cpp"),

    # Other negatives: changed behavior is already exercised by the selected H0
    # entry or the change is non-semantic/does not create a fuzzing obligation.
    ("c-ares", "0ad09d251bf0", "OTHER_NEGATIVE", "N2", "ares_dns_parse_buf", "FUNCTION", "DNS packet-size guard", "test/ares-test-fuzz.c"),
    ("c-ares", "40fb125849ee", "OTHER_NEGATIVE", "N2", "ares_dns_parse_rr_uri", "FUNCTION", "URI resource-record parser", "test/ares-test-fuzz.c"),
    ("c-ares", "fb43c04bae76", "OTHER_NEGATIVE", "N6", "ares_dns_parse_rr_tlsa", "API_SUBSYSTEM", "TLSA resource-record parse/write", "test/ares-test-fuzz.c"),
    ("c-ares", "df1cbdccf748", "OTHER_NEGATIVE", "N6", "ares_dns_parse_rr_opt", "API_SUBSYSTEM", "OPT key/value option parse/write", "test/ares-test-fuzz.c"),
    ("libplist", "31a353b57152", "OTHER_NEGATIVE", "N2", "plist_from_json", "FUNCTION", "JSON plist token initialization", "fuzz/jplist_fuzzer.cc"),
    ("libplist", "79f58e9355e9", "OTHER_NEGATIVE", "N2", "node_from_openstep", "FUNCTION", "OpenStep plist bounds checks", "fuzz/oplist_fuzzer.cc"),
    ("libplist", "9969b8ebeb2d", "OTHER_NEGATIVE", "N2", "parse_bin_node_at_index", "FUNCTION", "binary-plist offset arithmetic", "fuzz/bplist_fuzzer.cc"),
    ("libplist", "ac7b64160f5c", "OTHER_NEGATIVE", "N2", "unescape_entities", "FUNCTION", "XML plist entity unescaping", "fuzz/xplist_fuzzer.cc"),
    ("libplist", "292994b09fcf", "OTHER_NEGATIVE", "N2", "parse_real_node", "FUNCTION", "binary-plist unaligned numeric reads", "fuzz/bplist_fuzzer.cc"),
    ("libspng", "99657966b6d0", "OTHER_NEGATIVE", "N2", "spng_decode_image", "API_SUBSYSTEM", "PNG decode cleanup on final scanline", "tests/spng_read_fuzzer.cc"),
    ("libspng", "466a080234e3", "OTHER_NEGATIVE", "N2", "spng_decode_image", "API_SUBSYSTEM", "interlaced PNG output-width calculation", "tests/spng_read_fuzzer.cc"),
    ("libspng", "5ce9a01928fa", "OTHER_NEGATIVE", "N2", "spng_decode_image", "API_SUBSYSTEM", "PNG decoder error cleanup", "tests/spng_read_fuzzer.cc"),
    ("libspng", "6bef42c45d44", "OTHER_NEGATIVE", "N2", "spng_decoded_image_size", "FUNCTION", "decoded image-size calculation", "tests/spng_read_fuzzer.cc"),
    ("libspng", "dc9b7ddee427", "OTHER_NEGATIVE", "N2", "spng_decode_image", "API_SUBSYSTEM", "PNG row-filter validation", "tests/spng_read_fuzzer.cc"),
    ("meshoptimizer", "0c42448e1217", "OTHER_NEGATIVE", "N2", "meshopt_encodeVertexBufferBound", "FUNCTION", "vertex encoder bound estimate", "tools/codecfuzz.cpp"),
    ("meshoptimizer", "4e59ade48c36", "OTHER_NEGATIVE", "N2", "meshopt_simplify", "API_SUBSYSTEM", "simplifier wedge remapping", "tools/simplifyfuzz.cpp"),
    ("meshoptimizer", "77e485dd2723", "OTHER_NEGATIVE", "N2", "meshopt_decodeVertexBuffer", "API_SUBSYSTEM", "SSE vertex delta decoding", "tools/codecfuzz.cpp"),
    ("meshoptimizer", "adacfb0fa382", "OTHER_NEGATIVE", "N2", "encodeVertexBlock", "FUNCTION", "vertex bit-group palette encoding", "tools/codecfuzz.cpp"),
    ("meshoptimizer", "da13ccf958f4", "OTHER_NEGATIVE", "N1", "meshopt_decodeIndexSequence", "API_SUBSYSTEM", "stability annotation only for codec APIs", "tools/codecfuzz.cpp"),
    ("selinux", "9541097ed796", "OTHER_NEGATIVE", "N2", "module_compiler", "FUNCTION", "checkpolicy flavor precedence", "checkpolicy/fuzz/checkpolicy-fuzzer.c"),
    ("selinux", "64c49eb31cdf", "OTHER_NEGATIVE", "N2", "cil_add_file", "FUNCTION", "CIL file-size truncation guard", "libsepol/fuzz/secilc-fuzzer.c"),
    ("selinux", "fb255b9ea927", "OTHER_NEGATIVE", "N2", "define_genfs_context_helper", "FUNCTION", "checkpolicy error-path ownership", "checkpolicy/fuzz/checkpolicy-fuzzer.c"),
    ("selinux", "54fc5a5328a5", "OTHER_NEGATIVE", "N2", "define_te_avtab_xperms_helper", "FUNCTION", "xperm complement boundaries", "checkpolicy/fuzz/checkpolicy-fuzzer.c"),
    ("selinux", "394b6d0836ab", "OTHER_NEGATIVE", "N2", "cil_binary_create_allocated_pdb", "FUNCTION", "CIL borrowed datum error path", "libsepol/fuzz/secilc-fuzzer.c"),
    ("libarchive", "20da2c1c877c", "OTHER_NEGATIVE", "N2", "lzx_huffman_init", "FUNCTION", "CAB LZX Huffman table initialization", "contrib/oss-fuzz/libarchive_cab_fuzzer.cc"),
    ("libxml2", "b9da8bcc7854", "OTHER_NEGATIVE", "N2", "xmlURIEscapeStr", "FUNCTION", "URI escaping length guard", "fuzz/uri.c"),
    ("simdjson", "f9c973a359ea", "OTHER_NEGATIVE", "N2", "element::at_path", "API_SUBSYSTEM", "DOM JSONPath error propagation", "fuzz/fuzz_atpointer.cpp"),
    ("simdjson", "20b28712ffce", "OTHER_NEGATIVE", "N2", "parse_unpadded", "PARSER_SUBSYSTEM", "truncated nested JSON bounds handling", "fuzz/fuzz_parser.cpp"),
    ("solidity", "208e62ae44b7", "OTHER_NEGATIVE", "N2", "LValue::setToZero", "API_SUBSYSTEM", "memory byte-array delete code generation", "test/tools/ossfuzz/solc_ossfuzz.cpp"),
    ("solidity", "12692b3975d2", "OTHER_NEGATIVE", "N2", "StackLimitEvader::run", "API_SUBSYSTEM", "Yul optimizer stack-slot relocation", "test/tools/ossfuzz/strictasm_opt_ossfuzz.cpp"),
    ("h2o", "f761722d2385", "OTHER_NEGATIVE", "N1", "h2o_qpack_parse_request", "PROTOCOL_SUBSYSTEM", "format-only QPACK/HTTP3 edit", "fuzz/h3_header_generator.c"),
    ("h2o", "e9942f8ce69f", "OTHER_NEGATIVE", "N1", "h2o_process_request", "HTTP_SUBSYSTEM", "format-only HTTP core edit", "fuzz/driver.cc"),
]


def resolve(prefix: str, project: str, universe: list[dict[str, str]]) -> dict[str, str]:
    matches = [row for row in universe if row["project"] == project and row["commit"].startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"{project}:{prefix} resolved to {len(matches)} universe rows")
    row = matches[0]
    if row["prior_case_excluded"] != "False":
        raise RuntimeError(f"selected prior identity: {project}:{row['commit']}")
    return row


def tree_harnesses(project: str, rev: str) -> list[str]:
    return [path for path in git(project, "ls-tree", "-r", "--name-only", rev).stdout.splitlines() if is_harness(path)]


def select_harnesses(project: str, rev: str, hint: str, changed: str) -> list[str]:
    available = tree_harnesses(project, rev)
    wanted = [path for path in changed.split(";") if path] if not hint else []
    if hint:
        exact = [path for path in available if path == hint]
        suffix = [path for path in available if path.endswith(hint)]
        wanted = exact or suffix
    selected = sorted(set(path for path in wanted if path in available))
    if not selected and changed and not hint:
        # A newly added dedicated target has no same-path H0.  In that case H0
        # is the complete pre-existing harness family in the same source tree.
        roots = {path.split("/", 1)[0] for path in changed.split(";") if "/" in path}
        selected = sorted(path for path in available if path.split("/", 1)[0] in roots)
        if not selected:
            selected = sorted(available)
    return selected


def show(project: str, rev: str, path: str) -> str:
    result = git(project, "show", f"{rev}:{path}", check=False)
    return result.stdout if result.returncode == 0 else ""


def occurrences(text: str, target: str) -> int:
    leaf = target.split("::")[-1].split()[-1]
    return len(re.findall(r"(?<![A-Za-z0-9_])" + re.escape(leaf) + r"(?![A-Za-z0-9_])", text))


def main() -> None:
    with (ROOT / "mining" / "candidate_universe.csv").open(newline="", encoding="utf-8") as handle:
        universe = list(csv.DictReader(handle))
    if len(SPECS) != 104:
        raise RuntimeError(f"expected 104 frozen selections, found {len(SPECS)}")
    if len({(p, c) for p, c, *_ in SPECS}) != len(SPECS):
        raise RuntimeError("duplicate selection")

    cases: list[dict] = []
    labels: list[dict] = []
    scopes: list[dict] = []
    evidence: list[dict] = []
    snapshots: list[dict] = []
    audit_dir = ROOT / "ground-truth" / "audit-sheets"
    source_dir = ROOT / "ground-truth" / "case-evidence"
    audit_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    for index, spec in enumerate(SPECS, 1):
        project, prefix, label, subtype, target, scope_type, scope, hint = spec
        row = resolve(prefix, project, universe)
        case_id = f"T8{index:03d}"
        commit, parent = row["commit"], row["parent"]
        changed_harnesses = row["harness_paths_changed"]
        h0_paths = select_harnesses(project, parent, hint, changed_harnesses)
        if label == "POSITIVE":
            changed_after = select_harnesses(project, commit, hint, changed_harnesses)
            current = set(tree_harnesses(project, commit))
            h1_paths = sorted((set(h0_paths) & current) | set(changed_after))
        else:
            h1_paths = h0_paths
        if not h0_paths:
            raise RuntimeError(f"{case_id} has no selected H0: {project}:{prefix}:{hint}")
        if label == "POSITIVE" and not h1_paths:
            raise RuntimeError(f"{case_id} has no real developer H1")
        production_paths = [path for path in row["production_paths"].split(";") if path]
        source_diff = git(project, "diff", "--no-ext-diff", "--no-renames", "--unified=3", parent, commit, "--", *production_paths).stdout
        harness_diff = git(project, "diff", "--no-ext-diff", "--no-renames", "--unified=3", parent, commit, "--", *[p for p in changed_harnesses.split(";") if p]).stdout if changed_harnesses else ""
        h0_text = "\n".join(show(project, parent, path) for path in h0_paths)
        h1_text = "\n".join(show(project, commit, path) for path in h1_paths) if label == "POSITIVE" else h0_text
        s0_text = "\n".join(show(project, parent, path) for path in production_paths)
        s1_text = "\n".join(show(project, commit, path) for path in production_paths)
        evidence_path = source_dir / f"{case_id}.patch"
        evidence_path.write_text(
            f"PROJECT {project}\nCOMMIT {commit}\nPARENT {parent}\nSUBJECT {row['subject']}\n\n"
            f"=== COMPLETE PRODUCTION DIFF ===\n{source_diff}\n\n=== DEVELOPER HARNESS DIFF (GT ONLY) ===\n{harness_diff}",
            encoding="utf-8",
        )
        expected_before = "EXISTING_GAP" if label == "N4" else "NO_MATERIAL_GAP"
        expected_after = "MATERIAL_GAP" if label == "POSITIVE" else expected_before
        delta = "NEW" if subtype in {"P1", "P3", "P4"} else ("AGGRAVATED" if subtype == "P2" else ("UNCHANGED" if label == "N4" else "NONE"))
        cases.append({
            "case_id": case_id, "project": project, "split": SPLITS[project], "commit": commit,
            "parent": parent, "commit_time": row["timestamp"], "subject": row["subject"],
            "candidate_class": row["candidate_class"], "production_paths": ";".join(production_paths),
            "harness_id": ";".join(h0_paths), "h0_paths": ";".join(h0_paths), "h1_paths": ";".join(h1_paths),
        })
        labels.append({
            "case_id": case_id, "project": project, "split": SPLITS[project], "label": label,
            "positive_type": subtype if label == "POSITIVE" else "",
            "negative_type": subtype if label != "POSITIVE" else "",
            "expected_gap_before": expected_before, "expected_gap_after": expected_after,
            "expected_delta": delta, "maintenance_needed": "YES" if label == "POSITIVE" else "NO",
            "exact_target": target, "audit_status": "AUDITED_PRE_FREEZE",
        })
        scopes.append({
            "case_id": case_id, "impact_scope_type": scope_type,
            "impact_scope": scope, "impact_scope_files": ";".join(production_paths),
            "impact_scope_functions": target, "impact_scope_api": target if scope_type.startswith("API") else "",
            "impact_scope_state": scope if scope_type in {"STATE_CONFIG", "PROTOCOL_SUBSYSTEM"} else "",
            "impact_scope_config": scope if scope_type == "STATE_CONFIG" else "",
            "equivalent_targets": target,
        })
        evidence.append({
            "case_id": case_id,
            "evidence_type": "REAL_DEVELOPER_H1+THREE_SNAPSHOT_SEMANTIC_AUDIT" if label == "POSITIVE" else "THREE_SNAPSHOT_SEMANTIC_AUDIT+NO_CHANGE_H1",
            "h1_provenance": f"developer tree at {commit}" if label == "POSITIVE" else "H1=H0; negative control requires no maintenance",
            "s0_target_occurrences": occurrences(s0_text, target),
            "s1_target_occurrences": occurrences(s1_text, target),
            "h0_target_occurrences": occurrences(h0_text, target),
            "h1_target_occurrences": occurrences(h1_text, target),
            "production_diff_sha256": __import__("hashlib").sha256(source_diff.encode()).hexdigest(),
            "harness_diff_sha256": __import__("hashlib").sha256(harness_diff.encode()).hexdigest(),
            "evidence_file": str(evidence_path.relative_to(ROOT)),
            "audit_rationale": ("S1 production and the co-committed developer H1 jointly add/adapt the listed fuzz obligation."
                                if label == "POSITIVE" else
                                ("The same omitted target/subsystem exists around both snapshots and the commit adds no new caller-controlled harness obligation."
                                 if label == "N4" else
                                 "The selected H0 entry already exercises the changed input path, or the edit has no semantic fuzz-harness obligation.")),
        })
        for name, source_rev, harness_rev, paths in [
            ("S0_H0", parent, parent, h0_paths), ("S1_H0", commit, parent, h0_paths),
            ("S1_H1", commit, commit if label == "POSITIVE" else parent, h1_paths),
        ]:
            blob_ids = []
            for path in paths:
                oid = git(project, "rev-parse", f"{harness_rev}:{path}", check=False).stdout.strip()
                blob_ids.append(f"{path}={oid or 'MISSING'}")
            snapshots.append({"case_id": case_id, "snapshot": name, "source_commit": source_rev,
                              "harness_commit": harness_rev, "harness_blobs": ";".join(blob_ids),
                              "construct_status": "CONSTRUCTED"})
        sheet = [
            f"# {case_id} — pre-freeze audit", "", f"- Project: `{project}`", f"- Commit: `{commit}`",
            f"- Parent: `{parent}`", f"- Split: `{SPLITS[project]}`", f"- Subject: {row['subject']}",
            f"- Draft label: `{label}` / `{subtype}`", f"- Exact target: `{target}`", f"- Impact scope: {scope}",
            f"- H0: `{';'.join(h0_paths)}`", f"- H1: `{';'.join(h1_paths)}`",
            f"- H1 provenance: {'real developer commit' if label == 'POSITIVE' else 'no-change negative control'}", "",
            "Snapshot construction is recorded in `snapshot_manifest.csv`; the complete production and GT-only harness diffs are in "
            f"`{evidence_path.relative_to(ROOT)}`.", "",
        ]
        (audit_dir / f"{case_id}.md").write_text("\n".join(sheet), encoding="utf-8")

    case_fields = list(cases[0]); label_fields = list(labels[0]); scope_fields = list(scopes[0]); evidence_fields = list(evidence[0]); snap_fields = list(snapshots[0])
    write_csv(ROOT / "ground-truth" / "cases.csv", cases, case_fields)
    write_csv(ROOT / "ground-truth" / "labels.draft.csv", labels, label_fields)
    write_csv(ROOT / "ground-truth" / "impact_scope.draft.csv", scopes, scope_fields)
    write_csv(ROOT / "ground-truth" / "evidence.draft.csv", evidence, evidence_fields)
    write_csv(ROOT / "ground-truth" / "snapshot_manifest.csv", snapshots, snap_fields)
    counts = Counter(row["label"] for row in labels)
    subtypes = Counter((row["positive_type"] or row["negative_type"]) for row in labels)
    projects = Counter(row["project"] for row in cases)
    write_json(ROOT / "ground-truth" / "construction_manifest.json", {
        "constructed_at": utc_now(), "status": "AUDIT_DRAFT_NOT_FROZEN", "case_count": len(cases),
        "label_counts": dict(counts), "taxonomy_counts": dict(subtypes), "project_counts": dict(projects),
        "max_project_share": max(projects.values()) / len(cases),
        "seen_count": sum(row["split"] == "SEEN_PROJECT" for row in cases),
        "unseen_count": sum(row["split"] == "UNSEEN_PROJECT_HOLDOUT" for row in cases),
        "all_prior_case_excluded": True, "predictions_existed_at_construction": False,
        "mining_manifest_sha256": sha256_file(ROOT / "mining" / "mining_manifest.json"),
        "cases_sha256": sha256_file(ROOT / "ground-truth" / "cases.csv"),
        "labels_draft_sha256": sha256_file(ROOT / "ground-truth" / "labels.draft.csv"),
    })
    print(json.dumps({"cases": len(cases), "labels": dict(counts), "types": dict(subtypes),
                      "projects": dict(projects)}, indent=2))


if __name__ == "__main__":
    main()
