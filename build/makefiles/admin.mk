# Admin panel build & dev targets
# All targets run inside the dev container at /workspace
ADMIN_DIR := $(REPO_ROOT)/frontend/admin-panel

admin_install:
	$(call log_build,$@...)
	@cd $(ADMIN_DIR) && npm install
	$(call log_ok,Finished $@.)

admin_dev: admin_install
	$(call log_build,$@...)
	@cd $(ADMIN_DIR) && npm run dev -- --host 0.0.0.0
	$(call log_ok,Finished $@.)

admin_build: admin_install
	$(call log_build,$@...)
	@cd $(ADMIN_DIR) && npm run build
	$(call log_ok,Finished $@.)

admin_preview: admin_build
	$(call log_build,$@...)
	@cd $(ADMIN_DIR) && npm run preview -- --host 0.0.0.0
	$(call log_ok,Finished $@.)
