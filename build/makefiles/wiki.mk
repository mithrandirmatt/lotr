



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

wiki_all: wiki_gather_sites wiki_process_card_images wiki_create_xlist_databases wiki_create_lotr_database wiki_create_starter_database