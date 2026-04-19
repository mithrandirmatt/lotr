

.PHONY: update_agent

PY := python
BUILD_SCRIPT := .github/scripts/build_agents.py
GENERATED_DIR := .github/agents/generated

update_agent:
	@echo "Running agent build..."
	@$(PY) $(BUILD_SCRIPT)
	@echo "Validating YAML frontmatter for key agent files..."
	@$(PY) - <<'PY'
import sys, pathlib, yaml
paths = [
	'.github/agents/my-agent.agent.md',
	'.github/agents/generated/my-agent.agent.md',
	'.github/agent/permissions.md'
]
errs = []
for p in paths:
	pth = pathlib.Path(p)
	if not pth.exists():
		print('MISSING', p)
		errs.append(p)
		continue
	txt = pth.read_text(encoding='utf-8')
	if not txt.strip().startswith('---'):
		print('NO FRONTMATTER', p)
		errs.append(p)
		continue
	fm = txt.split('---')[1]
	try:
		yaml.safe_load(fm)
	except Exception as e:
		print('YAML ERROR in', p, e)
		errs.append(p)
if errs:
	print('Validation failed', errs)
	sys.exit(2)
print('Validation OK')
PY
	@echo "Staging generated files and committing..."
	@git add $(GENERATED_DIR) || true
	@git commit -m "chore(agent): update generated agents" || echo "no changes to commit"
	@git push || echo "push failed"