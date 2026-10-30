import html
import json
from pathlib import Path

from study import ROOT, read
from verify_study import audit


def fraction(value, total):
    return f"{value}/{total} ({100 * value / total:.0f}%)"


def main():
    verified = audit(True)
    protocol = read(ROOT / "protocol.json")
    result = read(ROOT / "runs/summary.json")
    rows = result["attempts"]
    before, after = verified["versions"]["basic"], verified["versions"]["hard"]
    normal_before = fraction(before["normal_completion_passes"], before["attempts"])
    normal_after = fraction(after["normal_completion_passes"], after["attempts"])
    functional_before = fraction(before["collected_source_passes"], before["attempts"])
    functional_after = fraction(after["collected_source_passes"], after["attempts"])
    fell = after["normal_completion_passes"] < before["normal_completion_passes"]
    observed = ("The measured pass rate fell in this small pilot. This is an observation from five attempts per version, not a broad model-difficulty estimate." if fell else
                "The measured pass rate did not fall. The added requirements reject incomplete fixes, but this pilot does not show that they make this model less likely to solve the task.")
    lines = ["# Multipart task-hardening study", "",
             "A matched pilot on two versions of one real Werkzeug repair task. Both versions start from the same pinned source. The harder version expands the explicit contract before any counted model attempt.", "",
             "![Recorded results for all ten attempts](proof/results.jpg)", "",
             "The screenshot shows saved records. The tables below link to the underlying patches, named test results and offline replays.", "",
             "## Observed results", "",
             "| Measure | Basic version | Harder version |",
             "| --- | ---: | ---: |",
             f"| Fresh native coding-agent attempts | {before['attempts']} | {after['attempts']} |",
             f"| Finished normally and passed every check | {normal_before} | {normal_after} |",
             f"| Harbor-collected source passed every check | {functional_before} | {functional_after} |",
             f"| Solve-timeout outcomes | {before['timeouts']} | {after['timeouts']} |",
             "| Required verifier cases | 36 | 100 |", "",
             observed, "",
             "Normal completion plus passing verification is the primary measure specified in the protocol before the runs. Collected-source verification is shown separately. Harbor collects artifacts after an attempt, so these are not claimed to be atomic filesystem snapshots taken exactly at the 300-second deadline.", "",
             "The model is gpt-6.1-sol through Codex 0.166.0 and native Harbor 0.25.0. Every attempt has medium reasoning, a configured 300-second solve phase, two CPUs and 1 GiB of agent memory. Each round runs one basic and one hard attempt in fresh containers, with no private feedback or candidate reuse. All ten planned attempts are retained.", "",
             "## What changed", "",
             "The basic task repairs the real 64 KiB upload bug where a trailing CR is lost. Its verifier combines 31 selected upstream preservation cases and five direct Request regression cases.", "",
             "The harder task adds byte-exact fragmented parsing through MultipartDecoder, FormDataParser and Request. It covers one-byte reads, padded delimiter lines, real EOF closure, false closing markers that must remain payload, repeated fields, empty binary parts, strict rejection and streaming progress. It has 31 upstream cases and 69 private parameter cases. Split positions and seeded partitions inside one case are subcases, not extra independent bugs.", "",
             "Both public contracts and private verifiers were frozen before the counted runs. The hard reference is a local extension of the attributed upstream work. It is not claimed to be an accepted upstream fix or complete RFC conformance.", "",
             "## Individual attempts", "",
             "| Attempt | Native outcome | Passing checks | Collected source reward | Patch | Replay |",
             "| --- | --- | ---: | ---: | --- | --- |"]
    table_rows = []
    for row in sorted(rows, key=lambda value: (value["id"].split("-")[-1], value["version"])):
        name = row["id"]
        checks = row["checks"]
        status = row["status"]
        lines.append(f"| [{name}](runs/curated/{name}/summary.json) | {status} | {checks['passed']}/{checks['tests_run']} | {row['native_reward']} | [Source changes](runs/curated/{name}/submitted.patch) | [Proof](runs/replays/{name}/replay.json) |")
        table_rows.append([name, status, f"{checks['passed']}/{checks['tests_run']}", row["native_reward"]])
    lines.extend(["", "Each attempt directory also includes original per-case results, the native Harbor result, permitted-source hashes, a tool-only trajectory and network-boundary evidence. Exact-source replays reconstruct each patch and match the native case statuses.", "",
                  "## Grader controls", "",
                  "| Fixed source | Basic | Harder |",
                  "| --- | ---: | ---: |",
                  "| Original baseline | 33/36, rejected | 56/100, rejected |",
                  "| Attributed basic reference | 36/36, accepted | 50/100, rejected |",
                  "| Previous complete task-pack reference | 36/36, accepted | 79/100, rejected |",
                  "| New hard reference | 36/36, accepted | 100/100, accepted |",
                  "| Equivalent reference emitting Data chunks up to 64 bytes | 36/36, accepted | 100/100, accepted |", "",
                  "The authoritative matrices are [basic-final](evidence/verifier-author/basic-final/summary.json), [basic old-reference confirmation](evidence/verifier-author/basic-old-complete-final/summary.json) and [hard-final](evidence/verifier-author/hard-final/summary.json). The alternate event strategy confirms the grader does not demand one internal chunking strategy for the added fragmented-input cases. All control runs have zero skips.", "",
                  "## Inspect the proof", "",
                  "- [Frozen protocol](protocol.json), including runner, replay-tool and task fingerprints.",
                  "- [Saved-evidence audit](AUDIT.json) and [machine-readable summary](runs/summary.json).",
                  "- [Basic instructions](versions/basic/instruction.md) and [harder instructions](versions/hard/instruction.md).",
                  "- [Grader coverage and pre-freeze fixes](evidence/verifier-author/README.md).",
                  "- [Reference provenance](reference-evidence/reference-author/summary.json) and [decision trail](decisions.tsv).", "",
                  "## Reproduce", "", "```sh", "python3 experiments/multipart-hardening/verify_study.py", "```", "",
                  "This audits committed records and reconstructs source patches without Docker or a model call. Python 3.11 or newer and Git are required. To rerun the actual offline grading of a saved patch, choose a new output directory:", "",
                  "```sh", "python3 experiments/multipart-hardening/replay_study.py hard-01 --output /tmp/new-hard-01-replay", "```", "",
                  "The original ten-attempt protocol is preserved. study.py refuses to overwrite existing runs. New experiments should have a new protocol and output directory, rather than changing the frozen conditions or replacing a failure.", "",
                  "## Limits", "",
                  "This is a five-attempt-per-condition pilot using one model family on a historical public repository. It is not a statistical estimate of broad model ability or proof of training-data independence. Both conditions restrict solving-time network access in the same way. The parser has a bounded public contract, not a complete MIME implementation. The existing candidate-code grading limitations are documented in the original task pack.", ""])
    (ROOT / "README.md").write_text("\n".join(lines))
    answer_observation = ("The added cases caught more incomplete repairs. This small study also recorded a lower model pass rate. " if fell else
                          "So the added cases caught more incomplete repairs, but they did not lower this model's pass rate in this small study. ")
    answer = ("The hardest task I authored was a streaming file-upload parser repair in my personal task pack, based on real Werkzeug bugs. The basic version asked the model to fix an upload losing its final byte around a 64 KiB read boundary.\n\n"
              "I expanded it to handle uploads arriving one byte at a time, boundaries split across reads, spaces and tabs after boundary markers, and closing markers at the end of input. Fake boundary markers inside a file had to stay untouched. The parser also had to reject incomplete uploads and keep processing data as it arrived. The required checks increased from 36 to 100, including 69 private cases.\n\n"
              f"I tested gpt-6.1-sol through Codex in 10 fresh runs, five per version, using Harbor and Docker. Both versions used the same starting code, medium reasoning, resource limits and a 300-second solve budget. The basic version passed {before['normal_completion_passes']} of 5 runs; the harder version passed {after['normal_completion_passes']} of 5. The pass rate went from {100*before['normal_completion_passes']/5:.0f}% to {100*after['normal_completion_passes']/5:.0f}%. There were {before['timeouts'] + after['timeouts']} timeouts.\n\n"
              + answer_observation +
              "The previous full repair passed only 79/100 of the harder checks. The new reference and an alternative implementation passed all 100.\n\n"
              "I replayed all 10 saved patches in clean offline verifiers. The repo has the frozen setup, every patch, per-test results and screenshots.\n\n"
              "https://github.com/GautamBytes/agent-reliability-taskpack/tree/main/experiments/multipart-hardening")
    assert len(answer) < 2000, len(answer)
    (ROOT / "QUESTION_8_ANSWER.txt").write_text(answer + "\n")
    headers = ["Attempt", "Native outcome", "Checks passed", "Source reward"]
    table = "<table><thead><tr>" + "".join("<th>" + value + "</th>" for value in headers) + "</tr></thead><tbody>"
    table += "".join("<tr>" + "".join("<td>" + html.escape(str(value)) + "</td>" for value in row) + "</tr>" for row in table_rows) + "</tbody></table>"
    viewer = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Matched task-hardening results</title><style>
body{font:16px/1.45 system-ui,sans-serif;background:#f6f8fb;color:#182838;margin:0}main{max-width:1100px;margin:20px auto;padding:26px 34px;background:white;border:1px solid #d4dde7;border-radius:9px}h1{font-size:28px;margin:8px 0 14px}p{margin:9px 0}table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid #e0e6ed}th{background:#eef3f8}.label{font-size:12px;color:#596a7c;font-weight:650}.note{font-size:13px;border-left:3px solid #99a9ba;padding-left:12px;color:#46586b}a{color:#095bb5}</style><main>
<div class="label">AGENT RELIABILITY TASK PACK · RECORDED MATCHED STUDY</div><h1>One task, two frozen difficulty versions</h1>"""
    viewer += f"<p><strong>Finished normally and passed:</strong> basic {normal_before} → harder {normal_after}.</p><p><strong>Collected-source verification:</strong> basic {functional_before} → harder {functional_after}.</p>"
    viewer += "<p>gpt-6.1-sol · medium reasoning · configured 300-second solve phase · 5 fresh attempts per version · same source and container limits</p>" + table
    viewer += "<p>Reference and equivalent solutions pass. The older full fix scores 79/100 on the harder contract. Every saved source patch was reconstructed and replayed offline.</p><p class='note'>A view of saved results, not a new live test run. Timeouts remain separate; Harbor-collected source is not claimed to be an atomic exact-deadline snapshot. This small same-model pilot does not estimate broad model ability.</p><p><a href='runs/summary.json'>Native results</a> · <a href='protocol.json'>Frozen protocol</a> · <a href='AUDIT.json'>Source and replay audit</a></p></main></html>\n"
    (ROOT / "results-viewer.html").write_text(viewer)
    print(json.dumps({"answer_characters": len(answer), "normal_basic": normal_before, "normal_hard": normal_after,
                      "source_basic": functional_before, "source_hard": functional_after}, indent=2))


if __name__ == "__main__":
    main()
