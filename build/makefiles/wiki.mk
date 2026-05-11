



wiki_gather_sites:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/lotr_download_site.py
	$(call log_ok,Finished $@.)

wiki_create_lotr_database:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/create_card_database.py
	$(call log_ok,Finished $@.)

wiki_create_starter_database:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/create_starter_database.py
	$(call log_ok,Finished $@.)

wiki_create_xlist_databases:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/create_xlist_databases.py
	$(call log_ok,Finished $@.)

wiki_process_card_images:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/process_card_images.py
	$(call log_ok,Finished $@.)

wiki_parse_game_logic:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/parse_game_logic.py
	$(call log_ok,Finished $@.)

wiki_all: wiki_gather_sites wiki_process_card_images wiki_create_xlist_databases wiki_create_lotr_database wiki_create_starter_database wiki_parse_game_logic wiki_game_asset_creation

wiki_game_asset_creation: wiki_parse_game_logic
	$(call log_build,$@...)

	@mkdir -p $(REPO_ROOT)/gotdot/assets/cards
	@mkdir -p $(REPO_ROOT)/gotdot/assets/

	$(call log_info,Syncing card images to gotdot/assets/cards/ ...)

	@rsync -a --delete --info=progress2 --include='*/' --include='*.png' --exclude='*' \
	    $(REPO_ROOT)/build/do/assets/cards/processed/ \
	    $(REPO_ROOT)/gotdot/assets/cards/

	$(call log_info,Copying databases to gotdot/assets/data/ ...)
	@cp $(REPO_ROOT)/build/do/assets/database/*.json    $(REPO_ROOT)/gotdot/assets/data/

	$(call log_ok,Finished $@.)


# Validation workflow: run parser -> generate ambiguous suggestions -> interactive review -> evaluate
VALIDATION_CLI_ARGS ?= --preview=browser

wiki_validation_logic: wiki_parse_game_logic
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/ambiguous_feedback.py
	@cd $(REPO_ROOT) && python3 build/py/wiki/review_cli.py $(VALIDATION_CLI_ARGS)
	@cd $(REPO_ROOT) && python3 build/py/wiki/evaluate_overrides.py
	$(call log_ok,Finished $@.)



