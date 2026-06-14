# lotr

Lord Of the Rings TCG project focused on training and optimizing Mixture-of-Experts (MoE) models for high-performance inference on AMD hardware (e.g., 7900XTX).

## Core Technologies
- **Base Model**: LLaMA 3 8B
- **Quantization**: 4-bit quantization using `llama.cpp`
- **Hardware Target**: AMD Radeon RX 7900XTX
- **Build System**: Makefile-based automation (`agent.mk`)

## Project Structure
- `build/`: Build scripts, including training, quantization, and optimization workflows.
- `frontend/`: Admin panel and UI components.
- `gotdot/`: Godot engine integration for game logic and assets.
- `lotr/`: Core server implementation.
- `ml-project/`: Machine learning pipelines and evaluations.
- `server/`: Python-based backend services.
- `tools/`: Utility scripts for repository management and RAG queries.

## Development Workflow
All development work must be performed within the provided Docker container to ensure environment consistency across Linux and Windows hosts.

## Dev Container Commands

Use these commands from the workspace root on the host.

Build the main dev container for AMD ROCm (7900 XTX):

```powershell
./build/docker/docker.ps1 build -GpuVariant rocm
```

Open the main dev container interactively:

```powershell
./build/docker/docker.ps1 run -GpuVariant rocm
```

Run a one-off command in the main dev container without restarting the app services:

```powershell
./build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile agent_build" -GpuVariant rocm
```

Run a one-off command in the main dev container while also starting the normal workspace services:

```powershell
./build/docker/docker.ps1 run -CommandArg "cd /workspace/build && make -f makefile agent_build"
```

Recommended agent recipe for this workspace:

```powershell
./build/docker/docker.ps1 exec "cd /workspace && <command>" -GpuVariant rocm
```

Examples:

```powershell
./build/docker/docker.ps1 exec "cd /workspace/server && pytest"
./build/docker/docker.ps1 exec "cd /workspace/frontend/admin-panel && npm test"
./build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile agentic_build"
```
