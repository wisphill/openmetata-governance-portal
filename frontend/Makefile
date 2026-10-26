NPM ?= npm
WRANGLER ?= npx --yes wrangler@4
PAGES_PROJECT ?= openmetadata-governance-portal
PAGES_BRANCH ?= main

.PHONY: install run build test verify pages-deploy

install:
	$(NPM) ci

run:
	$(NPM) run dev -- --host 0.0.0.0

build:
	$(NPM) run build

test:
	$(NPM) run test

verify: build

# Use this only from an authorized CI/manual deployment environment. The
# preferred production flow is Cloudflare Pages Git integration, which builds
# this directory automatically after a branch push.
pages-deploy: build
	test -n "$$CLOUDFLARE_API_TOKEN"
	test -n "$$CLOUDFLARE_ACCOUNT_ID"
	$(WRANGLER) pages deploy dist --project-name "$(PAGES_PROJECT)" --branch "$(PAGES_BRANCH)"
