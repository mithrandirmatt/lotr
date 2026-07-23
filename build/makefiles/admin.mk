# Admin panel build & dev targets
# All targets run inside the dev container at /workspace
ADMIN_DIR := $(REPO_ROOT)/frontend/admin-panel
ADMIN_CACHE_DIR := $(REPO_ROOT)/build/do/admin/.cache
ADMIN_STAMP_TOOL := $(REPO_ROOT)/build/py/wiki/cache_stamp.py
ADMIN_INSTALL_STAMP := $(ADMIN_CACHE_DIR)/admin_install.stamp.json
ADMIN_BUILD_STAMP := $(ADMIN_CACHE_DIR)/admin_build.stamp.json

# Cached via cache_stamp.py: skips `npm install` when package.json/
# package-lock.json are unchanged and node_modules/ is still present.
admin_install:
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(ADMIN_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(ADMIN_STAMP_TOOL) check --verbose --trust-output-stamp --input-mode content --output-mode stat \
		--label admin_install \
		--stamp $(ADMIN_INSTALL_STAMP) \
		--input frontend/admin-panel/package.json \
		--input frontend/admin-panel/package-lock.json \
		--output frontend/admin-panel/node_modules ; then \
		echo "[INFO] Skipping admin_install (dependencies unchanged)"; \
	else \
		echo "[INFO] Cache miss for admin_install; running npm install"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "admin_install..."; \
		cd frontend/admin-panel && npm install && \
		cd $(REPO_ROOT) && python3 $(ADMIN_STAMP_TOOL) update --input-mode content --output-mode stat \
			--label admin_install \
			--stamp $(ADMIN_INSTALL_STAMP) \
			--input frontend/admin-panel/package.json \
			--input frontend/admin-panel/package-lock.json \
			--output frontend/admin-panel/node_modules ; \
	fi
	$(call log_ok,Finished $@.)

admin_dev: admin_install
	$(call log_build,$@...)
	@cd $(ADMIN_DIR) && npm run dev -- --host 0.0.0.0
	$(call log_ok,Finished $@.)

# Cached via cache_stamp.py: skips `npm run build` when source/config files
# and installed dependencies are unchanged since the last successful build.
admin_build: admin_install
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(ADMIN_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(ADMIN_STAMP_TOOL) check --verbose --trust-output-stamp --input-mode content --output-mode stat \
		--label admin_build \
		--stamp $(ADMIN_BUILD_STAMP) \
		--input frontend/admin-panel/src \
		--input frontend/admin-panel/index.html \
		--input frontend/admin-panel/vite.config.ts \
		--input frontend/admin-panel/tsconfig.json \
		--input $(ADMIN_INSTALL_STAMP) \
		--output frontend/admin-panel/dist ; then \
		echo "[INFO] Skipping admin_build (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for admin_build; running npm run build"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "admin_build..."; \
		cd frontend/admin-panel && npm run build && \
		cd $(REPO_ROOT) && python3 $(ADMIN_STAMP_TOOL) update --input-mode content --output-mode stat \
			--label admin_build \
			--stamp $(ADMIN_BUILD_STAMP) \
			--input frontend/admin-panel/src \
			--input frontend/admin-panel/index.html \
			--input frontend/admin-panel/vite.config.ts \
			--input frontend/admin-panel/tsconfig.json \
			--input $(ADMIN_INSTALL_STAMP) \
			--output frontend/admin-panel/dist ; \
	fi
	$(call log_ok,Finished $@.)

admin_preview: admin_build
	$(call log_build,$@...)
	@cd $(ADMIN_DIR) && npm run preview -- --host 0.0.0.0
	$(call log_ok,Finished $@.)

