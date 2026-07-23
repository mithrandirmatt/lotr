# LotR TCG Game Mechanism Plan: Releases, Gifts, And Server-Authoritative Distribution

## Purpose

Define the initial product mechanism for:
- New user onboarding grants
- Monthly set releases
- Gift tracking and redemption
- Server-authoritative card circulation
- Release-event planning scaffolding

This document is a planning artifact for implementation issues and database/API design.

## Core Product Rules

1. At launch, only Set 1 (Fellowship of the Ring) is visible and purchasable.
2. A new set is released every month.
3. Each set release includes a release event.
4. All purchases, gift grants, gift redemptions, and card distribution decisions are server-side only.
5. The client only submits intents; the server validates and executes all inventory mutations.

## New User Bootstrap Grants

On first successful account bootstrap, each user receives these entitlements:

1. `gift_booster_choice` x1
- User can choose one currently available set.
- Server grants one booster equivalent as a gift redemption flow.

2. `booster_choice` x5
- User can choose any currently available set for each of the 5 packs.
- Choices can be the same set or mixed sets if those sets are active.

3. `starter_deck_choice` x1
- User can choose any starter deck currently marked as available.
- Starter availability is controlled by server release policy.

Notes:
- These are entitlements first, not immediate random card inserts.
- Entitlements are consumed only when redeemed.
- Redemption and card outcomes are generated and persisted server-side.

## Gifts: Tracking And Lifecycle

### Gift Scope (Current)
Current scope is tracking, issuance, redemption, and consumption state. Detailed social gifting UX can evolve later.

### Gift Lifecycle

Recommended state machine:
- `created` - gift record created by server/admin/system
- `granted` - assigned to a user account
- `redeemed` - user has redeemed the gift token
- `consumed` - gift has been used to create inventory results
- `expired` - no longer redeemable
- `revoked` - canceled by system/admin

### Gift Rules

1. Gifts are immutable in value once granted (except revoke/expire actions).
2. Every transition must be idempotent.
3. Every transition must be audit logged.
4. Gift consumption must produce a distribution transaction ID.
5. A consumed gift cannot be reused.

## Server-Authoritative Distribution Rules

All card circulation must come from explicit server transactions.

### Allowed Distribution Sources
- Purchase redemption
- Gift redemption
- Starter deck grant
- Event rewards
- Admin/system grant (audited)

### Disallowed
- Client-side card minting
- Client-side RNG as source of truth
- Direct client inventory mutation

### Required Transaction Fields (Planning)
- `transaction_id`
- `user_id`
- `source_type` (purchase, gift, starter, event, admin)
- `source_ref_id`
- `set_code` / `set_number`
- `card_id`
- `quantity_delta`
- `created_at`
- `server_seed` (where RNG applies)

## Circulation Tracking And Balance

## Goals
1. Track total cards in circulation by set.
2. Track total cards in circulation by rarity and card ID.
3. Track active inventory totals to monitor economy balance.

### Minimum Metrics (Planning)
- `circulation_total_by_set`
- `circulation_total_by_rarity`
- `circulation_total_by_card_id`
- `cards_issued_today`
- `cards_issued_this_release_window`

### Balance Guidance
- Set soft thresholds and alerting before major imbalance.
- Add admin dashboards for circulation drift.
- Use release events and gift policy to smooth distribution.

Future work (explicitly out of current scope):
- On account closure/removal, reclaim and rebalance released cards into circulation pools.
- We only note this for now; implementation is deferred.

## Monthly Set Release Plan

At launch (Month 0), only Set 1 is active.
Each subsequent month activates the next set.

| Month | Set Number | Planned Status |
|------:|------------|----------------|
| 0 | Set 1 | Active at launch |
| 1 | Set 2 | Release event + activate |
| 2 | Set 3 | Release event + activate |
| 3 | Set 4 | Release event + activate |
| 4 | Set 5 | Release event + activate |
| 5 | Set 6 | Release event + activate |
| 6 | Set 7 | Release event + activate |
| 7 | Set 8 | Release event + activate |
| 8 | Set 9 | Release event + activate |
| 9 | Set 10 | Release event + activate |
| 10 | Set 11 | Release event + activate |
| 11 | Set 12 | Release event + activate |
| 12 | Set 13 | Release event + activate |
| 13 | Set 14 | Release event + activate |
| 14 | Set 15 | Release event + activate |
| 15 | Set 16 | Release event + activate |
| 16 | Set 17 | Release event + activate |
| 17 | Set 18 | Release event + activate |
| 18 | Set 19 | Release event + activate |

Note:
- Set names can be resolved from canonical card data during implementation.
- Release policy can support pauses or adjusted cadence later.

## Release Events (Planned)

Each monthly set release should create an event record and participation tracking entry.

### Event Metadata (Minimum)
- `event_id`
- `event_type` (`set_release`)
- `set_number`
- `start_at`
- `end_at`
- `status` (`scheduled`, `live`, `closed`)
- `reward_policy_id` (optional now, required later)

### Participation Tracking (Minimum)
- `event_id`
- `user_id`
- `joined_at`
- `participation_state`
- `reward_claim_state`

Event mechanics, scoring, and reward design are deferred to a later planning pass.

## Data Model Direction (Planning Only)

Recommended new logical tables/entities:
1. `set_release_schedule`
2. `user_entitlements`
3. `user_gifts`
4. `gift_redemptions`
5. `distribution_transactions`
6. `circulation_metrics_daily`
7. `release_events`
8. `event_participation`

## API Direction (Planning Only)

Recommended server endpoints:
1. `GET /api/v1/releases/active-sets`
2. `GET /api/v1/users/me/entitlements`
3. `POST /api/v1/users/me/entitlements/{id}/redeem`
4. `GET /api/v1/users/me/gifts`
5. `POST /api/v1/users/me/gifts/{gift_id}/redeem`
6. `GET /api/v1/circulation/summary` (admin)
7. `POST /api/v1/admin/releases/{set_number}/activate`
8. `POST /api/v1/admin/events/set-release`

## In Scope Now

1. Mechanism definition and planning
2. Tracking model for gifts and redemptions
3. Monthly release and event scaffolding requirements
4. Server-authoritative distribution and circulation tracking requirements

## Out Of Scope Now

1. Account closure reclamation implementation
2. Full event gameplay design
3. Economy tuning, dynamic pack odds balancing, and anti-fraud policy details

## Acceptance Criteria For This Plan Document

1. Specifies Fellowship-only launch availability.
2. Specifies new user grant bundle: 1 gift booster choice, 5 booster choices, 1 starter deck choice.
3. Defines gift lifecycle and consumption tracking.
4. Defines server-authoritative inventory and card-circulation rules.
5. Defines monthly release plan through Set 19.
6. Defines release-event tracking direction.
7. Notes account closure circulation reclaim as future work only.
