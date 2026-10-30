import html
import json
from collections import Counter
from datetime import datetime

from study import ROOT, read
from verify_study import audit


def percentage(passes, attempts):
    return f"{100 * passes / attempts:g}%"


def main():
    verified = audit(True)
    protocol = read(ROOT / "protocol.json")
    result = read(ROOT / "runs/summary.json")
    before = verified["versions"]["before"]
    after = verified["versions"]["after"]
    total = verified["counted_native_agent_attempts"]
    size_before = len(protocol["expected_case_names"]["before"])
    size_after = len(protocol["expected_case_names"]["after"])
    rate_before = percentage(before["normal_completion_passes"], before["attempts"])
    rate_after = percentage(after["normal_completion_passes"], after["attempts"])
    source_rate_before = percentage(before["collected_source_passes"], before["attempts"])
    source_rate_after = percentage(after["collected_source_passes"], after["attempts"])
    rows = sorted(result["attempts"], key=lambda row: (row["id"].split("-")[-1], row["version"] == "after"))
    failures = Counter()
    for row in rows:
        if row["version"] == "after":
            failures.update(case["name"] for case in read(ROOT / "runs/curated" / row["id"] / "results.json")["cases"] if case["status"] == "failed")
    lines = ["# Transactional multipart upload study", "",
             "A new matched study of a cross-layer upload task. The earlier [100-check hardening study](../multipart-hardening/README.md) remains preserved with its original 5/5 to 5/5 result.", "",
             "![Recorded results for every planned attempt](proof/results.jpg)", "",
             "This screenshot renders saved records. Each row below links to native results, submitted source and an offline replay.", "",
             "## Observed results", "",
             "| Measure | Before | After |", "| --- | ---: | ---: |",
             f"| Fresh native attempts | {before['attempts']} | {after['attempts']} |",
             f"| Finished normally and passed all checks | {before['normal_completion_passes']}/{before['attempts']} ({rate_before}) | {after['normal_completion_passes']}/{after['attempts']} ({rate_after}) |",
             f"| Harbor-collected source passes | {before['collected_source_passes']}/{before['attempts']} | {after['collected_source_passes']}/{after['attempts']} |",
             f"| Solve timeouts | {before['timeouts']} | {after['timeouts']} |",
             f"| Required cases | {size_before} | {size_after} |", "",
             "The primary measure was specified before testing. A pass requires normal native completion and every required verifier case. Timeouts stay separate. Collected source is not claimed to be an atomic snapshot taken exactly at the solve deadline.", "",
             "Both conditions use gpt-6.1-sol through Codex 0.166.0 and native Harbor 0.25.0, medium reasoning, the same pinned Werkzeug source, a configured 300-second solve phase, two CPUs and 1 GiB of agent memory. Eight paired rounds use fresh containers with no private feedback or candidate reuse. All sixteen planned runs are retained, without automatic Harbor episode retries.", "",
             "## What makes the new task different", "",
             "![Stream ownership on success and failure](proof/ownership.svg)", "",
             "The before task repairs fragmented multipart parsing. The after task retains that entire contract and adds transactional ownership of temporary upload files across parser and Request APIs.", "",
             "The new API enforces actual per-file and aggregate field-plus-file byte limits. It ignores misleading declared part lengths, handles short writes without losing data or counting retries twice, and resets budgets on parser reuse. Failures in reading, parsing, stream creation, writing, seeking or return construction must close all owned streams while preserving the original exception. Success transfers open streams to the caller. Request.close must handle repeated file names and shared stream identities without triggering lazy parsing.", "",
             "Every policy is stated in the [public contract](CONTRACT.md) and [after instructions](versions/after/instruction.md), which were frozen before testing. This is a bounded repair and local feature task. It does not claim complete MIME conformance.", "",
             "## Source and ownership", "",
             "The source is the same pinned historical Werkzeug checkout used in the earlier task. The byte-preservation repair family retains its upstream credits. [Werkzeug PR #3101](https://github.com/pallets/werkzeug/pull/3101) supplies the real upstream resource-cleanup context. The two quota settings and stricter partial-write and ownership policies are local task extensions. They are not claimed to be accepted upstream features or newly discovered vulnerabilities.", "",
             "## Every planned attempt", "",
             "| Attempt | Native outcome | Agent phase, s | Checks passed | Collected source reward | Patch | Replay |",
             "| --- | --- | ---: | ---: | ---: | --- | --- |"]
    viewer_rows = []
    for row in rows:
        name = row["id"]
        checks = row["checks"]
        phase = read(ROOT / "runs/curated" / name / "harbor-result.json")["agent_execution"]
        elapsed = (datetime.fromisoformat(phase["finished_at"].replace("Z", "+00:00")) - datetime.fromisoformat(phase["started_at"].replace("Z", "+00:00"))).total_seconds()
        duration = f"{elapsed:.1f}"
        lines.append(f"| [{name}](runs/curated/{name}/summary.json) | {row['status']} | {duration} | {checks['passed']}/{checks['tests_run']} | {row['native_reward']} | [Patch](runs/curated/{name}/submitted.patch) | [Replay](runs/replays/{name}/replay.json) |")
        viewer_rows.append([name, row["status"], duration, f"{checks['passed']}/{checks['tests_run']}", row["native_reward"]])
    lines.extend(["", "Each native directory also contains its original named case results, actual model metadata, tool-only trajectory, source hashes and network-boundary evidence. All exact-source replays must agree with the original reward and per-case outcomes, including failures.", "",
                  "## Failed checks in the after condition", "",
                  "These counts describe failed parameter cases across attempts. They are not counts of independent bugs or model trials.", ""])
    if failures:
        lines.extend(["| Named case | Attempts failing this case |", "| --- | ---: |"])
        lines.extend(f"| `{name}` | {count} |" for name, count in failures.most_common())
    else:
        lines.append("No collected after-condition source failed a required case. Any timeout affects the normal-completion measure, while collected-source functional results remain separate.")
    lines.extend(["", "## Review the verification", "",
                  "- [Frozen protocol](protocol.json), [public pre-evaluation commit](" + read(ROOT / "evidence/publication-anchor.json")["commit_url"] + ") and [saved-evidence audit](AUDIT.json).",
                  "- [Pre-freeze control and fairness gate](evidence/prefreeze-gate.json).",
                  "- [GitHub server-timestamp anchor](evidence/public-ci-anchor.json) and [fresh Docker verification workflow](https://github.com/GautamBytes/agent-reliability-taskpack/actions/workflows/evidence-audit.yml).",
                  "- [Private verifier coverage and control results](evidence/verifier-author/README.md).",
                  "- [Reference and alternative provenance](reference-evidence/reference-author/summary.json).",
                  "- [Failure review](FAILURE_REVIEW.md) and [decision trail](decisions.tsv).", "",
                  "## Audit or replay", "", "```sh", "python3 experiments/multipart-ownership/verify_study.py", "```", "",
                  "Python 3.11 or newer and Git are required. This audits saved evidence and reconstructs every patch without a model call or Docker. GitHub Actions also checks the publication manifest and both historical studies, then executes all sixteen saved patches and twelve fixed-source controls in fresh offline Docker verifiers. It makes no model calls.", "",
                  "To execute one saved patch in a fresh offline Docker verifier, choose a new output directory:", "", "```sh",
                  "python3 experiments/multipart-ownership/replay_study.py after-01 --output /tmp/new-ownership-replay", "```", "",
                  "## Limits", "",
                  "Eight attempts per condition and one model family provide a descriptive pilot, not a broad accuracy estimate or statistical significance claim. Historical public source may have appeared in model training. Solving-time access is restricted to the model API, unlike open-internet evaluations. There is no external benchmark acceptance or commissioning. The task pack's documented candidate-code isolation limits still apply. All original studies and unsuccessful attempts remain available.", ""])
    (ROOT / "README.md").write_text("\n".join(lines))
    timeout_note = (f"There were {before['timeouts']} before and {after['timeouts']} after timeouts. Passing collected patches from timed-out runs are kept separate from normal completions. "
                    if before["timeouts"] or after["timeouts"] else "There were no timeouts. ")
    answer = ("My hardest task was a streaming upload repair in my personal Werkzeug task pack, based on real parser bugs and upstream file-cleanup work.\n\n"
              "The first version covered fragmented uploads and exact file contents. I made the next version enforce real byte limits for each file and the whole form, even when part headers gave false sizes. It also had to handle partial writes, clean up every opened temporary file after any failure, keep the original error, and leave successful uploads open for the caller. These rules had to work through the parser and Request APIs, including repeated file names and parser reuse.\n\n"
              f"I tested gpt-6.1-sol through Codex in {total} fresh Harbor/Docker runs, {before['attempts']} per version. Both used the same starting code, medium reasoning, resource limits and a 300-second solve budget. The verifier accepted {before['collected_source_passes']} of {before['attempts']} before and {after['collected_source_passes']} of {after['attempts']} after, so collected-source correctness went from {source_rate_before} to {source_rate_after}. Normal completion plus passing checks was {before['normal_completion_passes']}/{before['attempts']} to {after['normal_completion_passes']}/{after['attempts']}, or {rate_before} to {rate_after}. " + timeout_note + "\n\n"
              f"The checks grew from {size_before} to {size_after}. I checked the reference, two valid alternatives and seven incomplete fixes before freezing the tasks. I kept every attempt and replayed all {total} saved patches in clean offline verifiers, including the timed-out attempt.\n\n"
              "I published the frozen setup before testing. The repo includes every patch, individual test results, failure review and screenshots. This was a small same-model study.\n\n"
              "https://github.com/GautamBytes/agent-reliability-taskpack/tree/main/experiments/multipart-ownership")
    assert len(answer) < 2000, len(answer)
    (ROOT / "QUESTION_8_ANSWER.txt").write_text(answer + "\n")
    table = "<table><thead><tr><th>Attempt</th><th>Native outcome</th><th>Agent phase, s</th><th>Checks passed</th><th>Source reward</th></tr></thead><tbody>"
    table += "".join("<tr>" + "".join("<td>" + html.escape(str(value)) + "</td>" for value in row) + "</tr>" for row in viewer_rows) + "</tbody></table>"
    viewer = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Transactional upload study results</title><style>body{font:15px/1.4 system-ui,sans-serif;background:#f6f8fb;color:#182838;margin:0}main{max-width:1100px;margin:16px auto;padding:24px 32px;background:white;border:1px solid #d4dde7;border-radius:9px}h1{font-size:27px;margin:7px 0 12px}p{margin:8px 0}table{border-collapse:collapse;width:100%;margin:13px 0;font-size:13px}th,td{text-align:left;padding:5px 10px;border-bottom:1px solid #e0e6ed}th{background:#eef3f8}.label{font-size:12px;color:#596a7c;font-weight:650}.note{font-size:12px;border-left:3px solid #99a9ba;padding-left:12px;color:#46586b}a{color:#095bb5}</style><main><div class="label">AGENT RELIABILITY TASK PACK · RECORDED MATCHED STUDY</div><h1>Transactional streaming upload task</h1>"""
    viewer += f"<p><strong>Finished normally and passed:</strong> before {before['normal_completion_passes']}/{before['attempts']} ({rate_before}) → after {after['normal_completion_passes']}/{after['attempts']} ({rate_after}).</p>"
    viewer += f"<p><strong>Collected-source passes:</strong> before {before['collected_source_passes']}/{before['attempts']} ({percentage(before['collected_source_passes'], before['attempts'])}) → after {after['collected_source_passes']}/{after['attempts']} ({percentage(after['collected_source_passes'], after['attempts'])}).</p>"
    viewer += f"<p><strong>Solve timeouts:</strong> before {before['timeouts']}, after {after['timeouts']}.</p>"
    viewer += f"<p>gpt-6.1-sol · medium · configured 300-second solve phase · 8 fresh attempts per version · {size_before} → {size_after} required cases</p>" + table
    viewer += "<p>The after reference and two valid alternative implementations passed all 171 checks before the study. Every saved patch was reconstructed and replayed offline, including unsuccessful attempts.</p><p class='note'>A view of saved results, not a new live test run. All 16 planned attempts are retained. Timeouts are separate; collected source is not an atomic exact-deadline snapshot. One model family, eight runs per condition, no broad accuracy or external benchmark claim.</p><p><a href='runs/summary.json'>Native records</a> · <a href='protocol.json'>Frozen protocol</a> · <a href='AUDIT.json'>Source and replay audit</a></p></main></html>\n"
    (ROOT / "results-viewer.html").write_text(viewer)
    print(json.dumps({"answer_characters": len(answer), "before": rate_before, "after": rate_after, "counted_attempts": total}, indent=2))


if __name__ == "__main__":
    main()
