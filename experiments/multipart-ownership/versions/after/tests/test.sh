#!/bin/bash
set -eu
umask 022
mkdir -p /logs/verifier
chmod 700 /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
python3 -I /tests/verify.py
