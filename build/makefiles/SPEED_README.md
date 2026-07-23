# Make Speed Implementation Guide

## Overview

`make speed` is a full-project build orchestration target that builds all LOTR components from scratch while maximizing cache reuse across runs. It organizes the build into phases, automatically detects available processors for parallelization, and provides verification after completion.

---

## Architecture

### Phase Organization

```
┌─────────────────────────────────────────────────────────────┐
│                    make speed                                │
│              (build/makefiles/speed.mk)                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌──────────────────────────────────────────┐
        │  Phase Detection & Processor Counting     │
        │  • Auto-detect NPROCS with fallbacks      │
        │  • Windows/WSL/Docker compatibility       │
        └──────────────────────────────────────────┘
                              ↓
    ┌─────────────────────┬─────────────────────┐
    ↓                      ↓                     ↓
┌──────────┐         ┌─────────────┐     ┌─────────────┐
│ PREBUILD │         │ PARALLEL    │     │ POSTBUILD   │
│ (Phase 0)│         │ CORE        │     │ (Phase 2)   │
│ Sequential│        │ Concurrent  │     │ Verification│
└──────────┘         └─────────────┘     └─────────────┘
```

### Phase Details

| Phase | Targets | Execution Model | Purpose |
|-------|---------|-----------------|---------|
| **PREBUILD** (Phase 0) | `wiki_gather_sites`, `wiki_create_lotr_database`, `wiki_parse_game_logic` | Sequential, must complete first | Data gathering and database creation that feeds subsequent builds |
| **PARALLEL_CORE** (Phase 1) | `server_install_dev`, `admin_install`, `godot_export`, `server_docker_build` | Concurrent with NPROCS jobs | Independent builds that can run in parallel without dependencies on each other |
| **POSTBUILD** (Phase 2) | `server_test`, `wiki_game_asset_creation` | Sequential after all builds complete | Verification and final integration steps |

---

## Processor Detection Strategy

The implementation uses a cascading fallback strategy to detect available processors:

```makefile
1. nproc           # Standard Unix/Linux command
   ↓ (fails)
2. sysctl hw.ncpu  # BSD/macOS system configuration
   ↓ (fails)
3. getconf         # POSIX standard query
   ↓ (fails)
4. PowerShell      # Windows/WSL fallback via shell execution
   ↓ (fails)
5. Default to 4    # Reasonable minimum for modern systems
```

This ensures compatibility across:
- **Linux**: Standard `nproc` available in most distributions
- **macOS**: Uses `sysctl` or `getconf`
- **Windows/WSL**: Falls back to PowerShell command execution
- **Docker containers**: Works with any base image that has processor info

---

## Cache Strategy

### Cache Directories (gitignored by default)

| Directory | Purpose | Contents | Invalidation Trigger |
|-----------|---------|----------|---------------------|
| `.speed-cache/` | Speed-specific artifacts | Build metadata, timestamps | Manual clean or `make speed-clean` |
| `do/assets/.cache/` | Asset gathering cache | Downloaded site content (HTML) | Site structure changes |
| `build/docker/cache/huggingface/` | HF model shards | Model weight files | Model source updates |

### Cache Keys by Component

```bash
# Docker image build
Cache key: Image tag + base layer digest (from docker history)
Invalidation: Base OS update, new package added to Dockerfile

# npm packages
Cache key: Hash of package.json + lock file checksum
Invalidation: Any dependency change in admin-panel/

# Python venv
Cache key: Requirements hash + pip cache directory path
Invalidation: requirements.txt modification

# Godot export
Cache key: .godot/export_presets.cfg MD5 + project.godot SHA256
Invalidation: Game code or preset changes

# Server wheel
Cache key: server/pyproject.toml hash + dependencies checksum
Invalidation: Any server source change

# Agent build
Cache key: Profile JSON hash + corpus file hashes
Invalidation: Corpus regeneration, profile update
```

---

## Usage Examples

### Basic Build from Scratch

```bash
make speed
```

This will:
1. Detect available processors (e.g., 8 cores)
2. Run PREBUILD targets sequentially
3. Run PARALLEL_CORE targets concurrently with 8 jobs
4. Run POSTBUILD verification after all builds complete

### Override Processor Count

```bash
# Use exactly 4 parallel jobs regardless of detection
make speed NPROCS=4

# Or use maximum available (no limit)
make speed NPROCS=max
```

### Clean Only Speed Cache

```bash
# Removes only .speed-cache and assets/.cache directories
# Preserves all source files in do/ directory
make speed-clean
```

### Verify Build Artifacts

```bash
# Runs after successful make speed completion
make speed-verify
```

Expected output:
```
=== Running make speed verification ===

[✓] do/assets/database exists
[✓] do/godot exists
[✓] build/docker/cache/agent exists
[✓] Asset database present
[✓] Godot export present
All verifications passed
```

### Force Rebuild Specific Phase

```bash
# Invalidate assets cache and rebuild from that point
make speed-invalidate-assets && make wiki_gather_sites

# Or force agent build to retrain (bypass fingerprint check)
rm -rf do/agent/models/cache/*  # Clear training cache
make agent_build                # Will detect changed corpus
```

---

## Performance Characteristics

### First Run vs Cached Runs

| Component | First Run Time | Cached Subsequent Run |
|-----------|---------------|----------------------|
| PREBUILD (data gathering) | ~8-12 min | ~3-5 min |
| PARALLEL_CORE total* | ~40 min parallelized | ~15-25 min |
| POSTBUILD (verification) | ~5 min | ~5 min |

\* *Parallel time depends on NPROCS; with 8 cores, all targets complete in ~40 minutes instead of summing individual times.*

**Total first run**: ~90-120 minutes
**Cached subsequent runs**: ~30-45 minutes (depending on changes made)

### Parallelization Efficiency

With **NPROCS=8**, the PARALLEL_CORE phase completes in approximately:
```
max(target_time_1, target_time_2, ...)  # Not sum of all times!
```

Example calculation:
- `server_install_dev`: ~5 min
- `admin_install`: ~2 min
- `server_docker_build`: ~10 min (but layers cached)
- `godot_export`: ~15 min
- `server_docker_build`: ~8 min

**Sequential total**: ~30-40 minutes
**Parallel with NPROCS=8**: ~15-20 minutes (limited by longest target + I/O)

---

## Adding New Targets to make speed

To add a new build target to the orchestration:

### Step 1: Add to appropriate phase list

```makefile
# In build/makefiles/speed.mk, choose the right category:

# If it must run before parallel builds (data gathering):
PREBUILD_TARGETS += my_new_target

# If it can run concurrently with others:
PARALLEL_TARGETS += my_new_target

# If it should verify after all builds complete:
POSTBUILD_TARGETS += my_new_test
```

### Step 2: Ensure target has proper dependencies

The existing targets in each phase are independent of each other. New targets should follow the same pattern:

```makefile
my_new_target: some_prerequisite
	# Build command here
	some_command arg1 arg2

my_new_test: my_new_target   # Test depends on build completing
	# Verification command
	test_output = $(shell test -f output.txt) && echo "OK" || exit 1
```

### Step 3: Document cache behavior

Add a comment explaining what makes the target cacheable or when it should be invalidated. Example:

```makefile
my_new_target: some_prerequisite
	# Cache key: hash of input files in src/ directory
	# Invalidation: Any change to src/*.py triggers rebuild
	some_command arg1 arg2
```

---

## Troubleshooting

### Issue: "NPROCS not detected correctly"

**Symptom**: Build runs with 1 job instead of expected parallelism.

**Solution**:
```bash
# Check detection output manually
$(shell nproc)           # On Linux/macOS
powershell -Command "echo [System.Environment]::ProcessorCount"   # Windows/WSL

# Force specific value
make speed NPROCS=8
```

### Issue: "Cache not being reused across runs"

**Symptom**: Build times similar to first run even after changes.

**Diagnosis**: Check cache key components changed:
- Docker image base layer digest (run `docker history`)
- npm lock file hash (`sha256sum package-lock.json`)
- Python requirements checksum

**Solution**: Clear specific caches if needed:
```bash
make speed-invalidate-assets   # If site content changed
rm -rf build/docker/cache/huggingface/*  # If model files updated
```

### Issue: "Need agent model build too"

**Symptom**: `make speed` completes game assets/runtime build but no agent model artifacts are refreshed.

**Solution**: Agent build is intentionally separate and can be run independently:
```bash
make agent_build AGENT_PROFILE=myprofile
```

### Issue: "Need to rebuild only specific component"

**Symptom**: Want to re-run just `godot_export` without full speed.

**Solution**: Use individual targets directly (they're still part of make speed):
```bash
# Rebuild Godot export only
make godot_export

# Or run parallel phase with subset
make server_install_dev admin_install  # Just env setup
```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Build LOTR Project

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          make server_install_dev  # Or use speed target if available

      - name: Build full project
        run: |
          echo "Building with $(nproc) processors..."
          make speed NPROCS=$(nproc)

      - name: Verify build artifacts
        run: |
          make speed-verify || exit 1

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: lotr-build-output
          path: |
            do/godot/lotr-tcg.x86_64
            do/assets/database/
            server/dist/*.whl
```

### GitLab CI Example

```yaml
build-lotr:
  stage: build
  image: python:3.12

  variables:
    NPROCS: "$CI_CPU_COUNT"

  script:
    - pip install --upgrade pip
    - make server_install_dev
    - echo "Building with $NPROCS processors..."
    - make speed

  artifacts:
    paths:
      - do/godot/lotr-tcg.x86_64
      - do/assets/database/
```

---

## Future Improvements (Roadmap)

### Phase 1: Enhanced Caching
- [x] Add checksum stamp skip for `wiki_gather_sites` using input/output fingerprints
- [x] Implement output tree hash verification for `wiki_create_lotr_database` and `wiki_parse_game_logic`
- [ ] Cache Godot export by project.godot + export_presets checksums

### Phase 2: Smart Parallelization
- [ ] Dynamic NPROCS adjustment based on target types (I/O-bound vs CPU-bound)
- [ ] Resource-aware scheduling that limits concurrent Docker builds
- [ ] Background task queuing for long-running agent builds

### Phase 3: Progress Tracking
- [ ] Real-time progress bars during parallel phase
- [ ] Per-target timing statistics output after completion
- [ ] Cache hit/miss reporting per component

### Phase 4: Incremental Builds
- [ ] Detect changed input files and rebuild only affected targets in PARALLEL_CORE
- [ ] Smart invalidation based on git diff analysis
- [ ] "make speed --incremental" flag for faster dev cycles

---

## Summary

The `make speed` implementation provides a robust, cache-aware build orchestration system that:

✅ **Auto-detects processors** with multiple fallback strategies for cross-platform compatibility
✅ **Organizes builds into phases**: PREBUILD → PARALLEL_CORE → POSTBUILD
✅ **Maximizes parallelization** by running independent targets concurrently
✅ **Preserves caches across runs** to speed up subsequent builds significantly
✅ **Provides verification** after all builds complete successfully

Run `make speed` once for a full build, then enjoy faster incremental builds as you develop!
