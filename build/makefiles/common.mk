


# Repo root is one level above the build/ directory where make is invoked.
REPO_ROOT 	:= $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../..)
PYTHON_DIR 	:= $(REPO_ROOT)/build/py

# Workflows
GIT 		= $(PYTHON_DIR)/git.py
LOTR_WIKI 	= $(PYTHON_DIR)/lotr_wiki.py

include $(REPO_ROOT)/build/makefiles/admin.mk
include $(REPO_ROOT)/build/makefiles/agent.mk
include $(REPO_ROOT)/build/makefiles/ai.mk
include $(REPO_ROOT)/build/makefiles/godot.mk
include $(REPO_ROOT)/build/makefiles/project.mk
include $(REPO_ROOT)/build/makefiles/server.mk
include $(REPO_ROOT)/build/makefiles/utils.mk
include $(REPO_ROOT)/build/makefiles/wiki.mk

include $(REPO_ROOT)/build/agent/agent.mk