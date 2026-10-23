CONTAINER_ENGINE ?= docker
IMAGE ?= openmetadata-governance-portal-backend
TAG ?= dev
PYTHON ?= python3
PORT ?= 8000
ENV_FILE ?= .env

.PHONY: install build test verify run push

install:
	$(PYTHON) -m pip install -e '.[dev]'

build:
	$(CONTAINER_ENGINE) build --pull --tag "$(IMAGE):$(TAG)" .

test:
	$(PYTHON) -m pytest

verify: test build

run:
	test -f "$(ENV_FILE)"
	$(CONTAINER_ENGINE) run --rm --env-file "$(ENV_FILE)" --publish "$(PORT):8000" "$(IMAGE):$(TAG)"

push:
	$(CONTAINER_ENGINE) push "$(IMAGE):$(TAG)"
