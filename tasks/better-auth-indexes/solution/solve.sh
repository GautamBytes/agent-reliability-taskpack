#!/bin/bash
set -eu
cd /app/repo
git apply /solution/reference.patch
