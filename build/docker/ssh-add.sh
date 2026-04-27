#!/usr/bin/env bash
# ssh-add.sh -- start ssh-agent and load the SSH key into it.
#
# Steps:
#   1. Always start a new ssh-agent session.
#   2. Convert /root/.ssh/id_rsa.ppk -> /tmp/id_openssh (only if not already done).
#   3. Always add /tmp/id_openssh to the agent.
#
# Sourced by the 'sa' alias -- do NOT use set -e here or it will affect the
# calling interactive shell and cause it to exit on any non-zero command.

PPK_SRC="/root/.ssh/id_rsa.ppk"
OPENSSH_KEY="/root/.ssh_keys/id_openssh"

# 1. Start agent
eval "$(ssh-agent -s)"

# 2. Convert ppk -> OpenSSH only if the converted key doesn't exist yet.
#    --new-passphrase /dev/null writes the output key unencrypted so
#    ssh-add below needs no passphrase -- one password prompt total.
if [ ! -f "$OPENSSH_KEY" ]; then
    echo "[sa] Converting PuTTY key to OpenSSH format..."
    puttygen "$PPK_SRC" -O private-openssh -o "$OPENSSH_KEY" --new-passphrase /dev/null
    chmod 600 "$OPENSSH_KEY"
fi

# 3. Add key to agent
ssh-add "$OPENSSH_KEY"
