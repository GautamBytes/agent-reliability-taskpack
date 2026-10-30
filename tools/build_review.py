import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAMES = {"anyio-cancel-scope": "AnyIO", "better-auth-indexes": "Better Auth", "werkzeug-multipart": "Werkzeug"}


def read(name):
    return json.loads((ROOT / name).read_text())


def table(headers, rows):
    head = "".join("<th>" + html.escape(str(value)) + "</th>" for value in headers)
    body = "".join("<tr>" + "".join("<td>" + html.escape(str(value)) + "</td>" for value in row) + "</tr>" for row in rows)
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table>"


def page(name, title, content, sources):
    links = " · ".join('<a href="../../' + html.escape(path, quote=True) + '">' + html.escape(label) + "</a>" for label, path in sources)
    source = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + html.escape(title) + """</title><style>
body{font:16px/1.5 system-ui,sans-serif;margin:0;background:#f6f7f9;color:#17202a}
main{max-width:1100px;margin:24px auto;background:white;padding:30px 36px;border:1px solid #d8dee5;border-radius:10px}
h1{font-size:30px;line-height:1.2;margin:12px 0 18px}h2{font-size:19px;margin:20px 0 8px}
p{margin:10px 0}table{width:100%;border-collapse:collapse;margin:16px 0;font-size:15px}th{text-align:left;background:#f1f4f8}
th,td{padding:11px 12px;border-bottom:1px solid #dfe4ea;vertical-align:top}a{color:#095bb5}
.label{font-size:13px;font-weight:650;color:#526174}.note{border-left:3px solid #8b98a6;padding-left:14px;font-size:14px;color:#394957}
.sources{font-size:13px;margin-top:22px;border-top:1px solid #dfe4ea;padding-top:14px;overflow-wrap:anywhere}
</style><main><div class="label">AGENT RELIABILITY TASK PACK · SAVED RESULT VIEWER · 30 OCTOBER 2026</div><h1>""" + html.escape(title) + "</h1>" + content + '<p class="note">This page renders recorded local results. This screenshot is not a new test run. The linked JSON, logs and patches are the underlying evidence.</p><div class="sources">Sources: ' + links + '</div></main></html>\n'
    target = ROOT / "docs" / "proof" / (name + ".html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)


def main():
    audit = read("evidence/release-audit.json")
    trials = read("evidence/trial-summary.json")["trials"]
    rows = []
    for task, label in NAMES.items():
        baseline, reference = audit["baseline_results"][task], audit["reference_results"][task]
        rows.append([label, f"{baseline['passed']} passed / {baseline['failed']} failed", f"{reference['passed']} passed / {reference['failed']} failed", reference["skipped"]])
    page("controls", "Original bugs fail. Reference fixes pass.",
         table(["Task", "Original source", "Reference fix", "Known nonpasses"], rows) +
         "<h2>Additional fix controls</h2><p>All 10 incomplete fixes are rejected. All 3 valid alternatives are accepted.</p><p>All 313 required reference checks pass. Reports contain 317 entries because AnyIO retains 2 Python-version skips and 2 upstream xfails.</p><p>The original-source and reference columns come from native Harbor runs. Other fix controls use the same pinned verifier runtime.</p>",
         [("Release audit", "evidence/release-audit.json"), ("AnyIO controls", "evidence/final-anyio-controls/summary.json"), ("Better Auth controls", "tasks/better-auth-indexes/evidence/release-semantic-matrix/summary.json"), ("Werkzeug controls", "tasks/werkzeug-multipart/evidence/docker-adversarial-controls/summary.json")])
    rows = []
    for trial in trials:
        before, after = trial["original_checks"], trial["checks"]
        rows.append([NAMES[trial["task"]], trial["profile"], str(trial["agent_timeout_seconds"]) + "s", f"{before['passed']}/{before['tests_run']}", f"{after['passed']}/{after['tests_run']}", "Timed out; saved patch passes" if trial["budget_exhausted"] else "Finished"])
    page("trials", "Six fresh native coding-agent attempts",
         "<p>Codex 0.166.0 · gpt-6.1-sol · Harbor 0.25.0 · medium/300s and high/600s profiles</p>" +
         table(["Task", "Profile", "Deadline", "Original", "Final", "Run outcome"], rows) +
         "<p>5 attempts finished normally. 1 hit its solve deadline. All 6 saved patches pass the final checks and were replayed from their exact source changes.</p><p class='note'>Better Auth's original 80/83 and 82/83 results rejected valid schema syntax. The verifier was corrected after the attempts. Original scores, unchanged patches and the timeout are preserved. AnyIO's 4 known nonpasses are allowlisted.</p>",
         [("Trial summary", "evidence/trial-summary.json"), ("Grading correction", "FAIRNESS_REVISION.json"), ("Submitted patches and logs", "evidence/trials"), ("Exact-source replays", "evidence/replays")])
    audit_rows = [["Required checks in reference solutions", audit["required_passes"]], ["Original-project preservation checks", audit["required_upstream_preservation"]], ["Authored behavioural holdout checks", audit["authored_behavioral_holdouts"]], ["Focused TypeScript compile check", audit["focused_compile_checks"]], ["Incomplete fixes rejected / valid alternatives accepted", "10 / 3"], ["Exact-source patch replays / infrastructure failures", "6 / 0"], ["Pinned baseline source files byte-checked", sum(audit["byte_verified_baseline_files"].values())]]
    page("audit", "Saved evidence audit passed",
         "<p>All evidence-audit gates passed. Recorded audit time: " + html.escape(audit["audited_at"]) + "</p>" +
         table(["What was checked", "Recorded result"], audit_rows) +
         "<p>Each trial records blocked GitHub retrieval and blocked direct internet access. Verification runs offline. The source, patches, per-case results and network records are included.</p><p class='note'>This is a personal AI-assisted project with three historical public tasks and one model family. It has no external benchmark acceptance. The GitHub check audits saved evidence; it does not rerun the coding agents.</p>",
         [("Release audit", "evidence/release-audit.json"), ("Audit program", "tools/report.py"), ("Source credits", "SOURCES.md"), ("Scope and limits", "VERIFICATION.md")])
    markdown = ["# Review without running", "", "This is a personal task-pack project built with AI assistance. The recorded tests were hidden from the coding agents. Their source is public now for review.", "", "## Start with these records", "", "1. [Reference and original-source results](evidence/release-audit.json) show all 313 required reference checks passing, while all three original versions fail.", "2. [Six agent attempts](TRIALS.md) show original scores, final scores and the one solve timeout.", "3. [Grading corrections](FAIRNESS_REVISION.json) explain why valid schema syntax originally failed. The saved patches stayed unchanged.", "4. [Source credits](SOURCES.md) link each task to real issues and upstream fixes.", "", "## Screenshots of the saved results", "", "These are actual browser captures of the [generated result viewer](tools/build_review.py). They render the linked saved JSON. They do not depict new live agent runs.", "", "![Original and reference results](docs/proof/controls.jpg)", "", "![Six native coding attempts](docs/proof/trials.jpg)", "", "![Evidence audit](docs/proof/audit.jpg)", "", "## Every incomplete and alternative fix", "", "| Task | Variant | Passed / reported | Expected reward | Actual reward |", "| --- | --- | ---: | ---: | ---: |"]
    matrices = [("AnyIO", "evidence/final-anyio-controls/summary.json", "variants"), ("Better Auth", "tasks/better-auth-indexes/evidence/release-semantic-matrix/summary.json", "runs"), ("Werkzeug", "tasks/werkzeug-multipart/evidence/docker-adversarial-controls/summary.json", "variants")]
    for label, path, key in matrices:
        for row in read(path)[key]:
            markdown.append(f"| {label} | [{row['variant']}]({path}) | {row['passed']}/{row['tests_run']} | {row['expected_reward']} | {row['reward']} |")
    markdown.extend(["", "AnyIO has four known upstream nonpasses. Werkzeug's forged-public-report control manufactures public records and still fails private assertions. It is a tampering probe, not an additional set of executed public tests.", "", "## Inspect an agent's actual work", "", "| Attempt | Source patch | Original per-case results | Final replay | Tool calls and results |", "| --- | --- | --- | --- | --- |"])
    for trial in trials:
        name = trial["id"]
        markdown.append(f"| {name} | [Patch](evidence/trials/{name}/submitted.patch) | [Results](evidence/trials/{name}/results.json) | [Replay](evidence/replays/{name}/replay.json) | [Trace](evidence/trials/{name}/trajectory.json) |")
    markdown.extend(["", "The two Better Auth attempts also have `corrected-results.json` beside their original results. The 300-second timeout is retained in the Harbor result. Tool trajectories omit raw reasoning text.", "", "## Scope", "", "Live database checks use SQLite. Drizzle output executes against builder metadata. Other database engines and Prisma receive schema/SQL representation checks. This uses one model family at two budgets and three historical public tasks. It does not establish broad model difficulty or absence of training-data overlap. See [VERIFICATION.md](VERIFICATION.md) for the full limits.", ""])
    (ROOT / "REVIEW.md").write_text("\n".join(markdown))


if __name__ == "__main__":
    main()
