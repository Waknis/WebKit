#!/usr/bin/env python3
"""Print a readable summary of one or more run-webkit-tests results directories.

Usage: summarize-layout-test-results.py LABEL=RESULTS_DIR[:LOG_FILE] ...

For each directory, prints the summary lines from the run-webkit-tests log and every
test listed in full_results.json (run-webkit-tests lists only tests that did not pass
as expected), with its -diff.txt. If a 'baseline' and a 'regressions' entry are both
given, also prints which failures are new relative to the baseline. The same text is
appended to $GITHUB_STEP_SUMMARY when that is set.
"""

import json
import os
import sys


def load_full_results(results_dir):
    path = os.path.join(results_dir, "full_results.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        text = f.read()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return None
    return json.loads(text[start:end + 1])


def leaves(node, prefix=""):
    for key, value in sorted(node.items()):
        name = prefix + "/" + key if prefix else key
        if isinstance(value, dict) and isinstance(value.get("actual"), str):
            yield name, value
        elif isinstance(value, dict):
            yield from leaves(value, name)


def log_summary(log_path):
    if not log_path or not os.path.exists(log_path):
        return []
    with open(log_path, errors="replace") as f:
        lines = [line.rstrip("\n") for line in f if "Path does not exist" not in line]
    # The tail of a run-webkit-tests log is its summary.
    keep = []
    for line in lines:
        if line.startswith("Found ") or line.startswith("Running ") or "failed unexpectedly" in line or "crashed" in line or "timed out" in line:
            keep.append(line)
    tail_start = max(0, len(lines) - 25)
    for line in lines[tail_start:]:
        if line and line not in keep and not line.startswith("Results are available"):
            keep.append(line)
    return keep


def main(argv):
    out = []
    failures_by_label = {}
    for spec in argv:
        label, _, rest = spec.partition("=")
        results_dir, _, log_path = rest.partition(":")
        out.append("")
        out.append("=" * 100)
        out.append(f"{label}: {results_dir}")
        out.append("=" * 100)
        for line in log_summary(log_path):
            out.append(line)
        results = load_full_results(results_dir)
        if results is None:
            out.append("(no full_results.json)")
            failures_by_label[label] = None
            continue
        out.append("")
        out.append("num_passes={} num_regressions={} num_flaky={} skipped={} interrupted={}".format(
            results.get("num_passes"), results.get("num_regressions"), results.get("num_flaky"),
            results.get("skipped"), results.get("interrupted")))
        failed = {}
        for name, entry in leaves(results.get("tests", {})):
            failed[name] = entry
            out.append("")
            out.append("--- {}  expected={} actual={} report={}".format(
                name, entry.get("expected"), entry.get("actual"), entry.get("report", "-")))
            base = os.path.join(results_dir, os.path.splitext(name)[0])
            for suffix in ("-diff.txt", "-stderr.txt", "-crash-log.txt"):
                path = base + suffix
                if os.path.exists(path):
                    with open(path, errors="replace") as f:
                        content = f.read().splitlines()
                    out.append(f"    [{os.path.basename(path)}]")
                    for line in content[:80]:
                        out.append("    " + line)
                    if len(content) > 80:
                        out.append(f"    ... ({len(content) - 80} more lines)")
        if not failed:
            out.append("No unexpected results.")
        failures_by_label[label] = failed

    baseline = failures_by_label.get("baseline")
    regressions = failures_by_label.get("regressions")
    if baseline is not None and regressions is not None:
        out.append("")
        out.append("=" * 100)
        out.append("regressions vs. baseline (unmodified prebuilt Web Inspector)")
        out.append("=" * 100)
        new = sorted(set(regressions) - set(baseline))
        fixed = sorted(set(baseline) - set(regressions))
        same = sorted(set(regressions) & set(baseline))
        out.append("Not passing with the fix but passing on the baseline: " + (", ".join(new) if new else "none"))
        out.append("Not passing on the baseline but passing with the fix: " + (", ".join(fixed) if fixed else "none"))
        out.append("Not passing on both: " + (", ".join(same) if same else "none"))

    text = "\n".join(out)
    print(text)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write("```\n" + text + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
