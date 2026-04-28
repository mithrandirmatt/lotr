



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

wiki_all: wiki_gather_sites wiki_create_lotr_database wiki_create_starter_database wiki_create_xlist_databases