FROM node:24.11.1-bookworm-slim@sha256:48abc13a19400ca3985071e287bd405a1d99306770eb81d61202fb6b65cf0b57 AS node
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
RUN apt-get update && apt-get install -y --no-install-recommends curl git ca-certificates ripgrep build-essential && rm -rf /var/lib/apt/lists/*
RUN npm install --global @openai/codex@0.166.0 pnpm@11.1.1
RUN useradd --uid 1000 --create-home agent && mkdir -p /app/repo && chown -R agent:agent /app
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/repo
WORKDIR /app/repo
COPY repo/ /app/repo/
RUN pnpm --filter 'better-auth...' --filter @better-auth/root install --frozen-lockfile --ignore-scripts
COPY public/ /opt/task-public/
RUN python3 /opt/task-public/prepare.py && (id -u agent >/dev/null 2>&1 || useradd --uid 1000 --create-home agent) && chown -R 1000:1000 /app/repo
USER agent
COPY network_probe.py /opt/network_probe.py
