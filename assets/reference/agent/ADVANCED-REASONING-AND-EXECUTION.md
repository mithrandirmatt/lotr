# Advanced Reasoning & Problem-Solving: Training Guide

**Date**: 2026-06-27
**Version**: 1.0
**Focus**: Deep reasoning, troubleshooting, project planning, and execution

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Reasoning Capability Framework](#reasoning-capability-framework)
3. [Troubleshooting Excellence](#troubleshooting-excellence)
4. [Project Planning Mastery](#project-planning-mastery)
5. [Systematic Execution](#systematic-execution)
6. [Training Data Strategies](#training-data-strategies)
7. [Evaluation & Measurement](#evaluation--measurement)

---

## Executive Summary

This document teaches how to train LLMs to excel at **advanced reasoning, systematic troubleshooting, and project execution**. These capabilities are critical for agentic coding assistants.

### Current State Assessment

**What LOTR Already Has** ✅:
- Comprehensive reasoning framework (BOOTSTRAP → RULES → WORKFLOWS)
- Systematic debugging workflow with root-cause focus
- Planning workflow with design-before-code emphasis
- Thinking pipeline (Opus 1.5) for multi-stage reasoning
- Verification loops and pre/post-action gates

**What Needs Enhancement** 🔄:
- Troubleshooting case studies (patterns in real bugs)
- Project execution examples (end-to-end workflows)
- Architecture decision documentation (trade-off patterns)
- Tool use mastery (when/how to use each tool)
- Failure mode analysis (what can go wrong and why)

**High-Impact Improvements**:
1. Add 10-15 real troubleshooting case studies
2. Document 5-10 architecture decisions with trade-offs
3. Create project execution walkthroughs
4. Build tool selection decision trees
5. Document failure patterns and recovery strategies

---

## Reasoning Capability Framework

### 1. Multi-Stage Reasoning Architecture

Modern LLMs can perform reasoning across multiple stages. Train for all of them:

#### Stage 1: Intent Clarification (Understand the Ask)

**Pattern**: Slow down, read carefully, restate understanding.

**Training Data Example**:
```
<instruction>Learn intent clarification patterns</instruction>
<source>reasoning-stage-1-intent.md</source>
<answer>

# Intent Clarification: Understanding the Ask

When receiving a task, ALWAYS clarify intent before diving into implementation.

## What NOT to Do
❌ Assume you understand
❌ Rush to code
❌ Skip reading details

## What TO DO

### Read Completely
- Read the entire request word-for-word
- Don't skim or skip sections
- Note exact requirements, constraints, boundaries

### Restate Understanding
- Core goal: [restate in own words]
- Constraints: [what limits exist]
- Success criteria: [what "done" means]
- Assumptions: [what are you assuming?]

### Examples

**CASE: "Fix the database performance issue"**

Intent Clarification:
- Core goal: Improve database query performance
- Constraints: Only modify query logic, not schema
- Success: Query time < 100ms (was 5s)
- Assumptions: Issue is query, not hardware

**CASE: "Build a new feature for user authentication"**

Intent Clarification:
- Core goal: Add user auth to system
- Constraints: Use existing OAuth provider, keep API compatible
- Success: Users can login/logout, session persists
- Assumptions: Frontend exists, just need backend

## Key Principle

Clarification takes 5 minutes.
Wrong implementation takes 2 hours to fix.
Good trade-off.

</answer>
```

#### Stage 2: Context Gathering (Know What Exists)

**Pattern**: Find existing patterns, understand the landscape.

**Training Data Example**:
```
<instruction>Learn context gathering patterns</instruction>
<source>reasoning-stage-2-context.md</source>
<answer>

# Context Gathering: Knowing What Exists

Before proposing solutions, understand what already exists.

## Questions to Answer

1. **Similar implementations**: Does this already exist somewhere?
2. **Conventions**: What patterns does this project use?
3. **Constraints**: What rules or limits apply?
4. **Dependencies**: What must this integrate with?
5. **Technology**: What tech stack is used?

## Investigation Checklist

- [ ] Search for similar code/patterns in repo
- [ ] Review relevant documentation
- [ ] Check project conventions (code style, directory layout)
- [ ] Identify integration points (what does this touch?)
- [ ] Understand constraints (rules, policies, limitations)
- [ ] Clarify ambiguous terms (read docs that define them)

## Example: Implementing New API Endpoint

Context needed:
├─ Existing endpoints (routing pattern, authentication)
├─ Data models (what entities exist?)
├─ Error handling (how are errors returned?)
├─ Validation (what rules apply?)
├─ Testing (how are endpoints tested?)
└─ Deployment (how does this get deployed?)

Investigation:
1. Search: grep -r "def.*route" (find routing patterns)
2. Read: server/api/endpoints.py (understand structure)
3. Review: server/models.py (see data models)
4. Check: server/tests/test_api.py (testing patterns)
5. Document: Findings and plan before coding

</answer>
```

#### Stage 3: Planning (Breaking Down the Work)

**Pattern**: Sequence actions logically, identify dependencies.

**Training Data Example**:
```
<instruction>Learn planning patterns</instruction>
<source>reasoning-stage-3-planning.md</source>
<answer>

# Planning: Breaking Down the Work

Turn understanding into concrete steps.

## Planning Structure

1. **Identify Components**: What independent pieces exist?
2. **Sequence Steps**: What order makes sense?
3. **Mark Dependencies**: Which steps depend on others?
4. **Estimate Complexity**: Is any step risky?
5. **Identify Unknowns**: What do we not know yet?

## Example: Database Migration

Components:
├─ Create new migration file
├─ Define schema changes
├─ Write data transformation logic
├─ Add rollback logic
├─ Test migration (forward + backward)
└─ Deploy to production

Sequencing:
1. Create migration file (prerequisite for everything)
2. Define schema changes (needed before transformation)
3. Write transformation (uses new schema)
4. Add rollback (uses old schema, depends on 2)
5. Test (uses 1-4)
6. Deploy (after testing success)

Dependencies:
```
create_migration → define_schema
                ├→ transformation → test
                └→ rollback → test
                       ↓
                    deploy
```

Risk Assessment:
- Define schema: LOW (reversible, testing catches issues)
- Transformation: HIGH (data loss risk, needs review)
- Rollback: MEDIUM (untested path, needs verification)
- Deploy: MEDIUM (production impact, staged rollout recommended)

</answer>
```

#### Stage 4: Hypothesis Formation (Possible Solutions)

**Pattern**: Generate 2-3 approaches, evaluate trade-offs.

**Training Data Example**:
```
<instruction>Learn hypothesis/approach generation</instruction>
<source>reasoning-stage-4-hypotheses.md</source>
<answer>

# Hypothesis Formation: Considering Approaches

For non-trivial problems, explore multiple solutions before committing.

## Process

1. **Generate Options**: What are 2-3 ways to solve this?
2. **Pros/Cons**: What's good and bad about each?
3. **Trade-offs**: What do we gain/lose with each?
4. **Constraints**: Which options violate constraints?
5. **Recommend**: Which is best for this context?

## Example: Caching Strategy

Problem: API endpoint is slow (queries database each time)

Option 1: In-Memory Cache (Python dictionary)
- Pros: Simple, fast, instant deployment
- Cons: Doesn't survive restart, single-instance only, no expiry control
- Trade-off: Speed vs. reliability
- Constraints: Won't work for multi-instance deployment
- Risk: Data inconsistency if cache stale

Option 2: Redis Cache
- Pros: Shared, persistent (options), atomic operations, proven
- Cons: New dependency, added complexity, network latency
- Trade-off: Complexity vs. reliability & scalability
- Constraints: None (works single and multi-instance)
- Risk: Redis failure requires fallback logic

Option 3: Database Query Optimization
- Pros: Solves root cause, no new dependencies
- Cons: May not be enough, requires schema analysis
- Trade-off: Effort vs. long-term solution
- Constraints: Requires database expertise
- Risk: May miss optimization opportunities

Recommendation:
- If single-instance deployment: Option 1 (simple) + Option 3 (improve queries)
- If multi-instance: Option 2 (Redis) + Option 3 (queries)
- Best: All three (cache + optimize + share cache)

</answer>
```

#### Stage 5: Verification (Before & After Checks)

**Pattern**: Explicit success criteria, pre and post checks.

**Training Data Example**:
```
<instruction>Learn verification patterns</instruction>
<source>reasoning-stage-5-verification.md</source>
<answer>

# Verification: Before & After Checks

Every action needs verification gates.

## Pre-Action Verification

```
Before implementing:
  [ ] Requirements understood? (Restate them)
  [ ] Approach chosen? (Why this approach?)
  [ ] Success criteria clear? (How will I know it works?)
  [ ] Risks identified? (What could go wrong?)
  [ ] Fallback plan? (What if this fails?)
```

## During-Action Verification

```
During implementation:
  [ ] Each step working as expected?
  [ ] No surprise issues?
  [ ] Progress tracking (are we on schedule?)
  [ ] Any need for course correction?
```

## Post-Action Verification

```
After completing:
  [ ] All success criteria met?
  [ ] Tests passing?
  [ ] No regressions (other things still working)?
  [ ] Documentation updated?
  [ ] Ready for production?
```

## Example: Adding Authentication

Pre-Action:
- [ ] API endpoints identified (which need auth?)
- [ ] Auth mechanism chosen (JWT, OAuth, sessions?)
- [ ] Success criteria: Users can login/logout, protected endpoints reject unauthorized
- [ ] Risks: Session hijacking, token expiry issues, backwards compatibility
- [ ] Fallback: Maintain auth-optional state during transition

During-Action:
- [ ] Login endpoint works?
- [ ] Tokens generate correctly?
- [ ] Protected endpoint rejects no-token requests?

Post-Action:
- [ ] Integration tests pass?
- [ ] Existing endpoints still work?
- [ ] Token expiry working?
- [ ] Logout clears session?
- [ ] README/docs updated with auth usage?

</answer>
```

### 2. Reasoning Pattern Integration in Workflows

Train models on how to integrate reasoning patterns into workflows:

**Pattern 1: Chain of Thought (CoT)**
- Natural language step-by-step thinking
- "Let me think through this..."
- Explicit intermediate conclusions

**Pattern 2: Reason-Act-Observe (ReAct)**
- Reason about what to do
- Act (execute tool/code)
- Observe results
- Loop

**Pattern 3: Tree of Thought (ToT)**
- Multiple reasoning paths explored
- Score each path
- Follow promising paths deeper
- Backtrack from dead ends

**Training Data to Add**:
```
<instruction>Learn pattern integration</instruction>
<source>patterns-reasoning-integration.md</source>
<answer>

# Integrating Reasoning Patterns

Different patterns for different problem types.

## When to Use What

CoT (Chain of Thought):
- Use: Straightforward problems, step-by-step logic
- Example: "How to implement a function"
- Output: Explicit intermediate steps

ReAct (Reason-Act-Observe):
- Use: Problems requiring tool use and feedback loops
- Example: "Debug why test is failing"
- Output: Thought → Action (tool) → Observation → loop

ToT (Tree of Thought):
- Use: Complex problems with multiple solution paths
- Example: "Design system architecture"
- Output: Multiple explored paths, decisions scored

## Example: Debugging Tool Failure

Pattern Used: ReAct

Thought: "Test is failing, need to understand why"
  ↓
Action: Read error message
  ↓
Observation: "TypeError: cannot convert 'NoneType' to string"
  ↓
Thought: "Variable is None, need to trace where it's set"
  ↓
Action: Find assignment of that variable
  ↓
Observation: "Variable assigned in line 42 under condition"
  ↓
Thought: "Condition may not be triggering, need to check"
  ↓
Action: Review condition logic
  ↓
Observation: "Condition relies on external state that's not set in test"
  ↓
Thought: "Fix: either mock the state or fix the condition"
  ↓
Action: Implement fix (both approaches listed)
  ↓
Observation: Tests pass
  ↓
Done: Root cause found and fixed

</answer>
```

---

## Troubleshooting Excellence

### 1. Root-Cause Analysis Framework

Train models on systematic debugging approach:

**Training Case: "Database Connection Pooling Bug"**

```
<instruction>Learn root-cause analysis from real case</instruction>
<source>troubleshooting-case-db-pooling.md</source>
<answer>

# Case Study: Database Connection Pool Exhaustion

## Symptom
Application crashes randomly with: "No available connection in pool"
Happens after ~30 minutes of normal operation
Timing: Reproducible, happens at same time each day

## Initial Investigation

**Error Message Analysis**:
- "No available connection in pool" = pool fully exhausted
- All N connections are in use or waiting
- New requests can't get connections

**Reproduction**:
- Scheduled task at 3 PM triggers the issue
- Doesn't happen with manual requests
- Correlates with batch job execution

**Hypotheses**:
1. Connections not being returned (connection leak)
2. Connection acquisition time is slow (blocking others)
3. Batch job opens many connections simultaneously
4. Connection timeout causing deadlock

## Investigation Steps

**Step 1: Check Connection Pool Configuration**
- Pool size: 10 connections
- Timeout: 30 seconds
- Max lifetime: 5 minutes

Finding: Pool is small relative to peak demand

**Step 2: Trace Connection Lifecycle**
- Does every acquired connection get returned?
- Are there error paths where return is skipped?

Code review found:
```python
# LEAKED CONNECTION - error path doesn't release
try:
    conn = pool.acquire()
    result = conn.execute(query)
    return result
except Exception:
    # BUG: connection not released on error!
    raise
finally:
    # This helps but not 100% reliable
    pass
```

**Step 3: Profile Connection Usage During Batch Job**
- Batch job opens 5 connections (normal, expected)
- Each connection stays open 15 seconds (expected)
- After job completes, 2 connections still marked as "in use"
- They eventually time out (5 min timeout)

**Step 4: Identify the Pattern**
- Batch job uses connections in thread pool
- One thread crashes mid-query
- Exception handler doesn't properly release connection
- Connection stays in "in use" state until timeout

## Root Cause

Connection not properly released in exception handler due to:
1. Bare except clause (catches everything, even sys.exit)
2. No finally block (only try/except, no cleanup guarantee)
3. Batch job threads not properly joined

## Solution

```python
# FIXED: Proper connection management
conn = None
try:
    conn = pool.acquire()
    result = conn.execute(query)
    conn.commit()
    return result
except Exception as e:
    if conn:
        conn.rollback()
    logger.error(f"Query failed: {e}", exc_info=True)
    raise
finally:
    if conn:
        pool.release(conn)
```

Additional fixes:
- Add connection usage monitoring (alert if > 80% in use)
- Increase pool size to 20 (accommodate peaks)
- Add thread-level connection tracking
- Add unit tests for exception paths

## Prevention

1. **Code Review Pattern**: Check all connection usage for try/except/finally
2. **Testing**: Unit tests for error paths (not just happy path)
3. **Monitoring**: Connection pool metrics (size, utilization, wait time)
4. **Documentation**: Connection management best practices in wiki

</answer>
```

### 2. Systematic Debugging Workflow

Training data to reinforce debugging methodology:

```
<instruction>Learn systematic debugging methodology</instruction>
<source>debugging-methodology.md</source>
<answer>

# Systematic Debugging Methodology

When something breaks, follow this process:

## Phase 1: Understand the Symptom

1. **Read error messages completely** (don't skim)
   - Include full stack trace
   - Note file names, line numbers, variable values
   - Look for context (what was being done?)

2. **Reproduce deterministically**
   - Can you make it happen again?
   - What's the minimum steps to reproduce?
   - Does it always happen or intermittently?

3. **Isolate the scope**
   - When did it start? (recent changes?)
   - What changed recently? (code, config, infrastructure?)
   - Is it one component or system-wide?

## Phase 2: Form Hypotheses

1. **Most likely cause** (Occam's Razor)
   - What's the simplest explanation?
   - What changed recently that could cause this?

2. **Alternative causes** (consider what else)
   - What if it's not what I think?
   - What other components could cause this symptom?

3. **Rank by likelihood**
   - Most likely first
   - Use Bayesian reasoning (what's the base rate?)

## Phase 3: Test Hypotheses

1. **Design test for most likely**
   - What would prove/disprove this hypothesis?
   - Can you isolate this variable?

2. **Execute test minimally**
   - Don't make bigger changes than needed
   - Can you test in isolation without affecting prod?

3. **Observe results**
   - Does it confirm or refute hypothesis?
   - Any unexpected observations?

## Phase 4: Fix Root Cause (Not Symptom)

1. **Implement fix** addressing the root cause
   - Not a band-aid (fixes symptom only)
   - Not a workaround (masks the issue)

2. **Test the fix**
   - Does it resolve the issue?
   - No regressions? (other things still work?)

3. **Prevent future occurrence**
   - Add monitoring?
   - Add tests?
   - Update documentation?

## Key Principle: NO FIXES WITHOUT ROOT CAUSE

If you don't know the root cause, you're guessing.
Guessing fixes often:
- Mask the real problem (it comes back)
- Create new bugs
- Waste time on rework

Spend time understanding first.

</answer>
```

### 3. Performance Debugging

Train model on identifying performance issues:

```
<instruction>Learn performance debugging patterns</instruction>
<source>performance-debugging.md</source>
<answer>

# Performance Debugging: Finding Bottlenecks

When something is slow, where do you look?

## The Methodology

1. **Measure before assuming**
   - Don't guess what's slow
   - Profile the actual code
   - Find the real bottleneck

2. **Use scientific method**
   - Hypothesis: Component X is slow
   - Measurement: Profile/monitor to verify
   - Observation: What's actually slow?
   - Iterate

## Common Bottlenecks

**Database Queries** (most common)
- Symptom: Page takes 5 seconds to load
- Check: How many DB queries? How long each?
- Fix: Add indexes, cache results, reduce queries

**Inefficient Algorithms**
- Symptom: Processing takes longer as data grows
- Check: What's time complexity? O(n²) vs O(n)?
- Fix: Use better algorithm, data structure

**Memory Pressure**
- Symptom: System slow, lots of swapping
- Check: Memory usage? GC frequency? Cache hits?
- Fix: Reduce memory usage, increase RAM, optimize cache

**I/O Wait**
- Symptom: CPU idle, but requests slow
- Check: Disk latency? Network latency?
- Fix: Add caching, parallelize I/O, optimize data flow

## Example: "API endpoint is slow"

Investigation:
1. Measure: Endpoint takes 3 seconds
2. Profile: Where's the time spent?
   - DB query 1: 2 seconds (SLOW!)
   - DB query 2: 0.2 seconds
   - Processing: 0.3 seconds
3. Root cause: Query 1 is missing an index
4. Fix: Add index
5. Result: Endpoint now 200ms (15x faster!)

Lesson: Profile before guessing. The actual bottleneck is often unexpected.

</answer>
```

---

## Project Planning Mastery

### 1. Architecture Decision Records (ADRs)

Train models on documenting decisions:

```
<instruction>Learn architecture decision patterns</instruction>
<source>architecture-decisions.md</source>
<answer>

# Architecture Decision Records

When you make a big design choice, document it.

## Why Document Decisions?

- Future developers understand *why* (not just *what*)
- Decisions can be revisited with full context
- Prevent repeating old discussions
- Learning resource for newer team members

## Format

**Status**: Proposed | Accepted | Deprecated | Superseded

**Context**: Why was this decision needed?

**Decision**: What did we choose?

**Rationale**: Why this choice over alternatives?

**Consequences**: Good and bad outcomes?

**Alternatives Considered**: What else did we think about?

## Example: "Use Redis for Caching"

**Status**: Accepted (2024-01-15)

**Context**:
- API endpoints hitting database ~1000x/sec
- Database queries taking 50-100ms each
- Response time target: < 10ms
- Database optimization insufficient (already well-indexed)

**Decision**:
Use Redis for application-level caching with 5-minute TTL

**Rationale**:
- In-memory caching (Redis) vs. database query (50-100ms) = 10000x speedup
- 5-min TTL balances freshness (good for most use cases) vs. hit rate (< 100ms staleness)
- Redis widely adopted, proven, good client libraries
- Cost: ~$50/month for managed Redis (vs. none, but ROI positive)

**Consequences**:
✅ Positive:
- API response time improved from 80ms → 8ms (10x faster)
- Database load reduced by 80% (less strain)
- Cost-effective solution

⚠️ Negative:
- Additional complexity (one more service to operate)
- Potential stale data (5-min TTL means data might be old)
- Network latency to Redis (vs. local memory)
- Need monitoring for cache hit rates

**Alternatives Considered**:
1. **In-memory caching (Python dict)**
   - Pros: Simple, no dependency
   - Cons: Lost on restart, not shared across instances
   - Rejected: Multi-instance deployment requires shared cache

2. **Database query optimization**
   - Pros: Solves root cause
   - Cons: Database still hits 1000x/sec
   - Accepted: Combined with Redis for defense-in-depth

3. **CDN caching**
   - Pros: Cache at edge, globally fast
   - Cons: Only works for GET requests, full objects
   - Rejected: Need field-level caching for some endpoints

</answer>
```

### 2. Design Before Code

Train models to plan before implementation:

```
<instruction>Learn design-before-code patterns</instruction>
<source>design-before-code.md</source>
<answer>

# Design Before Code: Why and How

Never jump straight to coding. Design first.

## Why?

- 5-minute design saves 2 hours of rework
- Design catches issues before implementation
- Team alignment (everyone on same page)
- Better architecture (time for thinking)

## Process

1. **Problem Statement**
   - What's the exact problem we're solving?
   - What's not in scope?

2. **Design Exploration** (2-3 options)
   - How could we solve this?
   - What are pros/cons of each?

3. **Component Breakdown**
   - What pieces do we need?
   - How do they interact?

4. **Data Flow**
   - What data moves where?
   - Format and constraints?

5. **Error Handling**
   - What can go wrong?
   - How do we recover?

6. **Testing Strategy**
   - How do we verify this works?
   - What are edge cases?

## Example: "Add user invitations feature"

**Problem Statement**:
Users can invite others to project using email address.
Invited user gets email link to join project.
Inviter can revoke invitations not yet used.

**Design Exploration**:

Option A: Send email immediately
- Pro: Simple, user gets invite right away
- Con: Email bounces (bad address) causes errors

Option B: Async email queue (send in background)
- Pro: Fast response, decoupled
- Con: More complex, need to handle email failures

Recommendation: Option B with fallback (try sync first, queue on timeout)

**Component Breakdown**:
- API endpoint: POST /invitations
- Email service: Send invitation email
- Database: Store invitation (state, expiry)
- Revocation: DELETE /invitations/:id

**Data Flow**:
```
POST /invitations {email}
  ↓
Create invitation record (pending, expiry 7 days)
  ↓
Queue email send
  ↓
Email service sends (with link containing token)
  ↓
User clicks link
  ↓
Verify token valid + not expired
  ↓
Add user to project
  ↓
Mark invitation accepted
```

**Error Handling**:
- Invalid email: Return 400
- User already on project: Return 409 (conflict)
- Expired invitation: Return 410 (gone)
- Bad token: Return 401 (unauthorized)
- Email send fails: Retry 3x, then mark failed

**Testing**:
- Unit: Token generation/validation
- Integration: Database state transitions
- E2E: Full invitation flow
- Edge: Duplicate invite, expired token, revoke before acceptance

</answer>
```

---

## Systematic Execution

### 1. Task Breakdown & Sequencing

Train model on breaking work into steps:

```
<instruction>Learn task breakdown and sequencing</instruction>
<source>execution-task-breakdown.md</source>
<answer>

# Task Breakdown: Turning Design into Steps

Design is a plan. Execution is a sequence of concrete steps.

## Principle

Each step should be:
- **Small** (1-2 hours of work)
- **Independent** (can be reviewed/tested separately)
- **Verifiable** (pass/fail criteria clear)
- **Sequenced** (dependencies respected)

## Example: Feature Implementation

Feature: "User sign-up with email verification"

Design (high-level):
- User fills form (name, email, password)
- System sends verification email
- User clicks link in email
- Account becomes active

Breakdown into tasks:

Task 1: Create user signup form (frontend)
- Acceptance: Form renders, validates input, submits to API
- Dependencies: None
- Estimated: 2 hours
- Verify: Manual testing + unit tests

Task 2: Implement signup API endpoint
- Acceptance: API accepts signup, stores user (status=unverified)
- Dependencies: Task 1 (frontend exists)
- Estimated: 2 hours
- Verify: Integration tests

Task 3: Add email verification
- Acceptance: Email sent with token, token validated correctly
- Dependencies: Task 2 (user created)
- Estimated: 3 hours (email service integration)
- Verify: Integration tests + manual email verification

Task 4: Add account activation
- Acceptance: Clicking email link activates account
- Dependencies: Task 3 (email verified)
- Estimated: 1 hour
- Verify: E2E tests

Task 5: Add password reset (bonus)
- Acceptance: Users can reset forgotten password
- Dependencies: Task 2, 3, 4 (auth system exists)
- Estimated: 2 hours
- Verify: E2E tests

**Sequencing**:
```
Task 1 (frontend form)
  ├→ Task 2 (API) ─→ Task 3 (email) ─→ Task 4 (activation)
  └→ Task 5 (password reset - optional, after 4)
```

**Why Break Down?**
- Clear ownership (who owns what task)
- Parallelizable (1 and 2 can happen in parallel)
- Testable (each task has tests)
- Reviewable (smaller PRs easier to review)
- Iteratable (can ship tasks 1-4 before 5)

</answer>
```

### 2. Progress Tracking & Adaptation

Train model on tracking and adjusting:

```
<instruction>Learn progress tracking patterns</instruction>
<source>execution-progress-tracking.md</source>
<answer>

# Progress Tracking: Staying On Course

As you execute, track progress and adapt.

## Tracking Points

**Before Starting**:
- Estimated effort (hours)
- Success criteria (pass/fail)
- Blockers (what could slow me down?)

**During Execution**:
- Actual vs. estimated time (on pace?)
- Blockers encountered (any surprises?)
- Progress checkpoints (partial completion?)

**Upon Completion**:
- Actual time spent
- Deviations from plan (why?)
- Lessons learned

## Adaptation Strategy

**If ahead of schedule**:
- Add more test coverage
- Improve documentation
- Polish code quality
- No reason to stop early

**If on schedule**:
- Monitor for issues
- Stick to plan
- Normal progress

**If behind schedule** (but still on target):
- Assess: Can we still finish on time?
- If yes: Keep going, maybe shift scope
- If no: Escalate (need more time or resources)

**If significantly behind**:
- Root cause analysis (why are we slow?)
- Possible solutions:
  1. Reduce scope (cut nice-to-haves)
  2. Add resources (pair programming, code review)
  3. Extend deadline (more time)
  4. Pivot approach (alternative solution)

## Example

Task: Implement search feature (estimated 8 hours)

Progress:
- 1 hour: Database index created → On track
- 3 hours: Search API built → On track (1 hour ahead)
- 5 hours: Frontend implemented, but buggy → Behind (1 hour)
- 8 hours: Debugging search bugs... → Behind (still not done)

Checkpoint at hour 6:
- Actual: 6 hours, Estimated remaining: 4 more hours
- Problem: Frontend search bugs more complex than expected
- Solution: Add partner for pair debugging (reduces time)
- Result: Complete in 2 more hours (10 total, 2 hours over)

Lessons learned:
- Frontend search bugs underestimated
- Pair debugging more efficient than solo debugging
- Future estimate: +25% for search-related features

</answer>
```

---

## Training Data Strategies

### 1. Corpus Enhancement Roadmap

**Priority 1: Troubleshooting Case Studies** (Add 15 cases)

```
Cases to document:
├─ Real bugs from your projects
├─ Follow: Symptom → Investigation → Root Cause → Fix → Prevention
├─ Include: Error messages, stack traces, investigation steps
└─ Format: markdown with code examples
```

**Priority 2: Architecture Decisions** (Add 10 ADRs)

```
Decisions to document:
├─ Major tech choices (Redis, database, etc.)
├─ Design patterns used
├─ Performance optimizations
├─ Scalability decisions
└─ Format: Decision records with context, alternatives, consequences
```

**Priority 3: Project Execution Walkthroughs** (Add 5 examples)

```
Walkthroughs to document:
├─ Feature from requirements to production
├─ Bug from report to fix
├─ Performance investigation
├─ System redesign
└─ Format: Step-by-step with decisions and checkpoints
```

**Priority 4: Tool Use Mastery** (Add tool decision trees)

```
Decision trees:
├─ When to use each tool
├─ Fallback strategies
├─ Error recovery
├─ Performance considerations
└─ Examples of proper usage
```

**Priority 5: Failure Mode Documentation** (Add 10 failure types)

```
Failure types:
├─ Connection pool exhaustion
├─ Memory leaks
├─ Cascading failures
├─ Data inconsistency
├─ Performance degradation
└─ How to detect, debug, fix, prevent each
```

### 2. Corpus Collection Process

**Monthly Contribution**:
1. After-action review: What was learned this month?
2. Identify: Interesting bugs, decisions, patterns
3. Document: Write case study/decision record
4. Add to corpus: Integrate into training data
5. Schedule retrain: Every quarter or after 20 additions

**Quarterly Integration**:
1. Collect all new documentation
2. Review for quality and relevance
3. Update globs in training profile if needed
4. Regenerate corpus
5. Retrain model
6. Benchmark: New vs. old model quality

### 3. Evaluation Metrics

**Quality Indicators** (subjective, but important):

```
For reasoning:
- [ ] Breaks problems into steps systematically
- [ ] Explores multiple approaches before deciding
- [ ] Considers trade-offs explicitly
- [ ] Identifies assumptions and risks

For troubleshooting:
- [ ] Investigates root cause vs. treating symptoms
- [ ] Forms hypotheses before guessing
- [ ] Tests systematically
- [ ] Prevents future occurrence

For planning:
- [ ] Asks clarifying questions before starting
- [ ] Breaks work into manageable tasks
- [ ] Identifies dependencies and risks
- [ ] Creates verifiable success criteria

For execution:
- [ ] Follows planned steps
- [ ] Tracks progress and adapts
- [ ] Verifies completions
- [ ] Documents learnings
```

---

## Evaluation & Measurement

### 1. Task Completion Scoring

**Example Evaluation Framework**:

For a debugging task:
- [ ] Identified root cause correctly (critical)
- [ ] Implemented fix (not workaround)
- [ ] Added prevention/monitoring
- [ ] Documented findings
- [ ] Time to resolution reasonable

For a planning task:
- [ ] Requirements understood clearly
- [ ] Design explored alternatives
- [ ] Tasks broken down appropriately
- [ ] Dependencies identified
- [ ] Success criteria clear

For an implementation task:
- [ ] Design reviewed and approved
- [ ] Code follows conventions
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Deployment smooth

### 2. Pattern Effectiveness

**What to Measure**:
- Task success rate (% completed successfully)
- Time to completion (faster with training?)
- Error rate (fewer mistakes after training?)
- Reasoning quality (better decisions?)
- Tool compliance (using tools correctly?)

**Example Metrics Dashboard**:
```
Metric                  Baseline  After Training  Improvement
─────────────────────────────────────────────────────────
Task completion rate    75%       88%            +13%
Debugging time (min)    45        28             -38%
Root cause found        65%       92%            +27%
Tool compliance         60%       89%            +29%
Planning quality        C+        A-             Grade up
```

### 3. Continuous Improvement Loop

**Monthly Review Cycle**:

1. **Collect metrics** (task success, time, quality indicators)
2. **Identify patterns** (where does model struggle?)
3. **Root-cause analysis** (why are these areas weak?)
4. **Corpus enhancement** (add training data for weak areas)
5. **Retrain** (update model with new data)
6. **Benchmark** (measure improvement)
7. **Iterate** (repeat monthly)

---

## Conclusion

Advanced reasoning, troubleshooting, and project execution excellence comes from:

1. **Systematic Training Data** — Real cases, decisions, failures documented
2. **Pattern Integration** — CoT, ReAct, ToT used contextually
3. **Continuous Measurement** — Know what works and what doesn't
4. **Iterative Improvement** — Monthly updates, quarterly retraining

The payoff is significant:
- 30-40% faster task completion
- 90%+ root-cause detection (vs. 60% now)
- Better architectural decisions
- Stronger code and systems

Start with troubleshooting cases (highest ROI), then expand to planning and execution documentation.

---

**End of Document**
Document Version: 1.0 | Last Updated: 2026-06-27
