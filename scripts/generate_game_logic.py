#!/usr/bin/env python3
"""
Game Logic Database Generator
Parses card_database.json and generates structured game_logic_database.json
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Action:
    """Represents a single game action from card text"""
    action_id: str
    trigger: str
    timing: str
    cost: List[Dict[str, Any]]
    conditions: List[Dict[str, Any]]
    effects: List[Dict[str, Any]]
    targets: List[str]
    confidence: float
    ambiguous: bool
    notes: str

@dataclass
class CardLogic:
    """Structured game logic for a single card"""
    card_id: str
    name: str
    raw_text: str
    actions: List[Action]
    source_file: str
    created_by: str

# ============================================================================
# PARSING RULES
# ============================================================================

# Phase/trigger mapping
PHASE_MAP = {
    'fellowship': 'fellowship',
    'shadow': 'shadow',
    'maneuver': 'maneuver',
    'archery': 'archery',
    'skirmish': 'skirmish',
    'regroup': 'regroup',
    'assignment': 'assignment',
    'draw': 'draw',
    'play': 'play',
    'combat': 'combat',
}

# Common cost patterns
COST_PATTERNS = [
    # Burden patterns
    (r'add a burden', {'type': 'add_burden', 'value': 1}),
    (r'add \d+ burdens?', {'type': 'add_burden', 'value': int(re.search(r'\d+', re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1)}),

    # Exert patterns
    (r'exert (\w+)?', {'type': 'exert', 'target': r'\1'}),
    (r'exert \d+', {'type': 'exert', 'target': r'\d+'}),

    # Discard patterns
    (r'discard (\w+(?:\s+\w+)*)', {'type': 'discard', 'target': r'\1'}),
    (r'discard \d+ (\w+(?:\s+\w+)*)', {'type': 'discard', 'target': r'\2', 'count': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1)}),

    # Draw patterns
    (r'draw (\d+) card(s)?', {'type': 'draw', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1}),

    # Play patterns
    (r'play (\w+(?:\s+\w+)*) from your draw deck', {'type': 'play_card_from_deck', 'card_name': r'\1'}),
    (r'play (\w+(?:\s+\w+)*) from your hand', {'type': 'play_card_from_hand', 'card_name': r'\1'}),

    # Cost patterns
    (r'cost (\d+)', {'type': 'cost', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1}),
    (r'cost (\d+) life', {'type': 'cost_life', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1}),
]

# Common effect patterns
EFFECT_PATTERNS = [
    # Healing
    (r'heal your companion', {'type': 'heal', 'target': 'companion', 'value': 1}),
    (r'heal your ally', {'type': 'heal', 'target': 'ally', 'value': 1}),
    (r'heal up to (\d+) wounds', {'type': 'heal', 'target': 'companion', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1}),

    # Strength modifications
    (r'that ally is strength \+(\d+)', {'type': 'modify_stat', 'stat': 'strength', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1, 'target': 'that_ally', 'duration': 'until_regroup'}),
    (r'your ally is strength \+(\d+)', {'type': 'modify_stat', 'stat': 'strength', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1, 'target': 'your_ally', 'duration': 'until_regroup'}),

    # Vitality modifications
    (r'your companion is vitality \+(\d+)', {'type': 'modify_stat', 'stat': 'vitality', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1, 'target': 'your_companion', 'duration': 'until_regroup'}),

    # Resistance modifications
    (r'your companion is resistance \+(\d+)', {'type': 'modify_stat', 'stat': 'resistance', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1, 'target': 'your_companion', 'duration': 'until_regroup'}),

    # Site effects
    (r'at an underground site', {'type': 'site_condition', 'site_type': 'underground'}),
    (r'at a site', {'type': 'site_condition', 'site_type': 'any'}),

    # Draw deck effects
    (r'shuffle up to (\d+) cards from your discard pile into your draw deck', {'type': 'shuffle_discard', 'count': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1}),

    # Combat effects
    (r'attack with (\w+(?:\s+\w+)*)', {'type': 'attack', 'target': r'\1'}),
    (r'block with (\w+(?:\s+\w+)*)', {'type': 'block', 'target': r'\1'}),

    # Movement effects
    (r'move to (\w+(?:\s+\w+)*)', {'type': 'move', 'target': r'\1'}),

    # General effects
    (r'gain (\d+) strength', {'type': 'gain_strength', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1}),
    (r'gain (\d+) vitality', {'type': 'gain_vitality', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1}),
    (r'gain (\d+) resistance', {'type': 'gain_resistance', 'value': int(re.search(r'\d+', match.group(0)).group(0)) if (match := re.search(r'\d+', match.group(0))) else 1}),
]

# Keyword patterns for additional context
KEYWORD_PATTERNS = {
    'spell': 'spell',
    'bearer': 'bearer',
    'site': 'site',
    'fellowship': 'fellowship',
    'shadow': 'shadow',
    'unique': 'unique',
}

# ============================================================================
# PARSING FUNCTIONS
# ============================================================================

def normalize_trigger(trigger_text: str) -> str:
    """Normalize trigger text to standard format"""
    trigger_text = trigger_text.lower().strip()
    return PHASE_MAP.get(trigger_text, trigger_text)

def parse_cost(cost_text: str) -> List[Dict[str, Any]]:
    """Parse cost text into structured cost objects"""
    costs = []
    if not cost_text:
        return costs

    for pattern, template in COST_PATTERNS:
        match = re.search(pattern, cost_text, re.IGNORECASE)
        if match:
            cost_obj = template.copy()
            # Handle value extraction
            if 'value' in cost_obj and isinstance(cost_obj['value'], str):
                try:
                    cost_obj['value'] = int(cost_obj['value'])
                except (ValueError, TypeError):
                    pass
            costs.append(cost_obj)
            break

    return costs

def parse_effect(effect_text: str) -> List[Dict[str, Any]]:
    """Parse effect text into structured effect objects"""
    effects = []
    if not effect_text:
        return effects

    for pattern, template in EFFECT_PATTERNS:
        match = re.search(pattern, effect_text, re.IGNORECASE)
        if match:
            effect_obj = template.copy()
            # Handle value extraction
            if 'value' in effect_obj and isinstance(effect_obj['value'], str):
                try:
                    effect_obj['value'] = int(effect_obj['value'])
                except (ValueError, TypeError):
                    pass
            effects.append(effect_obj)
            break

    return effects

def parse_conditions(condition_text: str) -> List[Dict[str, Any]]:
    """Parse condition text into structured condition objects"""
    conditions = []
    if not condition_text:
        return conditions

    # Common condition patterns
    condition_patterns = [
        (r'must be a (\w+(?:\s+\w+)*)', {'type': 'requirement', 'requirement': r'\1'}),
        (r'while the fellowship is at this site', {'type': 'site_present'}),
        (r'during the fellowship or regroup phase', {'type': 'phase_active', 'phases': ['fellowship', 'regroup']}),
        (r'if (\w+(?:\s+\w+)*) is at an underground site', {'type': 'location_check', 'target': r'\1', 'location': 'underground'}),
    ]

    for pattern, template in condition_patterns:
        match = re.search(pattern, condition_text, re.IGNORECASE)
        if match:
            condition_obj = template.copy()
            conditions.append(condition_obj)

    return conditions

def parse_targets(action_text: str) -> List[str]:
    """Extract target entities from action text"""
    targets = []

    # Common target patterns
    target_patterns = [
        r'(?:play|attack|block|move|exert) (\w+(?:\s+\w+)*)',
        r'(?:heal|modify|gain) (?:your\s+)?(\w+(?:\s+\w+)*)',
        r'(\w+(?:\s+\w+)*) must be',
    ]

    for pattern in target_patterns:
        matches = re.findall(pattern, action_text, re.IGNORECASE)
        targets.extend(matches)

    return list(set(targets))

def parse_action(raw_text: str, card_id: str) -> Optional[Action]:
    """Parse a single action from raw card text"""
    if not raw_text or not raw_text.strip():
        return None

    # Split on colon to separate trigger from effect
    parts = raw_text.split(':', 1)
    trigger_text = parts[0].strip() if parts else ''
    effect_text = parts[1].strip() if len(parts) > 1 else ''

    # Normalize trigger
    trigger = normalize_trigger(trigger_text)

    # Determine timing
    timing = 'immediate'
    if 'when playing' in raw_text.lower():
        timing = 'when_playing'
    elif 'continuous' in raw_text.lower():
        timing = 'continuous'
    elif 'on' in raw_text.lower() and 'event' in raw_text.lower():
        timing = 'on_event'

    # Parse components
    costs = parse_cost(effect_text)
    effects = parse_effect(effect_text)
    conditions = parse_conditions(effect_text)
    targets = parse_targets(raw_text)

    # Calculate confidence based on what we parsed
    confidence = 0.0
    if trigger:
        confidence += 0.2
    if costs:
        confidence += 0.15
    if effects:
        confidence += 0.25
    if conditions:
        confidence += 0.1
    if targets:
        confidence += 0.1

    # Check for ambiguity
    ambiguous = bool(
        'up to' in raw_text.lower() or
        'may' in raw_text.lower() or
        'can' in raw_text.lower() or
        'optional' in raw_text.lower()
    )

    # Generate notes
    notes = []
    if ambiguous:
        notes.append('Contains optional/may/can language')
    if not costs and not effects:
        notes.append('No clear costs or effects parsed')
    if not trigger:
        notes.append('No clear trigger identified')

    if notes:
        notes_str = '; '.join(notes)
    else:
        notes_str = 'Fully parsed'

    return Action(
        action_id=f'a{len(card_logic_data.get("actions", [])) + 1}',
        trigger=trigger,
        timing=timing,
        cost=costs,
        conditions=conditions,
        effects=effects,
        targets=targets,
        confidence=min(confidence, 1.0),
        ambiguous=ambiguous,
        notes=notes_str
    )

def parse_card(card_id: str, card_data: Dict[str, Any]) -> CardLogic:
    """Parse a single card into structured game logic"""
    raw_text = card_data.get('game_text', '')

    # Try deterministic parsing first
    action = parse_action(raw_text, card_id)

    if action:
        return CardLogic(
            card_id=card_id,
            name=card_data.get('name', ''),
            raw_text=raw_text,
            actions=[action],
            source_file='gotdot/assets/data/card_database.json',
            created_by='my-agent-workflow:v0.1'
        )

    # Fallback: create minimal structure
    return CardLogic(
        card_id=card_id,
        name=card_data.get('name', ''),
        raw_text=raw_text,
        actions=[],
        source_file='gotdot/assets/data/card_database.json',
        created_by='my-agent-workflow:v0.1'
    )

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def process_card_database(input_path: str, output_path: str) -> Dict[str, Any]:
    """Main function to process the entire card database"""

    # Load card database
    with open(input_path, 'r', encoding='utf-8') as f:
        card_database = json.load(f)

    # Process each card in sorted order for deterministic output
    card_logic_data = {}
    stats = {
        'total_cards': len(card_database),
        'cards_with_actions': 0,
        'cards_without_actions': 0,
        'high_confidence': 0,
        'medium_confidence': 0,
        'low_confidence': 0,
        'ambiguous': 0,
    }

    for card_id in sorted(card_database.keys()):
        card_data = card_database[card_id]
        card_logic = parse_card(card_id, card_data)
        card_logic_data[card_id] = card_logic

        # Update stats
        if card_logic.actions:
            stats['cards_with_actions'] += 1
            for action in card_logic.actions:
                if action.confidence >= 0.8:
                    stats['high_confidence'] += 1
                elif action.confidence >= 0.5:
                    stats['medium_confidence'] += 1
                else:
                    stats['low_confidence'] += 1
                if action.ambiguous:
                    stats['ambiguous'] += 1
        else:
            stats['cards_without_actions'] += 1

    # Build report
    report = {
        'summary': stats,
        'coverage': {
            'total': stats['total_cards'],
            'with_actions': stats['cards_with_actions'],
            'without_actions': stats['cards_without_actions'],
            'coverage_percentage': round(stats['cards_with_actions'] / stats['total_cards'] * 100, 2) if stats['total_cards'] > 0 else 0
        },
        'confidence_distribution': {
            'high': stats['high_confidence'],
            'medium': stats['medium_confidence'],
            'low': stats['low_confidence']
        },
        'ambiguous_count': stats['ambiguous']
    }

    # Save outputs
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(card_logic_data, f, indent=2, ensure_ascii=False)

    with open('assets/reference/agent/game-logic-report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return {
        'success': True,
        'cards_processed': stats['total_cards'],
        'report': report
    }

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    input_path = 'gotdot/assets/data/card_database.json'
    output_path = 'gotdot/assets/data/game_logic_database.json'

    print(f"Processing card database from: {input_path}")
    print(f"Output will be written to: {output_path}")
    print("-" * 60)

    result = process_card_database(input_path, output_path)

    print("-" * 60)
    print("Processing Complete!")
    print(f"  Cards processed: {result['cards_processed']}")
    print(f"  Coverage: {result['report']['coverage']['coverage_percentage']}%")
    print(f"  High confidence: {result['report']['confidence_distribution']['high']}")
    print(f"  Ambiguous: {result['report']['ambiguous_count']}")
    print("-" * 60)
    print("Reports generated:")
    print("  - assets/reference/agent/game-logic-report.json")
    print("  - assets/reference/agent/game-logic-review.md (if ambiguous cards found)")

    return result

if __name__ == '__main__':
    main()
