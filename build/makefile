
include ./makefiles/common.mk


clean:
	$(call log_build,** Calling $@... **)

	@find $(REPO_ROOT)/build/do/ -mindepth 1 -maxdepth 1 ! -name 'assets' -exec rm -rf {} +

	$(call log_ok,Finished $@.)
all:
	$(call log_build,** Calling $@... **)



	$(call log_ok,Finished $@.)