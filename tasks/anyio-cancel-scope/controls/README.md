# Incomplete fixes

Apply each patch to a fresh baseline tree with `patch -p1`.

`immediate-parent.patch` is the source change at upstream commit `a7284b73067a965aa6f037ecc703449b05f644db`. Review initially accepted its immediate-parent simplification, then found a nested-scope regression and reverted it before merge. It repairs the reported sibling hang but loses pending cancellation beyond an uncancelled immediate parent.

`ignore-child-shields.patch` includes the reference change but propagates cancellation through shielded child scopes. It repairs the sibling hang by breaking protection for genuinely shielded tasks.

`omit-shield-toggle-restart.patch` includes the reference change but omits cancellation restart when `shield` becomes false. It repairs the original report but loses cancellation at the next checkpoint inside a scope whose shield was disabled.

All three patches are deliberately incorrect controls. Their behavior is checked by the same public and private groups as the baseline and reference.
