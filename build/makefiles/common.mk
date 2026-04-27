


# Repo root is one level above the build/ directory where make is invoked.
REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../..)

include $(REPO_ROOT)/build/makefiles/agent.mk
include $(REPO_ROOT)/build/makefiles/git.mk
include $(REPO_ROOT)/build/makefiles/utils.mk