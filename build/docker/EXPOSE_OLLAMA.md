Exposing Ollama to containers

This project can optionally use a local Ollama instance running on the host (Windows/WSL).
The Docker helper scripts now add a host mapping and default environment variables so containers
can reach Ollama as `http://host.docker.internal:11434`.

How it works

- `build/docker/docker.ps1` injects the following into both the MCP and dev container runs:
  - `--add-host=host.docker.internal:host-gateway`
  - `-e OLLAMA_URL` and `-e OLLAMA_ORIGINS` (script will auto-detect the best value unless you already set `OLLAMA_URL` or `OLLAMA_ORIGINS`)

Auto-detection behavior

- If an `ollama` container is found running in `lotr-docker-service` attached to `lotr-net`, the script will set `OLLAMA_URL=http://ollama:11434` so containers use the service by name.
- Otherwise the script tests `http://host.docker.internal:11434` from within the WSL distro and will use that if reachable.
- You can still override by setting `OLLAMA_URL` or `OLLAMA_ORIGINS` in your host environment before running `docker.ps1`.

Quick usage

- Start Ollama on the Windows host (default HTTP port 11434).
- Ensure Ollama allows origins if required (set `OLLAMA_ORIGINS` in your user/system env and restart Ollama):
  - Windows PowerShell:
    ```powershell
    [System.Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS","*","User")
    ```
  - Linux/macOS:
    ```bash
    export OLLAMA_ORIGINS='*'
    ```
- Run the dev environment as usual:
  ```powershell
  PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run -NoPause
  ```

Notes & alternatives

- If your Docker engine does not support `host-gateway`, you can instead determine the host gateway IP inside the container with `ip route` and call Ollama using that IP.
- Alternatively, run Ollama itself as a Docker container attached to the `lotr-net` network and set `OLLAMA_URL=http://ollama:11434` for containers.
 - Alternatively, run Ollama itself as a Docker container attached to the `lotr-net` network and set `OLLAMA_URL=http://ollama:11434` for containers. The script will detect this case automatically if the container is running.
- Exposing host services to containers reduces isolation — avoid enabling `OLLAMA_ORIGINS='*'` on shared machines.
