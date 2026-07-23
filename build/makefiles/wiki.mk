

WIKI_CACHE_DIR := $(REPO_ROOT)/build/do/assets/.cache/wiki
WIKI_STAMP_TOOL := $(REPO_ROOT)/build/py/wiki/cache_stamp.py
WIKI_GATHER_STAMP := $(WIKI_CACHE_DIR)/wiki_gather_sites.stamp.json
WIKI_STAMP_CHECK_FLAGS := --verbose --trust-output-stamp --input-mode content --output-mode stat
WIKI_STAMP_UPDATE_FLAGS := --input-mode content --output-mode stat

wiki_gather_sites:
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(WIKI_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(WIKI_STAMP_TOOL) check $(WIKI_STAMP_CHECK_FLAGS) \
		--label wiki_gather_sites \
		--stamp $(WIKI_CACHE_DIR)/wiki_gather_sites.stamp.json \
		--input build/build.ini \
		--input build/py/wiki/lotr_download_site.py \
		--output build/do/assets/wiki \
		--output build/do/assets/cards \
		--output build/do/assets/starters ; then \
		echo "[INFO] Skipping wiki_gather_sites (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for wiki_gather_sites; running build step"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "wiki_gather_sites..."; \
		python3 build/py/wiki/lotr_download_site.py && \
		python3 $(WIKI_STAMP_TOOL) update $(WIKI_STAMP_UPDATE_FLAGS) \
			--label wiki_gather_sites \
			--stamp $(WIKI_CACHE_DIR)/wiki_gather_sites.stamp.json \
			--input build/build.ini \
			--input build/py/wiki/lotr_download_site.py \
			--output build/do/assets/wiki \
			--output build/do/assets/cards \
			--output build/do/assets/starters ; \
	fi
	$(call log_ok,Finished $@.)

wiki_create_lotr_database:
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(WIKI_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(WIKI_STAMP_TOOL) check $(WIKI_STAMP_CHECK_FLAGS) \
		--label wiki_create_lotr_database \
		--stamp $(WIKI_CACHE_DIR)/wiki_create_lotr_database.stamp.json \
		--input build/py/wiki/create_card_database.py \
		--input $(WIKI_GATHER_STAMP) \
		--input build/do/assets/wiki/cargo_cards.json \
		--input build/do/assets/database/xlist_database.json \
		--input build/do/assets/database/errata_database.json \
		--input build/do/assets/database/card_unique_overrides.json \
		--output build/do/assets/database/card_database.json ; then \
		echo "[INFO] Skipping wiki_create_lotr_database (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for wiki_create_lotr_database; running build step"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "wiki_create_lotr_database..."; \
		python3 build/py/wiki/create_card_database.py && \
		python3 $(WIKI_STAMP_TOOL) update $(WIKI_STAMP_UPDATE_FLAGS) \
			--label wiki_create_lotr_database \
			--stamp $(WIKI_CACHE_DIR)/wiki_create_lotr_database.stamp.json \
			--input build/py/wiki/create_card_database.py \
			--input $(WIKI_GATHER_STAMP) \
			--input build/do/assets/wiki/cargo_cards.json \
			--input build/do/assets/database/xlist_database.json \
			--input build/do/assets/database/errata_database.json \
			--input build/do/assets/database/card_unique_overrides.json \
			--output build/do/assets/database/card_database.json ; \
	fi
	$(call log_ok,Finished $@.)

wiki_create_starter_database:
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(WIKI_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(WIKI_STAMP_TOOL) check $(WIKI_STAMP_CHECK_FLAGS) \
		--label wiki_create_starter_database \
		--stamp $(WIKI_CACHE_DIR)/wiki_create_starter_database.stamp.json \
		--input build/py/wiki/create_starter_database.py \
		--input build/do/assets/wiki/Starter_Decks.html \
		--input build/do/assets/wiki/starters \
		--input build/do/assets/starters \
		--output build/do/assets/database/starter_database.json ; then \
		echo "[INFO] Skipping wiki_create_starter_database (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for wiki_create_starter_database; running build step"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "wiki_create_starter_database..."; \
		python3 build/py/wiki/create_starter_database.py && \
		python3 $(WIKI_STAMP_TOOL) update $(WIKI_STAMP_UPDATE_FLAGS) \
			--label wiki_create_starter_database \
			--stamp $(WIKI_CACHE_DIR)/wiki_create_starter_database.stamp.json \
			--input build/py/wiki/create_starter_database.py \
			--input build/do/assets/wiki/Starter_Decks.html \
			--input build/do/assets/wiki/starters \
			--input build/do/assets/starters \
			--output build/do/assets/database/starter_database.json ; \
	fi
	$(call log_ok,Finished $@.)

wiki_create_xlist_databases:
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(WIKI_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(WIKI_STAMP_TOOL) check $(WIKI_STAMP_CHECK_FLAGS) \
		--label wiki_create_xlist_databases \
		--stamp $(WIKI_CACHE_DIR)/wiki_create_xlist_databases.stamp.json \
		--input build/py/wiki/create_xlist_databases.py \
		--input build/do/assets/wiki/cargo_cards.json \
		--input build/do/assets/wiki/PC_Errata.html \
		--output build/do/assets/database/xlist_database.json \
		--output build/do/assets/database/errata_database.json ; then \
		echo "[INFO] Skipping wiki_create_xlist_databases (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for wiki_create_xlist_databases; running build step"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "wiki_create_xlist_databases..."; \
		python3 build/py/wiki/create_xlist_databases.py && \
		python3 $(WIKI_STAMP_TOOL) update $(WIKI_STAMP_UPDATE_FLAGS) \
			--label wiki_create_xlist_databases \
			--stamp $(WIKI_CACHE_DIR)/wiki_create_xlist_databases.stamp.json \
			--input build/py/wiki/create_xlist_databases.py \
			--input build/do/assets/wiki/cargo_cards.json \
			--input build/do/assets/wiki/PC_Errata.html \
			--output build/do/assets/database/xlist_database.json \
			--output build/do/assets/database/errata_database.json ; \
	fi
	$(call log_ok,Finished $@.)

wiki_process_card_images:
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(WIKI_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(WIKI_STAMP_TOOL) check $(WIKI_STAMP_CHECK_FLAGS) \
		--label wiki_process_card_images \
		--stamp $(WIKI_CACHE_DIR)/wiki_process_card_images.stamp.json \
		--input build/py/wiki/process_card_images.py \
		--input $(WIKI_GATHER_STAMP) \
		--output build/do/assets/cards/processed ; then \
		echo "[INFO] Skipping wiki_process_card_images (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for wiki_process_card_images; running build step"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "wiki_process_card_images..."; \
		python3 build/py/wiki/process_card_images.py && \
		python3 $(WIKI_STAMP_TOOL) update $(WIKI_STAMP_UPDATE_FLAGS) \
			--label wiki_process_card_images \
			--stamp $(WIKI_CACHE_DIR)/wiki_process_card_images.stamp.json \
			--input build/py/wiki/process_card_images.py \
			--input $(WIKI_GATHER_STAMP) \
			--output build/do/assets/cards/processed ; \
	fi
	$(call log_ok,Finished $@.)

wiki_parse_game_logic:
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(WIKI_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(WIKI_STAMP_TOOL) check $(WIKI_STAMP_CHECK_FLAGS) \
		--label wiki_parse_game_logic \
		--stamp $(WIKI_CACHE_DIR)/wiki_parse_game_logic.stamp.json \
		--input build/py/wiki/parse_game_logic.py \
		--input build/py/wiki/game_logic_schema.py \
		--input build/do/assets/database/card_database.json \
		--output build/do/assets/database/game_logic_database.json ; then \
		echo "[INFO] Skipping wiki_parse_game_logic (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for wiki_parse_game_logic; running build step"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "wiki_parse_game_logic..."; \
		python3 build/py/wiki/parse_game_logic.py && \
		python3 $(WIKI_STAMP_TOOL) update $(WIKI_STAMP_UPDATE_FLAGS) \
			--label wiki_parse_game_logic \
			--stamp $(WIKI_CACHE_DIR)/wiki_parse_game_logic.stamp.json \
			--input build/py/wiki/parse_game_logic.py \
			--input build/py/wiki/game_logic_schema.py \
			--input build/do/assets/database/card_database.json \
			--output build/do/assets/database/game_logic_database.json ; \
	fi
	$(call log_ok,Finished $@.)

wiki_all: wiki_gather_sites wiki_process_card_images wiki_create_xlist_databases wiki_create_lotr_database wiki_create_starter_database wiki_parse_game_logic wiki_game_asset_creation

# Cached via cache_stamp.py (stat mode -- card image tree is large, so full
# content hashing is skipped for speed): skips the rsync/copy sync when the
# processed card images and databases are unchanged since the last sync.
wiki_game_asset_creation: wiki_parse_game_logic
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(REPO_ROOT)/gotdot/assets/cards
	@mkdir -p $(REPO_ROOT)/gotdot/assets/data
	@mkdir -p $(WIKI_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(WIKI_STAMP_TOOL) check --verbose --trust-output-stamp --input-mode stat --output-mode stat \
		--label wiki_game_asset_creation \
		--stamp $(WIKI_CACHE_DIR)/wiki_game_asset_creation.stamp.json \
		--input build/do/assets/cards/processed \
		--input build/do/assets/database \
		--output gotdot/assets/cards \
		--output gotdot/assets/data ; then \
		echo "[INFO] Skipping wiki_game_asset_creation (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for wiki_game_asset_creation; syncing assets"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "wiki_game_asset_creation..."; \
		echo "Syncing card images to gotdot/assets/cards/ ..." && \
		rsync -a --delete --info=progress2 --include='*/' --include='*.png' --exclude='*' \
		    build/do/assets/cards/processed/ gotdot/assets/cards/ && \
		echo "Copying databases to gotdot/assets/data/ ..." && \
		cp build/do/assets/database/*.json gotdot/assets/data/ && \
		python3 $(WIKI_STAMP_TOOL) update --input-mode stat --output-mode stat \
			--label wiki_game_asset_creation \
			--stamp $(WIKI_CACHE_DIR)/wiki_game_asset_creation.stamp.json \
			--input build/do/assets/cards/processed \
			--input build/do/assets/database \
			--output gotdot/assets/cards \
			--output gotdot/assets/data ; \
	fi
	$(call log_ok,Finished $@.)


# Validation workflow: run parser -> generate ambiguous suggestions -> interactive review -> evaluate
VALIDATION_CLI_ARGS ?= --preview=browser

wiki_validation_logic: wiki_parse_game_logic
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/ambiguous_feedback.py
	@cd $(REPO_ROOT) && python3 build/py/wiki/review_cli.py $(VALIDATION_CLI_ARGS)
	@cd $(REPO_ROOT) && python3 build/py/wiki/evaluate_overrides.py
	$(call log_ok,Finished $@.)



