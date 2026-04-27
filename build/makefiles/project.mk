


project_update:
	$(call log_build,** Calling $@... **)

	$(MAKE) agent_update

	$(call log_ok,Finished $@.)

project_commit:
	$(call log_build,** Calling $@... **)
	cd $(REPO_ROOT) && python3 build/py/project.py commit_project
	$(call log_ok,Finished $@.)