from pathlib import Path
import yaml

repo_root = Path(__file__).resolve().parents[2]
agents_dir = repo_root / '.github' / 'agents'

for agent_path in sorted(agents_dir.glob('*.agent.md')):
    text = agent_path.read_text(encoding='utf-8')
    if '---' in text:
        parts = text.split('---', 2)
        fm_text = parts[1]
        body = parts[2] if len(parts) > 2 else ''
        try:
            fm = yaml.safe_load(fm_text) or {}
        except Exception as e:
            print(f'Failed to parse frontmatter for {agent_path}: {e}')
            fm = {}
    else:
        fm = {}
        body = text

    includes = fm.get('includes') or fm.get('include') or []
    if not includes:
        print(f'No includes for {agent_path.name}; skipping merge')
        continue

    merged = {}
    for inc in includes:
        inc_path = (agent_path.parent / inc).resolve()
        if not inc_path.exists():
            print(f'Include not found: {inc} (referenced from {agent_path.name})')
            continue
        inc_text = inc_path.read_text(encoding='utf-8')
        if '---' in inc_text:
            inc_parts = inc_text.split('---', 2)
            try:
                inc_fm = yaml.safe_load(inc_parts[1]) or {}
            except Exception as e:
                print(f'Failed to parse include frontmatter {inc_path}: {e}')
                inc_fm = {}
        else:
            try:
                inc_fm = yaml.safe_load(inc_text) or {}
            except Exception as e:
                print(f'Failed to parse include file {inc_path}: {e}')
                inc_fm = {}

        # If the included content parsed as a YAML list, infer a key (e.g., tools)
        if isinstance(inc_fm, list):
            key = None
            if all(isinstance(item, dict) and (('type' in item) or ('description' in item) or ('name' in item)) for item in inc_fm):
                key = 'tools'
            elif all(isinstance(item, dict) and ('prompt' in item) for item in inc_fm):
                key = 'user_templates'
            else:
                key = 'shared_items'
            inc_fm = {key: inc_fm}

        for k, v in (inc_fm.items() if isinstance(inc_fm, dict) else []):
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = {**merged[k], **v}
            elif k in merged and isinstance(merged[k], list) and isinstance(v, list):
                merged[k] = v + merged[k]
            else:
                merged[k] = v

    # overlay agent's own frontmatter (agent overrides included)
    final = {**merged}
    for k, v in fm.items():
        if k == 'includes':
            continue
        if k in final and isinstance(final[k], dict) and isinstance(v, dict):
            final[k] = {**final[k], **v}
        elif k in final and isinstance(final[k], list) and isinstance(v, list):
            final[k] = final[k] + v
        else:
            final[k] = v

    out_text = '---\n' + yaml.safe_dump(final, sort_keys=False) + '---\n' + (body or '')
    # write merged output to generated/ to preserve source includes
    gen_dir = agent_path.parent / 'generated'
    gen_dir.mkdir(parents=True, exist_ok=True)
    out_path = gen_dir / agent_path.name
    out_path.write_text(out_text, encoding='utf-8')
    print(f'Built agent: {out_path.relative_to(repo_root)}')
