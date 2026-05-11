# Server build & run targets
DOCKER_REGISTRY ?= docker.io/yourname
DOCKER_TAG ?= latest

server_build_wheel:
	$(call log_build,$@...)
	@cd $(REPO_ROOT)/server && \
	if [ ! -d .venv ]; then python3 -m venv .venv; fi && \
	. .venv/bin/activate && \
	python -m pip install --upgrade pip build wheel setuptools && \
	python -m build
	$(call log_ok,Finished $@.)

server_install_dev:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 -m pip install -e server[tests]
	$(call log_ok,Finished $@.)

server_docker_build:
	$(call log_build,$@...)
	@cd $(REPO_ROOT)/server && docker build -t lotr-server:$(DOCKER_TAG) .
	$(call log_ok,Finished $@.)

server_docker_compose_up:
	$(call log_build,$@...)
	@cd $(REPO_ROOT)/server/docker && docker compose up -d --build
	$(call log_ok,Finished $@.)

server_run:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && docker run --rm -p 8000:8000 lotr-server:$(DOCKER_TAG)
	$(call log_ok,Finished $@.)

server_run_dev:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python -m server.server.cli --dev
	$(call log_ok,Finished $@.)

server_stop_compose:
	@cd $(REPO_ROOT)/server/docker && docker compose down || true

server_docker_push:
	$(call log_build,$@...)
	@docker tag lotr-server:$(DOCKER_TAG) $(DOCKER_REGISTRY)/lotr-server:$(DOCKER_TAG)
	@docker push $(DOCKER_REGISTRY)/lotr-server:$(DOCKER_TAG)
	$(call log_ok,Finished $@.)

server_test:
	$(call log_build,$@...)
	@cd $(REPO_ROOT)/server && pytest -q
	$(call log_ok,Finished $@.)

server_all: server_build_wheel server_docker_build

