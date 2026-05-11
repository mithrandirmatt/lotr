#!/usr/bin/env python3
import importlib.util
import json
import os
import re

spec = importlib.util.spec_from_file_location('rev','build/py/wiki/review_cli.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

card_db = json.load(open('build/do/assets/database/card_database.json','r',encoding='utf-8'))
amb = json.load(open('build/do/assets/database/ambiguous_filters.json','r',encoding='utf-8'))
items = amb.get('items', [])
if not items:
    print('No ambiguous items')
    raise SystemExit(0)

it = items[0]
card = card_db.get(it.get('card_id')) or {}

p = mod.create_preview_html(card, it, card_db)
print('preview_file=' + p)

s = open(p, 'r', encoding='utf-8').read()
imgs = re.findall(r'<img src="([^"]+)"', s)
print('imgs=', imgs)

from urllib.parse import unquote
print('\nexistence checks:')
for img in imgs:
    if img.startswith('file:'):
        path = unquote(img.replace('file://','',1))
        print(img, os.path.exists(path), path)
    else:
        print('non-file uri', img)

# Attempt to open the preview using the module's opener (will print diagnostics)
mod.open_preview_file(p)
