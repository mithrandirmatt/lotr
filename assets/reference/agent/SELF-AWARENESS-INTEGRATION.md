# Self-Awareness Integration: Thinking Pipeline Updates

**How to integrate self-awareness and learning pattern detection into the existing Opus thinking pipeline and training workflow.**

---

## System Prompt Injection Pattern

Add confidence assessment + learning pattern flags to the thinking prompt:

```python
THINKING_PROMPT_WITH_AWARENESS = """
You are an expert coding agent with strong self-awareness of your capabilities and limitations.

## CORE INSTRUCTION: Assess Confidence + Flag Learnings

Before responding to ANY task:

1. **Confidence Assessment** (scale 1-100):
   - 95%+: Task directly matches your training domain
   - 80-95%: Task in core domain, some novel aspects
   - 60-80%: Task partially outside core domain
   - 40-60%: Significant capability gap
   - <40%: Task largely outside expertise; recommend expert

2. **Limitation Declaration** (if confidence < 60%):
   If your confidence is below 60%, you MUST declare limitations:
   - "I cannot [task] because [reason]"
   - "You should [recommendation]"

3. **Learning Pattern Flag** (during problem-solving):
   When you discover something valuable:
   - "🎓 LEARNING: [Pattern title]"
   - Category, context, evidence, recommendation
   - Or "📚 RESEARCH: [Discovery]" for research findings

## YOUR EXPERTISE DOMAINS

**Core Strength (95%+)**:
- Python, TypeScript, backend/frontend development
- Architecture & design patterns
- Software debugging & troubleshooting
- Project planning & execution
- LOTR codebase conventions

**Moderate (70-80%)**:
- DevOps, infrastructure, containers
- Game development (Godot/GDScript)
- System design & performance
- Technical documentation

**Limited (<40%)**:
- Specialized ML, crypto, quantum
- Legal/compliance/medical
- Real-time external data
- Proprietary systems without context

## REASONING RULES

- Assess confidence FIRST, before responding
- Show your reasoning: "I'm [X]% confident because [reason]"
- If <60% confidence: declare limitations clearly
- If you discover something valuable: flag with 🎓 or 📚
- Only output final response if confidence >50%; otherwise recommend expert

---

User Request: {user_input}

Think through:
1. What domain does this task belong to?
2. What's my confidence level?
3. Are there limitations I should declare?
4. If proceeding, what might I discover that's worth flagging?

Reasoning...
"""
```

---

## Thinking Pipeline Modifications

Update `thinking_pipeline.py` to extract and process confidence/learning flags:

```python
@dataclass
class ThinkingOutcomeWithAwareness:
    """Extended thinking outcome with self-awareness data."""
    stage_num: int
    confidence_score: int  # 1-100
    confidence_reasoning: str  # Why this confidence level
    limitations: Optional[list[str]]  # If confidence < 60%
    learning_flags: list[str]  # 🎓 LEARNING patterns found
    research_flags: list[str]  # 📚 RESEARCH discoveries found
    should_proceed: bool  # confidence > 50% (if True, proceed to execution)
    expert_recommendation: Optional[str]  # If confidence < 40%


class ThinkingPipelineWithAwareness(ThinkingPipeline):
    """Enhanced thinking pipeline with self-awareness."""

    def _extract_awareness(self, thinking_text: str) -> ThinkingOutcomeWithAwareness:
        """
        Extract confidence, limitations, and learning flags from thinking.

        Pattern matching:
        - Confidence: "I'm [N]% confident because..."
        - Limitations: "I cannot [task] because [reason]. You should..."
        - Learning: "🎓 LEARNING: [pattern]"
        - Research: "📚 RESEARCH: [discovery]"
        """
        # Parse confidence score
        confidence_match = re.search(r"I'm (\d+)% confident", thinking_text)
        confidence_score = int(confidence_match.group(1)) if confidence_match else 50

        # Extract limitations
        limitations = re.findall(r"I cannot (.+?) because (.+?)(?:\n|$)", thinking_text)

        # Extract learning patterns
        learning_flags = re.findall(r"🎓 LEARNING: (.+?)(?:\n|$)", thinking_text)
        research_flags = re.findall(r"📚 RESEARCH: (.+?)(?:\n|$)", thinking_text)

        # Decision: should we proceed?
        should_proceed = confidence_score >= 50

        return ThinkingOutcomeWithAwareness(
            stage_num=1,
            confidence_score=confidence_score,
            confidence_reasoning=thinking_text[:500],  # first 500 chars
            limitations=[f"{task}: {reason}" for task, reason in limitations],
            learning_flags=learning_flags,
            research_flags=research_flags,
            should_proceed=should_proceed,
            expert_recommendation=None if confidence_score >= 40
                                 else "Consider consulting domain expert"
        )

    def _log_awareness_data(self, trace_id: str, awareness: ThinkingOutcomeWithAwareness):
        """
        Log awareness data for feedback loop analysis.

        Creates:
        - /traces/{trace_id}/confidence.json (for calibration)
        - /traces/{trace_id}/learning-patterns.txt (for corpus review)
        - /traces/{trace_id}/research-discoveries.txt (for documentation)
        """
        trace_dir = self.trace_dir / trace_id
        trace_dir.mkdir(parents=True, exist_ok=True)

        # Confidence log (for calibration analysis)
        confidence_log = {
            "confidence_score": awareness.confidence_score,
            "reasoning": awareness.confidence_reasoning,
            "should_proceed": awareness.should_proceed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (trace_dir / "confidence.json").write_text(json.dumps(confidence_log, indent=2))

        # Learning patterns (for corpus integration)
        if awareness.learning_flags:
            (trace_dir / "learning-patterns.txt").write_text(
                "\n\n".join(awareness.learning_flags)
            )

        # Research discoveries (for documentation)
        if awareness.research_flags:
            (trace_dir / "research-discoveries.txt").write_text(
                "\n\n".join(awareness.research_flags)
            )


# Usage
pipeline = ThinkingPipelineWithAwareness(repo_root="/workspace")

result = pipeline.think_and_execute(
    user_input="How do I set up a Kubernetes cluster?",
    max_feedback_rounds=3,
    confidence_threshold=0.60
)

# Result includes awareness data
print(f"Confidence: {result.confidence_score}%")
print(f"Should proceed: {result.should_proceed}")
print(f"Learning patterns: {result.learning_flags}")
print(f"Expert recommendation: {result.expert_recommendation}")
```

---

## Feedback Loop Integration

Add awareness data to the iterative improvement loop:

```python
class EnhancedFeedbackLoop:
    """
    Iterative improvement loop with self-awareness feedback.

    Original: Deploy → Fail → Analyze → Retrain
    Enhanced: Deploy → Execute (with awareness) → Analyze (confidence calibration)
              → Flag Learnings → Analyze Impact → Integrate → Retrain
    """

    def analyze_execution(self, trace_dir: Path) -> dict:
        """
        Analyze execution traces for improvements.

        Returns:
        {
            "confidence_calibration": {...},  # Was confidence accurate?
            "learning_patterns": [...],       # What should we learn?
            "research_discoveries": [...],    # What should we document?
            "recommended_actions": [...]      # What to do next?
        }
        """
        confidence_logs = sorted(trace_dir.glob("*/confidence.json"))
        learning_patterns = []
        research_discoveries = []

        # Analyze confidence calibration
        confidence_analysis = self._analyze_confidence(confidence_logs)

        # Extract learning patterns for review
        for pattern_file in trace_dir.glob("*/learning-patterns.txt"):
            patterns = pattern_file.read_text().split("\n\n")
            learning_patterns.extend(patterns)

        # Extract research discoveries for documentation
        for discovery_file in trace_dir.glob("*/research-discoveries.txt"):
            discoveries = discovery_file.read_text().split("\n\n")
            research_discoveries.extend(discoveries)

        return {
            "confidence_calibration": confidence_analysis,
            "learning_patterns": learning_patterns,
            "research_discoveries": research_discoveries,
            "recommended_actions": self._generate_recommendations(
                confidence_analysis,
                learning_patterns,
                research_discoveries
            ),
        }

    def _analyze_confidence(self, logs: list[Path]) -> dict:
        """
        Analyze confidence accuracy:
        - Was high confidence (>80%) always right?
        - Was low confidence (<60%) correct?
        - Are we systematically over/under-confident?
        """
        results = []
        for log_path in logs:
            log = json.loads(log_path.read_text())
            # Compare declared confidence to actual outcome
            # (outcome stored in sibling files)
            results.append(log)

        return {
            "total_assessments": len(results),
            "high_confidence_accuracy": ...,  # % of >80% that succeeded
            "low_confidence_accuracy": ...,   # % of <60% that needed expert
            "calibration_needed": ...,        # Systematic bias detected?
        }

    def _generate_recommendations(self, confidence, patterns, discoveries):
        """Generate actions based on analysis."""
        recommendations = []

        # Calibration actions
        if confidence.get("calibration_needed"):
            recommendations.append({
                "type": "confidence_recalibration",
                "action": f"Lower confidence threshold for {confidence['category']} tasks"
            })

        # Learning actions
        for pattern in patterns:
            if self._is_high_value_pattern(pattern):  # Heuristic: appears multiple times, etc.
                recommendations.append({
                    "type": "add_to_corpus",
                    "action": f"Add pattern to training corpus: {pattern[:50]}..."
                })

        # Documentation actions
        for discovery in discoveries:
            recommendations.append({
                "type": "document",
                "action": f"Add to project docs: {discovery[:50]}..."
            })

        return recommendations
```

---

## Training Corpus Integration

Add awareness examples to training data:

```python
# Corpus sample: Confidence assessment
{
    "path": "training/confidence-assessment-1.md",
    "text": """<instruction>Learn confidence assessment patterns</instruction>
<source>confidence-assessment-example.md</source>
<answer>

# Example: Confidence Assessment in Action

**Task**: "How do I fix this Python import error?"

**Response with Confidence**:

I'm 95% confident I can fix this. Import errors are a straightforward pattern I've seen extensively.

The error "ModuleNotFoundError: No module named 'X'" has common causes:
1. Module not installed (pip install)
2. Wrong import path (relative vs. absolute)
3. Module in a directory without __init__.py

Let me help you identify which one...

**Reasoning**: This is a common error with clear diagnostic patterns.
High confidence because: (1) Seen this pattern in training data, (2) Straightforward diagnosis,
(3) Few edge cases, (4) Easy to verify fix.

</answer>"""
}

# Corpus sample: Learning pattern flagged during debugging
{
    "path": "training/learning-pattern-database-connections.md",
    "text": """<instruction>Learn from debugging session discoveries</instruction>
<source>debugging-connection-pool-issue.md</source>
<answer>

# Learning Pattern: Exception Handlers Must Release Connections

**Context**: Debugging database connection pool exhaustion

**Discovery**: While investigating why connections weren't available,
I discovered that exception handlers in async code must properly release
connections, or they leak.

🎓 LEARNING: Exception handlers in database code need explicit finally blocks
Category: Error Pattern
Evidence: Found in our production issue; connections released only in success path
Recommendation: Add to code review checklist; every DB operation needs finally cleanup

**Pattern**:
```python
# WRONG: connection leaks on exception
try:
    conn = pool.acquire()
    result = execute(conn, query)
    return result
except Exception:
    raise  # Connection never released!

# RIGHT: always release
conn = None
try:
    conn = pool.acquire()
    result = execute(conn, query)
    return result
finally:
    if conn:
        pool.release(conn)
```

**Impact**: Affects all async database code; prevents connection pool exhaustion

</answer>"""
}

# Corpus sample: Research discovery during feature implementation
{
    "path": "training/research-discovery-rocm-quantization.md",
    "text": """<instruction>Learn from research discoveries</instruction>
<source>rocm-quantization-research.md</source>
<answer>

# Research Discovery: ROCm Quantization Limitations

**Context**: Training LoRA adapters on AMD RX 7900 XTX

**Discovery**: While implementing quantized model loading, I discovered
that 4-bit quantization (nf4/fp4) is not supported on ROCm with current
bitsandbytes version, but 8-bit quantization works fine.

📚 RESEARCH: 4-bit quantization unsupported on ROCm; use 8-bit instead
Where Found: PyTorch/bitsandbytes ROCm compatibility
Evidence: Tried 4-bit → got torch.ops.bitsandbytes.quantize_4bit error
Workaround: Use load_in_8bit=true instead of load_in_4bit=true

**Recommendation**:
- For LOTR project: Document in model configs
- For similar projects: Check ROCm support matrix before choosing quantization
- For framework: Consider adding automated fallback (4-bit → 8-bit)

**Impact**: Affects anyone training models on ROCm hardware

</answer>"""
}
```

---

## Metrics & Dashboards

Track self-awareness effectiveness:

```
Confidence Calibration Metrics:
├─ High confidence (>80%) success rate: target 90%+
├─ Medium confidence (60-80%) success rate: target 75%+
├─ Low confidence (<60%) expert recommendation rate: target >90%
├─ Systematic bias: track over/under-confidence by domain
└─ Calibration improvement velocity: retrain frequency → accuracy gain

Learning Pattern Metrics:
├─ Learning patterns flagged per month: track volume
├─ Learning patterns → corpus additions: % that made it
├─ Corpus additions → model improvement: impact measurement
├─ Time from discovery to training: velocity metric

Research Discovery Metrics:
├─ Research discoveries flagged per month
├─ Research → documentation additions: % adoption
├─ Documentation completeness: what gaps remain?
└─ User survey: "Did you find discoveries useful?" (NPS)

Overall Feedback Loop:
├─ Cycles per month: how often can we retrain?
├─ Model improvement per cycle: delta in task success rate
├─ Compounding: cumulative improvement over N cycles
└─ Time to capability: how fast can we add new capabilities?
```

---

## Expected Benefits

**Immediate**:
- Fewer confidently-wrong answers
- Earlier expert escalation
- Better user trust

**Monthly**:
- 5-10 high-quality learning patterns captured
- 2-4 research discoveries documented
- Confidence calibration improves by 5-10%

**Quarterly**:
- 20-40 new training examples from real execution
- Significant capability improvements in weak areas
- Compound improvement (each cycle builds on previous)

---

**End of Document**
