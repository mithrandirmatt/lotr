# =============================================================================
# utils.mk -- reusable color-echo helpers
#
# ANSI colors (works in bash, zsh, and most CI terminals).
# Usage from a recipe:
#   $(call log_info,  some message)
#   $(call log_error, something went wrong)
#
# Standalone test targets (call directly with make):
#   make echo_build   MSG="compiling foo"
#   make echo_debug   MSG="x = 42"
#   make echo_info    MSG="server started"
#   make echo_error   MSG="file not found"
#   make echo_warning MSG="deprecated flag"
#   make echo_ok      MSG="all tests passed"
# =============================================================================

# -- color definitions --------------------------------------------------------
_RESET   := \033[0m
_YELLOW  := \033[1;33m
_PURPLE  := \033[1;35m
_CYAN    := \033[1;36m
_RED     := \033[1;31m
_ORANGE  := \033[0;33m
_GREEN   := \033[1;32m

# -- call macros (use inside recipes) ----------------------------------------
# $(call log_build,   message)
# $(call log_debug,   message)
# $(call log_info,    message)
# $(call log_error,   message)
# $(call log_warning, message)
# $(call log_ok,      message)

log_build   = @printf "$(_YELLOW)[BUILD]   	%s$(_RESET)\n" "$(1)"
log_debug   = @printf "$(_PURPLE)[DEBUG]   	%s$(_RESET)\n" "$(1)"
log_info    = @printf "$(_CYAN)[INFO]    	%s$(_RESET)\n" "$(1)"
log_error   = @printf "$(_RED)[ERROR]   	%s$(_RESET)\n" "$(1)"
log_warning = @printf "$(_ORANGE)[WARNING] 	%s$(_RESET)\n" "$(1)"
log_ok      = @printf "$(_GREEN)[OK]     	%s$(_RESET)\n" "$(1)"

# -- standalone test targets --------------------------------------------------
# MSG variable can be set on the command line: make echo_info MSG="hello"
MSG ?= (no message)

.PHONY: echo_build echo_debug echo_info echo_error echo_warning echo_ok

echo_build:
	$(call log_build,$(MSG))

echo_debug:
	$(call log_debug,$(MSG))

echo_info:
	$(call log_info,$(MSG))

echo_error:
	$(call log_error,$(MSG))

echo_warning:
	$(call log_warning,$(MSG))

echo_ok:
	$(call log_ok,$(MSG))


