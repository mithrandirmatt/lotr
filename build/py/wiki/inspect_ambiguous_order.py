#!/usr/bin/env python3
import json, re, sys

card_db = json.load(open('build/do/assets/database/card_database.json', 'r', encoding='utf-8'))
amb = json.load(open('build/do/assets/database/ambiguous_filters.json', 'r', encoding='utf-8'))
items = amb.get('items', [])

def key_for_cid(cid):
    if not cid:
        return (9999, 9999, cid)
    rec = card_db.get(cid)
    if rec and isinstance(rec.get('set_num'), int):
        set_num = rec.get('set_num')
        collector = rec.get('collector_info') or ''
        m = re.search(r'(\d+)$', collector)
        if m:
            try:
                card_num = int(m.group(1))
                return (set_num, card_num, cid)
            except Exception:
                pass
    m = re.search(r'(\d+)$', cid)
    if m:
        num = int(m.group(1))
        return (num // 1000, num % 1000, cid)
    return (9999, 9999, cid)

orig_ids = [it.get('card_id') for it in items]
unique_ids = sorted(sorted(set(orig_ids)), key=key_for_cid)
print('Total ambiguous items:', len(items))
print('\nUnique card ids in ambiguous items (sorted):')
for i, cid in enumerate(unique_ids[:50]):
    print(i+1, key_for_cid(cid), cid)

print('\nFirst ambiguous item in provided order:', items[0].get('card_id') if items else None)
sorted_items = sorted(items, key=lambda it: key_for_cid(it.get('card_id') or ''))
print('\nFirst 20 sorted ambiguous items:')
for i, it in enumerate(sorted_items[:20]):
    print(i+1, key_for_cid(it.get('card_id') or ''), it.get('card_id'), it.get('action_id'), (it.get('raw_text') or '')[:80].replace('\n',' '))

# earliest card overall in card_db
all_cards_sorted = sorted(card_db.keys(), key=key_for_cid)
print('\nEarliest card overall in card_db:', all_cards_sorted[0] if all_cards_sorted else None)
