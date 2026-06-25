% Docker Integration Specification

Date: 2026-04-24

## Overview

Goal: a single PowerShell command creates a WSL2 distro named `lotr-docker-service`
running Ubuntu 24.04 with Docker Engine installed, defaulting to `root`, without
any interactive prompts.

No Docker Desktop. No MS Store interactive provisioning. No renaming from an
existing distro. The distro is created from scratch every time it is needed.

Sections:
- WSL Install -- enable required Windows features
- Ubuntu Install -- download Ubuntu 24.04 WSL rootfs and import as lotr-docker-service
- Docker Setup -- install Docker Engine inside the distro
- Scripts and Usage -- exact commands, parameters, invocation examples
- Logging and Acceptance Criteria

---

## WSL Install

Purpose: ensure the Windows host is WSL2-ready.

Host WSL configuration:
- `setup-wsl-docker.ps1` invokes `build/docker/setup-wslconfig.ps1` automatically
  in forced non-interactive mode to apply recommended host `.wslconfig` values
  (including `vmIdleTimeout` and auto-detected resource caps).
- Use `-SkipWslConfig` to bypass this behavior.

Rules:
- Run elevated (admin). The orchestrator re-launches with UAC if needed; exit non-zero
  if elevation is declined.
- Enable Windows features `Microsoft-Windows-Subsystem-Linux` and `VirtualMachinePlatform`
  if not already enabled (no reboot forced by script; operator reboots if prompted).
- Run `wsl --update` best-effort (skip if unsupported).

---

## Ubuntu Install

Purpose: create the `lotr-docker-service` WSL2 distro from an Ubuntu 24.04 rootfs.

Method: `wsl --import` (non-interactive, no interactive username/password prompts).

Steps performed by `ensure-lotr-distro.ps1`:
1. Abort with exit code 2 if `lotr-docker-service` already exists.
   Operator removes it with: `wsl --unregister lotr-docker-service`
2. Obtain the Ubuntu 24.04 WSL rootfs tarball:
   a. If `-TarballPath` is supplied, use it directly.
   b. If a cached tarball exists at `build/docker/artifacts/ubuntu-24.04-wsl.tar`, use it.
   c. Otherwise obtain a fresh Ubuntu 24.04 rootfs by:
      i.  If `Ubuntu-24.04` distro is already installed: export it to the cache.
      ii. Otherwise: run `wsl --install Ubuntu-24.04 --no-launch` (downloads from
          the WSL/MS Store, does not open a terminal or prompt for a username),
          then export it to the cache.
      The exported tarball is cached at `build/docker/artifacts/ubuntu-24.04-wsl.tar`.
3. Import: `wsl --import lotr-docker-service <InstallPath> <tarball> --version 2`
4. Write `/etc/wsl.conf` inside the distro to set `default=root`.
5. Compute SHA256 of tarball and record in `build/docker/artifacts/manifest.json`.

Note: if `wsl --install Ubuntu-24.04` is run by the script, the `Ubuntu-24.04` distro
will remain on the system after the import; unregister it if not needed:
  `wsl --unregister Ubuntu-24.04`

Parameters of `ensure-lotr-distro.ps1`:
- `-TarballPath`  (optional) path to a local Ubuntu 24.04 WSL rootfs `.tar` (skip install+export)
- `-InstallPath`  (default `C:\wsl\lotr-docker-service`) where WSL stores the distro VHD
- `-DistroName`   (default `lotr-docker-service`)
- `-ManifestPath` (default `build\docker\artifacts\manifest.json`)

---

## Docker Setup

Purpose: install Docker Engine inside `lotr-docker-service` as `root`, non-interactively.

Steps performed by `setup-wsl-docker.ps1` after the distro exists:
1. Write install script to a temp file (UTF-8 no BOM, LF-only line endings).
2. Transfer into WSL via `/mnt/` path: `wsl -d lotr-docker-service -u root -- cp /mnt/<drive>/<temp-path> /tmp/install.sh`
3. Syntax check: `wsl -d lotr-docker-service -u root -- bash -n /tmp/install.sh`
4. Execute: `wsl -d lotr-docker-service -u root -- bash /tmp/install.sh`

Install script steps (bash, inside distro):
- `export DEBIAN_FRONTEND=noninteractive`
- `apt-get update && apt-get install -y ca-certificates curl gnupg lsb-release`
- Add Docker apt keyring to `/etc/apt/keyrings/docker.gpg`
- Add Docker apt repo to `/etc/apt/sources.list.d/docker.list`
- `apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin`
- Write `/usr/local/bin/lotr-start-docker.sh` (start wrapper used when systemd absent)
- Start Docker: use `systemctl enable --now docker` if systemd present, else wrapper

Start wrapper (`/usr/local/bin/lotr-start-docker.sh`):
- Check PID 1 comm: `[ "$(cat /proc/1/comm)" = "systemd" ]` — NOT `systemctl --version`
  (the binary exists even without systemd running, so `--version` always exits 0).
- If systemd: `systemctl enable --now docker`
- Else: `nohup dockerd > /var/log/dockerd.log 2>&1 &` and write PID to `/var/run/dockerd.pid`

WSL2 persistence note (non-systemd path):
WSL2 terminates the distro when the last session exits, killing all background processes
including dockerd. The correct approach is to launch dockerd from a persistent Windows-side
process via `Start-Process` so the WSL session stays open after the start script returns:
  `Start-Process wsl -ArgumentList @("-d", "<distro>", "-u", "root", "--", "dockerd", "--host", "unix:///var/run/docker.sock") -WindowStyle Hidden`

Security note: Docker listens only on the UNIX socket `/var/run/docker.sock`; no TCP
socket is opened.

Verification (run by orchestrator after install):
- `wsl -d lotr-docker-service -u root -- docker version`
- `wsl -d lotr-docker-service -u root -- docker info`
- `wsl -d lotr-docker-service -u root -- cat /etc/wsl.conf`

---

## Scripts and Usage

Scripts (all in `build/docker/`):
```
PowerShell -ExecutionPolicy Bypass -File build/docker/ensure-lotr-distro.ps1                    # download/import Ubuntu 24.04, write wsl.conf, record manifest
PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wsl-docker.ps1                      # orchestrator: WSL features + ensure-lotr-distro + Docker install + ROCm install + verify
PowerShell -ExecutionPolicy Bypass -File build/docker/start-wsl-docker.ps1                      # start Docker inside lotr-docker-service
PowerShell -ExecutionPolicy Bypass -File build/docker/stop-wsl-docker.ps1                       # stop Docker inside lotr-docker-service
PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build                          # build the lotr-dev image from build/docker/Dockerfile
PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run                            # run interactive shell in the lotr-dev container (direct host Ollama by default)
PowerShell -ExecutionPolicy Bypass -File build/docker/trouble-shoot.ps1                         # Script to troubleshoot our setups
PowerShell -ExecutionPolicy Bypass -File build/docker/check-ollama-endpoints.ps1                # Script to check ollama server
PowerShell -ExecutionPolicy Bypass -File build/docker/ollama-latency-test.ps1 -Iterations 5     # Script to check ai lag
PowerShell -ExecutionPolicy Bypass -File build/docker/llm-checker.ps1                            # Script to verify llm path, context override, and endpoint health
```

Parameters of `setup-wsl-docker.ps1`:
- `-TarballPath`         (optional) passed through to ensure-lotr-distro.ps1
- `-InstallPath`         (default `C:\wsl\lotr-docker-service`)
- `-DistroName`          (default `lotr-docker-service`)
- `-ManifestPath`        (default `build\docker\artifacts\manifest.json`)
- `-NoPause`             (switch) skip end-of-run keypress; required for CI/automation
- `-RocmMetaPackage`     (default `amdrocm7.12-gfx950`) AMD ROCm apt meta-package to install
- `-AmdGPURepoVersion`   (default `30.30`) AMDGPU repository version
- `-SkipRocm`            (switch) skip ROCm installation (Docker-only install)
- `-SkipWslConfig`       (switch) skip automatic host `.wslconfig` tuning

Invocation:
```
# Interactive -- re-launches elevated, pauses at end for operator to read output:
PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wsl-docker.ps1

# CI / non-interactive:
PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wsl-docker.ps1 -NoPause

# With a pre-downloaded tarball:
PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wsl-docker.ps1 -TarballPath .\ubuntu-24.04-wsl.tar.gz

# Start / stop Docker:
PowerShell -ExecutionPolicy Bypass -File build/docker/start-wsl-docker.ps1 [-NoPause]
PowerShell -ExecutionPolicy Bypass -File build/docker/stop-wsl-docker.ps1  [-NoPause]
```

---

## Logging and Acceptance Criteria

Logging:
- All scripts append timestamped lines to `build/docker/logs/<script-name>.log`.
- Artifact manifest written to `build/docker/artifacts/manifest.json` with fields:
  `distro`, `tarball`, `sha256`, `created_at`.

Idempotency:
- If `lotr-docker-service` already exists, `setup-wsl-docker.ps1` exits 2 with
  instructions to unregister.
- Downloaded rootfs is cached at a fixed path; re-runs reuse the cache.

Acceptance criteria (happy path for `setup-wsl-docker.ps1`):
1. `lotr-docker-service` appears in `wsl -l -v` as WSL2.
2. `wsl -d lotr-docker-service -u root -- docker version` exits 0.
3. `wsl -d lotr-docker-service -u root -- cat /etc/wsl.conf` contains `default=root`.
4. Entire flow completes without any interactive prompts.

Exit codes:
- 0  success
- 2  target distro already exists
- 3  wsl --install Ubuntu-24.04 failed and no -TarballPath or cache supplied
- 5  tarball file not found
- 6  wsl --import failed

