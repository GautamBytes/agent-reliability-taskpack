from datetime import datetime
import json

from study import ROOT, read
from verify_study import audit


def main():
    audit(True)
    rows = read(ROOT / "runs/summary.json")["attempts"]
    reviewed = []
    for row in sorted(rows, key=lambda value: value["id"]):
        folder = ROOT / "runs/curated" / row["id"]
        native = read(folder / "harbor-result.json")
        metrics = read(folder / "results.json")
        phase = native["agent_execution"]
        duration = (datetime.fromisoformat(phase["finished_at"].replace("Z", "+00:00")) - datetime.fromisoformat(phase["started_at"].replace("Z", "+00:00"))).total_seconds()
        failed = [case["name"] for case in metrics["cases"] if case["status"] == "failed"]
        if row["status"] == "TIMEOUT":
            interpretation = "Deadline reached with passing collected source; not an incorrect-repair result" if row["native_reward"] == 1 else "Deadline reached and collected source fails required checks"
        else:
            interpretation = "Normal completion with passing collected source" if row["native_reward"] == 1 else "Normal completion with an incorrect collected repair"
        reviewed.append({"attempt": row["id"], "native_outcome": row["status"], "exception_type": (native.get("exception_info") or {}).get("exception_type"),
                         "agent_phase_seconds": round(duration, 6), "collected_source_reward": row["native_reward"],
                         "checks": row["checks"], "failed_case_names": failed, "interpretation": interpretation})
    output = ROOT / "evidence/failure-review"
    output.mkdir(parents=True, exist_ok=True)
    (output / "outcomes.json").write_text(json.dumps({"reviewed_attempts": len(reviewed), "all_planned_attempts_retained": True, "records": reviewed}, indent=2) + "\n")
    lines = ["# Native outcomes and collected-source correctness", "",
             "Native completion and collected-source correctness are separate observations. The primary normal-completion measure was frozen before testing, while the original native verifier reward remains visible for every attempt.", "",
             "| Attempt | Native outcome | Agent phase, s | Collected checks | Interpretation |",
             "| --- | --- | ---: | ---: | --- |"]
    for row in reviewed:
        count = row["checks"]
        lines.append(f"| [{row['attempt']}](runs/curated/{row['attempt']}/harbor-result.json) | {row['native_outcome']} | {row['agent_phase_seconds']:.1f} | {count['passed']}/{count['tests_run']} | {row['interpretation']} |")
    source_failures = [row for row in reviewed if row["collected_source_reward"] != 1]
    timeouts = [row for row in reviewed if row["native_outcome"] == "TIMEOUT"]
    lines.extend(["", f"All {len(reviewed)} saved patches were independently reconstructed and replayed in clean offline verifiers. {len(source_failures)} collected repairs fail a required check. {len(timeouts)} native {'attempt' if len(timeouts) == 1 else 'attempts'} reached the solve deadline.", ""])
    if not source_failures:
        lines.extend(["There is no demonstrated reduction in collected-source functional correctness in this study. A timeout with a passing patch is not evidence of a wrong repair. It remains a nonpass under the separately specified normal-completion criterion.", ""])
    for row in source_failures:
        lines.extend([f"## {row['attempt']}", "", "The collected source fails these named behavioural cases:", ""])
        lines.extend("- `" + name + "`" for name in row["failed_case_names"])
        lines.append("")
    lines.extend(["Harbor downloads artifacts after execution and does not establish an atomic filesystem snapshot exactly at the 300-second cutoff. The collected-source metric therefore describes the source Harbor actually supplied to verification. The original exception and timestamps are preserved. No unsuccessful attempt was replaced or silently rerun.", "",
                  "Eight attempts per condition from one model family do not establish a broad difficulty ranking or statistical significance. More requirements and stronger incomplete-fix rejection demonstrate added task scope. They do not alone prove a lower model solve probability.", ""])
    (ROOT / "FAILURE_REVIEW.md").write_text("\n".join(lines))
    print(json.dumps({"reviewed_attempts": len(reviewed), "incorrect_collected_repairs": len(source_failures), "solve_timeouts": len(timeouts)}))


if __name__ == "__main__":
    main()
