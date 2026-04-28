

get_wiki:
	$(call log_build,Generating flattened agent profiles...)
	cd $(REPO_ROOT) && python3 build/py/wiki/lotr_download_site.py
	$(call log_ok,Agent profiles ready in .github/agents/generated/)

get_master_list:
	$(call log_build,Downloading wiki pages...)
	cd $(REPO_ROOT) && python3 build/py/wiki/lotr_download_site.py
	$(call log_ok,Wiki pages downloaded and saved in assets/wiki/)