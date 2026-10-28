# Prefer npm because package-lock.json is the committed lockfile.  The Codex
# desktop runtime exposes pnpm (and its bundled Node.js) even when npm is not
# installed on the host, so discover that Node.js runtime as a fallback.
NODE ?= $(shell command -v node 2>/dev/null || { pnpm_path=$$(command -v pnpm 2>/dev/null); pnpm_dir=$$(dirname "$$pnpm_path"); [ -n "$$pnpm_path" ] && printf '%s/../../node/bin/node\n' "$$pnpm_dir"; })
NPM ?= $(shell command -v npm 2>/dev/null || command -v pnpm 2>/dev/null)
NPM_COMMAND := $(notdir $(firstword $(NPM)))
WRANGLER ?= $(shell if command -v npx >/dev/null 2>&1; then echo 'npx --yes wrangler@4'; else echo 'pnpm dlx wrangler@4'; fi)
PAGES_PROJECT ?= openmetadata-governance-portal
PAGES_BRANCH ?= main

.PHONY: install run build test verify pages-deploy

ifeq ($(strip $(NODE)),)
$(error Node.js runtime not found. Install Node.js, or install pnpm with its managed Node.js runtime.)
endif

install:
	@if [ "$(NPM_COMMAND)" = "pnpm" ]; then \
		$(NPM) install --no-frozen-lockfile --config.confirmModulesPurge=false; \
	else \
		$(NPM) ci; \
	fi

run:
	$(NODE) node_modules/vite/bin/vite.js --host 0.0.0.0

build:
	$(NODE) node_modules/typescript/bin/tsc -b
	$(NODE) node_modules/vite/bin/vite.js build

test:
	$(NODE) node_modules/vitest/vitest.mjs run

verify: build

# Use this only from an authorized CI/manual deployment environment. The
# preferred production flow is Cloudflare Pages Git integration, which builds
# this directory automatically after a branch push.
pages-deploy: build
	test -n "$$CLOUDFLARE_API_TOKEN"
	test -n "$$CLOUDFLARE_ACCOUNT_ID"
	$(WRANGLER) pages deploy dist --project-name "$(PAGES_PROJECT)" --branch "$(PAGES_BRANCH)"
