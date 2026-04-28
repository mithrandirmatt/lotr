

get_wiki:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && python3 build/py/wiki/lotr_download_site.py
	$(call log_ok,Finished $@.)

get_master_list:
	$(call log_build,$@...)
# TODO
	$(call log_ok,Finished $@.)