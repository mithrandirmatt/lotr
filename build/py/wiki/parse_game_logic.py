#!/usr/bin/env python3
"""Initial deterministic game-logic parser.

Reads `build/do/assets/database/card_database.json` and writes
`build/do/assets/database/game_logic_database.json` using
`game_logic_schema.py` dataclasses. This first pass implements a
conservative, regex-driven extraction for phase actions, trigger
prefixes, keywords, and a few common cost/effect patterns.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import difflib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
PYUTILS_DIR = os.path.join(REPO_ROOT, 'pyutils')

# Ensure local module imports work when invoked from repo root
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PYUTILS_DIR)

from game_logic_schema import (
    GameLogicDatabase,
    CardGameLogic,
    Action,
    Cost,
    Condition,
    Effect,
    Target,
    PHASE_TRIGGERS,
)


INPUT_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'card_database.json')
OUTPUT_PATH = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'game_logic_database.json')
APPROVAL_PATH = os.path.join(REPO_ROOT, 'gotdot', 'assets', 'data', 'approval_status.json')


def strip_tags(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return ' '.join(text.split())


_KW_PATTERN = re.compile(r'^[A-Za-z][A-Za-z\-]+(?:\s+\+?\d+)?$')


def parse_keywords(game_text: str) -> list[str]:
    if not game_text:
        return []
    keywords = []
    for raw_sent in re.split(r'\.\s+', game_text):
        sent = raw_sent.rstrip('.')
        sent = re.sub(r'[\u2013\u2014]', ' ', sent)
        sent = re.sub(r'\s+', ' ', sent).strip()
        if _KW_PATTERN.match(sent):
            keywords.append(sent.lower())
    return keywords


_PHASE_RE = re.compile(r'(?i)(fellowship:|shadow:|maneuver:|archery:|assignment:|skirmish:|regroup:)')

# Named draw/play/search patterns
_PLAY_NAMED_FROM_DECK_RE = re.compile(r"(?i)play (?:an?|the)? (?:card named |card called |the card named )?[\'\"]?(?P<name>[^\'\",\.]+?)[\'\"]? from your draw deck")
_DRAW_NAMED_RE = re.compile(r"(?i)draw (?:a|an|the)? card named [\'\"]?(?P<name>[^\'\",\.]+)[\'\"]?")
_SEARCH_PLAY_RE = re.compile(r"(?i)search your draw deck for (?:a|an|the)? (?:card named )?[\'\"]?(?P<name>[^\'\",\.]+)[\'\"]?.*play")
_SEARCH_RE = re.compile(r"(?i)search your draw deck for (?:a|an|the)? (?P<name>[^\'\",\.]+)")


def split_phase_sections(game_text: str) -> list[tuple[str | None, str]]:
    """Return list of (phase_or_none, text).
    Text before any phase prefix returns as (None, text).
    """
    if not game_text:
        return []
    parts = _PHASE_RE.split(game_text)
    out: list[tuple[str | None, str]] = []
    if parts:
        pre = parts[0].strip()
        if pre:
            out.append((None, pre))
    for i in range(1, len(parts), 2):
        phase = parts[i].rstrip(':').strip().lower()
        content = parts[i + 1] if i + 1 < len(parts) else ''
        out.append((phase, content.strip()))
    return out


_TRIGGER_PREFIX_RE = re.compile(r'(?i)^(when|each time|while|response)\b')


_action_counter = 0


def next_action_id(card_id: str) -> str:
    global _action_counter
    _action_counter += 1
    return f"{card_id}-a-{_action_counter}"


# Global card DB reference populated in main() to allow name resolution.
CARD_DB: dict = {}
ALIAS_INDEX: dict = {}


def _normalize_name_query(name: str) -> str:
    if not name:
        return ''
    s = re.sub(r'\(.*?\)', '', name)
    s = s.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    return s


def _resolve_name_to_ids(query: str) -> list:
    """Conservative name resolution with alias index + fuzzy matching.

    Strategy:
      1. Exact normalized alias lookup in `ALIAS_INDEX`.
      2. Conservative substring/title heuristics across card names.
      3. Conservative fuzzy match against alias keys (difflib).
    """
    q = _normalize_name_query(query)
    if not q or not CARD_DB:
        return []

    # 1) exact alias lookup
    if ALIAS_INDEX and q in ALIAS_INDEX:
        return ALIAS_INDEX[q][:]

    # 2) conservative full-name heuristics
    matches = []
    for cid, c in CARD_DB.items():
        cn = _normalize_name_query(c.get('name') or '')
        if not cn:
            continue
        if cn == q or cn.startswith(q + ',') or cn.startswith('the ' + q) or q.startswith(cn):
            matches.append(cid)
    if matches:
        return matches

    # 3) fuzzy match against alias keys
    if ALIAS_INDEX:
        keys = list(ALIAS_INDEX.keys())
        close = difflib.get_close_matches(q, keys, n=3, cutoff=0.90)
        if len(close) == 1:
            return ALIAS_INDEX[close[0]][:]
        # second-tier: lower cutoff but require a clear top scorer
        close2 = difflib.get_close_matches(q, keys, n=3, cutoff=0.80)
        if close2:
            scores = [(difflib.SequenceMatcher(None, q, k).ratio(), k) for k in close2]
            scores.sort(reverse=True)
            if scores[0][0] >= 0.88 and (len(scores) == 1 or scores[0][0] - scores[1][0] > 0.08):
                return ALIAS_INDEX[scores[0][1]][:]

    return []


def _build_alias_index(cards: dict) -> dict:
    """Build mapping normalized alias -> [card_id, ...].

    Includes: full name, main title (before comma), name without leading 'The', and subtitle.
    """
    aliases: dict = {}
    for cid, c in cards.items():
        name = c.get('name') or ''
        if not name:
            continue
        full = _normalize_name_query(name)
        aliases.setdefault(full, []).append(cid)

        # main title before comma
        main = name.split(',')[0].strip()
        if main:
            nmain = _normalize_name_query(main)
            if nmain and nmain != full:
                aliases.setdefault(nmain, []).append(cid)
            if main.lower().startswith('the '):
                tail = main[4:].strip()
                ntail = _normalize_name_query(tail)
                if ntail and ntail != full:
                    aliases.setdefault(ntail, []).append(cid)

        # subtitle
        sub = c.get('subtitle')
        if sub:
            nsub = _normalize_name_query(sub)
            if nsub:
                aliases.setdefault(nsub, []).append(cid)

    # dedupe lists
    for k in list(aliases.keys()):
        aliases[k] = sorted(set(aliases[k]))
    return aliases


def _extract_trait_filter(text: str) -> dict | None:
    """Try to extract simple trait/culture/card-type filters from text.

    Examples matched: 'a Gondor Ally', 'a Ranger', 'a Gondor character'
    Returns a dict like {'culture': 'Gondor', 'card_type': 'Ally', 'traits': []}
    or None if not matched.
    """
    if not text:
        return None
    # culture + type: e.g. 'a Gondor Ally'
    m = re.search(r'(?i)\b(?P<culture>[A-Z][a-z]+)\s+(?P<ctype>ally|companion|minion|character|attachment|possession|event|condition|site|follower)\b', text)
    if m:
        return {'culture': m.group('culture'), 'card_type': m.group('ctype'), 'traits': []}
    # trait-only before 'from your draw deck' or similar
    m2 = re.search(r"(?i)\b([A-Z][a-z]+)\b(?= from your draw deck| from your draw pile| from your deck)", text)
    if m2:
        return {'culture': None, 'card_type': None, 'traits': [m2.group(1)]}
    return None


def _filter_cards_by_traits(trait_filter: dict) -> list:
    """Return card_ids matching the simple trait/culture/card_type filter.

    Conservative matching: culture equality (normalized), card_type in card_type or subtypes, and trait in keywords/subtypes/name.
    """
    if not trait_filter:
        return []
    res = []
    culture = trait_filter.get('culture')
    ctype = trait_filter.get('card_type')
    traits = trait_filter.get('traits') or []
    for cid, c in CARD_DB.items():
        if culture:
            if not c.get('culture') or _normalize_name_query(c.get('culture')) != _normalize_name_query(culture):
                continue
        if ctype:
            ct = (c.get('card_type') or '').lower()
            subs = [s.lower() for s in (c.get('subtypes') or [])]
            if ctype.lower() not in ct and ctype.lower() not in subs:
                continue
        if traits:
            kw = [k.lower() for k in (c.get('keywords') or [])]
            subs = [s.lower() for s in (c.get('subtypes') or [])]
            name = _normalize_name_query(c.get('name') or '')
            matched = False
            for t in traits:
                tl = t.lower()
                if tl in kw or tl in subs or tl in name:
                    matched = True
                    break
            if not matched:
                continue
        res.append(cid)
    return res


def extract_actions_from_fragment(card_id: str, fragment: str, default_trigger: str | None = None) -> list[Action]:
    """Create one or more `Action` objects from a text fragment.

    This function uses conservative regex checks to populate costs/effects
    and sets a confidence score. Unmatched fragments are preserved as a
    `custom` effect with low confidence and marked ambiguous.
    """
    fragments = [s.strip().rstrip('.') for s in re.split(r'\.\s+', fragment) if s.strip()]
    actions: list[Action] = []
    for sent in fragments:
        a = Action(action_id=next_action_id(card_id))
        a.raw_text = sent
        # trigger / timing
        if default_trigger:
            a.trigger = default_trigger
            a.timing = 'immediate'
        else:
            m = _TRIGGER_PREFIX_RE.match(sent)
            if m:
                a.trigger = m.group(1).lower()
                a.timing = 'continuous' if a.trigger == 'while' else 'on_event'
            else:
                a.timing = 'immediate'

        lower = sent.lower()

        # Simple cost recognisers
        if re.search(r'\bexert\b', lower):
            a.costs.append(Cost(cost_type='exert', raw=sent))
        if re.search(r'\bspot\b', lower):
            a.costs.append(Cost(cost_type='spot', raw=sent))
        if re.search(r'\bdiscard\b', lower) and re.search(r'to play|to add', lower) is None:
            # ambiguous: treat as effect by default unless context suggests a cost
            a.effects.append(Effect(effect_type='discard_card', raw=sent))
        if re.search(r'\bdiscard\b', lower) and re.search(r'to play|to add', lower):
            a.costs.append(Cost(cost_type='discard', raw=sent))
        if re.search(r'\badd a burden\b|\bplace a burden\b', lower):
            # context-dependent; mark as effect for now
            a.effects.append(Effect(effect_type='place_burden', raw=sent))
        if re.search(r'\bwound\b', lower) and not re.search(r'prevent|prevented', lower):
            a.effects.append(Effect(effect_type='wound', raw=sent))
        if re.search(r'\bheal\b', lower):
            a.effects.append(Effect(effect_type='heal', raw=sent))
        # Detect named draw / search / play-from-deck patterns first
        m_play_named = _PLAY_NAMED_FROM_DECK_RE.search(sent)
        m_draw_named = _DRAW_NAMED_RE.search(sent)
        m_search_play = _SEARCH_PLAY_RE.search(sent)
        m_search = _SEARCH_RE.search(sent)

        if m_play_named:
            name = m_play_named.group('name').strip()
            eff = Effect(effect_type='play_card_from_deck', raw=sent)
            eff.filter = {'name_text': name, 'card_ids': None, 'traits': []}
            # Try to resolve now if unambiguous
            ids = _resolve_name_to_ids(name)
            if len(ids) == 1:
                eff.filter['card_ids'] = ids
                eff.card_name = (CARD_DB.get(ids[0]) or {}).get('name')
            else:
                a.ambiguous = True
            a.effects.append(eff)
        elif m_draw_named:
            name = m_draw_named.group('name').strip()
            eff = Effect(effect_type='draw_card', raw=sent)
            eff.filter = {'name_text': name, 'card_ids': None, 'traits': []}
            ids = _resolve_name_to_ids(name)
            if len(ids) == 1:
                eff.filter['card_ids'] = ids
                eff.card_name = (CARD_DB.get(ids[0]) or {}).get('name')
            else:
                a.ambiguous = True
            a.effects.append(eff)
        elif m_search_play:
            name = m_search_play.group('name').strip()
            eff = Effect(effect_type='play_card_from_deck', raw=sent)
            eff.filter = {'name_text': name, 'card_ids': None, 'traits': []}
            ids = _resolve_name_to_ids(name)
            if len(ids) == 1:
                eff.filter['card_ids'] = ids
                eff.card_name = (CARD_DB.get(ids[0]) or {}).get('name')
            else:
                a.ambiguous = True
            a.effects.append(eff)
        elif m_search:
            # generic search; capture name and leave ambiguous for manual QA
            name = m_search.group('name').strip()
            eff = Effect(effect_type='reveal_cards', raw=sent)
            eff.filter = {'name_text': name, 'card_ids': None, 'traits': []}
            ids = _resolve_name_to_ids(name)
            if len(ids) == 1:
                eff.filter['card_ids'] = ids
                eff.card_name = (CARD_DB.get(ids[0]) or {}).get('name')
            else:
                a.ambiguous = True
            a.effects.append(eff)
        else:
            # generic draw mention: fallback to generic draw effect
            if re.search(r'\bdraw\b', lower):
                a.effects.append(Effect(effect_type='draw_card', raw=sent))

        # Stat modifiers: strength +1, vitality -1
        mstat = re.search(r'\b(strength|vitality|resistance)\s*([+-]\d+)\b', lower)
        if mstat:
            a.effects.append(Effect(effect_type='modify_stat', stat=mstat.group(1), value=mstat.group(2), raw=sent))

        # Play-from-deck pattern
        # legacy catch-all for play-from-deck phrasing not matched above
        if re.search(r'play .* from your draw deck', lower) and not any(e.effect_type in ('play_card_from_deck','draw_card','reveal_cards') for e in a.effects):
            a.effects.append(Effect(effect_type='play_card_from_deck', raw=sent))

        # If nothing deterministic matched, keep the fragment as a custom effect
        if not a.effects and not a.costs and not a.conditions:
            a.effects.append(Effect(effect_type='custom', raw=sent))
            a.confidence = 0.3
            a.ambiguous = True
        else:
            score = 0.0
            if a.costs:
                score += 0.4
            if a.effects:
                score += 0.6
            a.confidence = min(1.0, score)
            a.ambiguous = a.confidence < 0.7

        actions.append(a)
    return actions


def main():
    if not os.path.exists(INPUT_PATH):
        print(f'Input DB not found: {INPUT_PATH}')
        sys.exit(1)

    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        cards = json.load(f)

    # Populate global CARD_DB for name-resolution helpers and build alias index
    global CARD_DB, ALIAS_INDEX
    CARD_DB = cards
    ALIAS_INDEX = _build_alias_index(cards)

    # Load or create approval-status file (mapping card_id -> passed: bool).
    approval = None
    try:
        if os.path.exists(APPROVAL_PATH):
            with open(APPROVAL_PATH, 'r', encoding='utf-8') as af:
                approval = json.load(af)
        else:
            approval = {cid: False for cid in cards.keys()}
            os.makedirs(os.path.dirname(APPROVAL_PATH), exist_ok=True)
            with open(APPROVAL_PATH, 'w', encoding='utf-8') as af:
                json.dump(approval, af, ensure_ascii=False, indent=2)
            print(f'Created approval status file with {len(approval)} entries at {APPROVAL_PATH}')
    except Exception:
        approval = {cid: False for cid in cards.keys()}

    # Load any existing game-logic output so we can skip re-processing passed cards
    existing = None
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, 'r', encoding='utf-8') as ef:
                existing = json.load(ef)
        except Exception:
            existing = None

    final_cards: dict = {}
    processed_ids: list = []

    # Process cards, skipping those marked as passed when possible
    for card_id, card in sorted(cards.items()):
        # If approved and existing output contains this card, reuse it
        if approval.get(card_id, False) and existing and card_id in existing:
            final_cards[card_id] = existing[card_id]
            continue

        # otherwise parse the card as normal
        raw_text = card.get('game_text') or ''
        cl = CardGameLogic(card_id=card_id, name=card.get('name') or '', raw_text=raw_text)

        # Keywords
        kws = parse_keywords(raw_text)
        if kws:
            cl.has_keywords = True
            for i, kw in enumerate(kws, start=1):
                ka = Action(action_id=f"{card_id}-kw-{i}")
                ka.trigger = kw
                ka.timing = 'continuous'
                ka.raw_text = kw
                ka.confidence = 1.0
                cl.keyword_actions.append(ka)

        # Phase-aware splitting and fragment parsing
        sections = split_phase_sections(raw_text)
        for phase, text in sections:
            if not text:
                continue
            if phase:
                # content belongs to a phase action block
                actions = extract_actions_from_fragment(card_id, text, default_trigger=phase)
            else:
                # no explicit phase: split into sentences and detect trigger prefixes
                fragments = [s.strip() for s in re.split(r'\.\s+', text) if s.strip()]
                actions: list[Action] = []
                for frag in fragments:
                    m = _TRIGGER_PREFIX_RE.match(frag)
                    if m:
                        actions.extend(extract_actions_from_fragment(card_id, frag, default_trigger=m.group(1).lower()))
                    else:
                        actions.extend(extract_actions_from_fragment(card_id, frag))

            cl.actions.extend(actions)

        # serialize this card's logic using the schema helper
        tmp = GameLogicDatabase()
        tmp.cards[card_id] = cl
        ser = tmp.to_dict()
        final_cards[card_id] = ser[card_id]
        processed_ids.append(card_id)

    # Write merged output (reused entries + newly parsed entries)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_cards, f, ensure_ascii=False, indent=2)

    print(f'Wrote {len(final_cards)} cards to {OUTPUT_PATH} (processed {len(processed_ids)} cards)')

    # Emit ambiguous filter report for manual review only for cards processed in this run
    ambiguous = []
    for cid in processed_ids:
        cl = final_cards.get(cid)
        if not cl:
            continue
        for a in cl.get('actions', []):
            for e in a.get('effects', []):
                f = e.get('filter')
                if not f:
                    continue
                card_ids = f.get('card_ids') if isinstance(f, dict) else None
                if card_ids:
                    continue
                name_text = f.get('name_text') if isinstance(f, dict) else None
                candidates = []
                if name_text:
                    candidates = _resolve_name_to_ids(name_text)
                if not candidates:
                    trait_filter = f if isinstance(f, dict) and (f.get('culture') or f.get('card_type') or (f.get('traits') and len(f.get('traits'))>0)) else None
                    if trait_filter:
                        candidates = _filter_cards_by_traits(trait_filter)
                ambiguous.append({
                    'card_id': cid,
                    'card_name': cl.get('name'),
                    'action_id': a.get('action_id'),
                    'raw_text': a.get('raw_text'),
                    'filter': f,
                    'candidate_ids': candidates,
                })

    ambiguous_path = os.path.join(REPO_ROOT, 'build', 'do', 'assets', 'database', 'ambiguous_filters.json')
    try:
        with open(ambiguous_path, 'w', encoding='utf-8') as af:
            json.dump({'count': len(ambiguous), 'items': ambiguous}, af, ensure_ascii=False, indent=2)
        print(f'Wrote ambiguous filter report to {ambiguous_path} ({len(ambiguous)} items)')
    except Exception as e:
        print(f'Warning: failed to write ambiguous report: {e}')


if __name__ == '__main__':
    main()
