# Report-forgery probe

`forged-public-junit.patch` deliberately writes a passing report for the 31 visible upstream preservation cases and exits the pytest process before those tests execute. This is an evaluation-security probe, not a plausible bug fix and not a real successful preservation run.

The private checks still run in the trusted parent, which imports no candidate code. An unprivileged worker evaluates candidate APIs. The unchanged buggy parser fails 16 private cases, so the forged public report cannot earn reward 1.

Run `python validate_controls.py --include-adversarial --output /tmp/new-werkzeug-controls` to repeat the probe in Docker. Its synthetic public report entries must not be counted as actual test executions in any aggregate evaluation statistic.
