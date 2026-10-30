#!/bin/bash
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
if python3 -I -c 'from pathlib import Path; assert Path("/app/repo/result.txt").read_bytes()==b"HARNESS_OK\n"'; then
    printf '1\n' > /logs/verifier/reward.txt
fi
