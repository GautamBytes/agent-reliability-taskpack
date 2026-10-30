#!/bin/bash
set -eu
cd /app/repo
git -c safe.directory=/app/repo apply /solution/reference.patch
