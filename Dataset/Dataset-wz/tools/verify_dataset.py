#!/usr/bin/env python3
"""
verify_dataset.py — 数据集证据自动校验

放在 dataset/ 内部，避免根目录被清理时丢失。

用法（在 dataset/ 目录下）：
    python3 tools/verify_dataset.py
    python3 tools/verify_dataset.py --check-commits
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.dirname(HERE)
CASES = os.path.join(DATASET, "cases")

REQUIRED = ["schema", "id", "label", "need_visibility", "degradation_type",
            "introduced_by_this_change", "discovery_route", "gt_source",
            "change_origin", "canonical_repo", "event_key", "uniqueness",
            "gap", "evidence", "rationale", "verification", "urls"]

GAP_TYPES = {"api", "configuration", "input_format", "state", "lifecycle", "mix"}
VISIBILITY = {"explicit", "silent"}

n_ok = n_fail = n_warn = 0


def ok(m):
    global n_ok; n_ok += 1; print(f"  OK    {m}")


def fail(m):
    global n_fail; n_fail += 1; print(f"  FAIL  {m}")


def warn(m):
    global n_warn; n_warn += 1; print(f"  WARN  {m}")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def gap_signature(label):
    msg = "\n".join([
        label["event_key"]["harness"],
        "\n".join(label["gap"].get("lines") or []),
        "\n".join(b["kind"] for b in label["gap"]["blockers"]),
    ])
    return "sha256:" + hashlib.sha256(msg.encode()).hexdigest()


def patch_id(diff_path):
    try:
        with open(diff_path, "rb") as f:
            r = subprocess.run(["git", "patch-id", "--stable"],
                               stdin=f, capture_output=True, check=False)
        if r.returncode != 0:
            return None
        parts = r.stdout.decode().strip().split()
        return parts[0] if parts else None
    except FileNotFoundError:
        return None


def check_commit(commit_url, sha):
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/commit/", commit_url or "")
    if not m:
        return None, f"url 无法解析: {commit_url!r}"
    owner, repo = m.group(1), m.group(2)
    api = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    req = urllib.request.Request(api, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "verify-dataset"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        return d.get("sha") == sha, d.get("commit", {}).get("message", "").splitlines()[0]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return None, f"{type(e).__name__}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-commits", action="store_true")
    args = ap.parse_args()

    # 收集显隐两个子目录下所有样本（cases/explicit/ 与 cases/silent/ 各自再一层）
    dirs = []
    for vis in ("explicit", "silent"):
        vdir = os.path.join(CASES, vis)
        if os.path.isdir(vdir):
            dirs.extend(sorted(os.path.join(vis, d) for d in os.listdir(vdir)
                               if os.path.isdir(os.path.join(vdir, d))))
    dirs.sort()
    print(f"共 {len(dirs)} 条样本\n")

    index_ids = [e["id"] for e in load(os.path.join(DATASET, "index.json"))]
    sig_seen, pid_seen = {}, {}

    for d in dirs:
        p = os.path.join(CASES, d)
        print(f"=== {d} ===")

        for rel in ["case.json", "label.json", "meta.json", "NOTES.md", "input/change.diff"]:
            (ok if os.path.isfile(os.path.join(p, rel)) else fail)(f"存在 {rel}")

        objs = {}
        for name in ["label", "meta", "case"]:
            try:
                objs[name] = load(os.path.join(p, f"{name}.json"))
                ok(f"{name}.json 可解析")
            except Exception as e:
                fail(f"{name}.json 解析失败: {e}")
                objs[name] = None

        label, meta = objs["label"], objs["meta"]
        if not label:
            print()
            continue

        dir_id = os.path.basename(d).split("_")[0]
        for name in ["label", "meta", "case"]:
            o = objs.get(name)
            if o is None:
                continue
            (ok if o.get("id") == dir_id else fail)(
                f"{name}.id = {o.get('id')!r}（期望 {dir_id}）")

        missing = [f for f in REQUIRED if f not in label]
        (fail if missing else ok)(f"label 必备字段 {len(REQUIRED)} 个"
                                  + (f"，缺 {missing}" if missing else "齐全"))

        (ok if label.get("degradation_type") in GAP_TYPES else fail)(
            f"degradation_type = {label.get('degradation_type')!r}")
        (ok if label.get("need_visibility") in VISIBILITY else fail)(
            f"need_visibility = {label.get('need_visibility')!r}")

        rec = label["event_key"].get("gap_signature")
        calc = gap_signature(label)
        (ok if rec == calc else fail)("gap_signature " + ("MATCH" if rec == calc else "不符"))
        if rec != calc:
            print(f"        记录 {rec}\n        实算 {calc}")

        pid = patch_id(os.path.join(p, "input", "change.diff"))
        rec_pid = label["uniqueness"].get("patch_id")
        if pid is None:
            warn("patch_id 无法计算")
        elif pid == rec_pid:
            ok(f"patch_id MATCH ({pid[:16]}…)")
        else:
            fail(f"patch_id 不符\n        记录 {rec_pid}\n        实算 {pid}")

        if calc in sig_seen:
            fail(f"gap_signature 与 {sig_seen[calc]} 冲突")
        else:
            sig_seen[calc] = d
        if pid and pid in pid_seen:
            fail(f"patch_id 与 {pid_seen[pid]} 冲突")
        elif pid:
            pid_seen[pid] = d

        (ok if dir_id in index_ids else fail)(f"index.json 收录 {dir_id}")

        if args.check_commits:
            urls = label.get("urls") or {}
            for key in ["M", "M_parent", "H"]:
                sha = meta.get(key, "") if meta else ""
                if not re.fullmatch(r"[0-9a-f]{40}", str(sha)):
                    warn(f"{key} 非 40 位 sha，跳过")
                    continue
                exists, info = check_commit(urls.get(key, ""), sha)
                if exists is True:
                    ok(f"{key} 真实存在: {info[:66]}")
                elif exists is False:
                    fail(f"{key} 不存在: {info}")
                else:
                    warn(f"{key} 无法验证: {info}")

        print()

    print("=" * 60)
    print(f"通过 {n_ok}  失败 {n_fail}  警告 {n_warn}")

    types = {}
    for d in dirs:
        try:
            lab = load(os.path.join(CASES, d, "label.json"))
            key = (lab["degradation_type"], lab["need_visibility"])
            types.setdefault(key, []).append(lab["id"])
        except Exception:
            pass

    covered = {t for t, _ in types}
    print(f"gap 类型覆盖: {sorted(covered)}  ({len(covered)}/{len(GAP_TYPES)})")
    print("\n类型 × 可见性矩阵:")
    for t in sorted(GAP_TYPES):
        e = types.get((t, "explicit"), [])
        s = types.get((t, "silent"), [])
        mark = "OK" if e and s else ("--" if not e and not s else "缺一半")
        print(f"  {t:14} explicit={','.join(e) or '-':10} silent={','.join(s) or '-':10}  [{mark}]")
    print("=" * 60)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
