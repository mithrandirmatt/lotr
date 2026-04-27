WSL + Docker setup
===================

This folder contains convenience PowerShell scripts to prepare Windows 11 for
WSL2 and to create a named WSL distribution for running the Docker Engine
(the flow does not require Docker Desktop by default).

Files:

- `setup-wsl-docker.ps1` — idempotent PowerShell orchestrator to enable WSL2,
  import or create an Ubuntu 24.04 distro named `lotr-docker-service`, and
  install the Docker Engine inside that distro.

How to run
----------

1. Open PowerShell (the script will attempt to relaunch elevated if needed).
2. From the repository root run one of the following examples:

Interactive (manual):
```powershell
PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wsl-docker.ps1
```

Non-interactive / CI:
```powershell
PowerShell -ExecutionPolicy Bypass -File build/docker/setup-wsl-docker.ps1 -NoPause
```

3. If the script enables Windows features, a reboot is recommended.
4. The script installs the Docker Engine inside the Ubuntu WSL distribution.
  If systemd is available in your WSL distro the script will attempt to start
  the `docker` service. If systemd is not available the script will launch
  `dockerd` in the background; you may prefer to enable systemd for a
  persistent service experience.

Notes
-----

- If no `-TarballPath` is supplied, the script installs `Ubuntu-24.04` via
  `wsl --install Ubuntu-24.04 --no-launch` (or exports it if already present),
  caches the export to `build/docker/artifacts/ubuntu-24.04-wsl.tar`, then
  imports it as `lotr-docker-service`. Subsequent runs reuse the cached tarball.
- The `Ubuntu-24.04` distro used as source remains installed after the run.
  Remove it with `wsl --unregister Ubuntu-24.04` if not needed.
- Pass `-NoPause` for fully non-interactive runs suitable for CI.
- If you prefer a Docker alternative, consider Podman (inside WSL) or
  Podman Desktop.
