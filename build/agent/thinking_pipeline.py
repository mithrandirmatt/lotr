#!/usr/bin/env python3
"""
Opus 1.5 Thinking Pipeline Integration

Integrates Opus 1.5 (reasoning/thinking) with execution models (Qwen).
- Opus generates thinking context via system prompt injection
- Execution model (Qwen) responds to chat
- Feedback loop: Up to 3 rounds if confidence < 0.8
- Full trace logging for analysis
- VS Code Copilot compatible (only execution model response visible)
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ThinkingStage:
    """Single thinking iteration in the pipeline."""
    stage_num: int
    thinking_prompt: str
    thinking_response: str
    confidence: float
    key_insights: list[str]
    timestamp: str


@dataclass
class ThinkingTrace:
    """Complete thinking pipeline trace for debugging/analysis."""
    trace_id: str
    user_input: str
    timestamp: str
    thinking_stages: list[ThinkingStage]
    final_response: str
    final_confidence: float
    total_rounds: int
    breakout_reason: str  # "confidence_met", "round_limit", "error"


class ThinkingPipeline:
    """
    Orchestrates Opus thinking + execution model flow.

    Architecture:
    1. User input
    2. Opus 1.5 thinking (reasoning)
    3. System prompt injection: "Based on this analysis: [thinking]"
    4. Qwen execution (response generation)
    5. Confidence check
    6. Optional feedback loop (max 3 rounds)
    7. Return response to chat
    8. Log full trace
    """

    def __init__(
        self,
        repo_root: Path,
        thinking_model: str = "opus-1.5",
        execution_model: str = "qwen25-coder-14b",
        max_feedback_rounds: int = 3,
        confidence_threshold: float = 0.8,
        trace_dir: Optional[Path] = None,
    ):
        self.repo_root = Path(repo_root)
        self.thinking_model = thinking_model
        self.execution_model = execution_model
        self.max_feedback_rounds = max_feedback_rounds
        self.confidence_threshold = confidence_threshold

        # Trace logging setup
        self.trace_dir = trace_dir or (self.repo_root / "build" / "do" / "agent" / "thinking_traces")
        self.trace_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"ThinkingPipeline initialized: "
            f"thinking={thinking_model}, execution={execution_model}, "
            f"max_rounds={max_feedback_rounds}, confidence_threshold={confidence_threshold}"
        )

    def _extract_thinking(self, opus_response: str) -> tuple[str, float]:
        """
        Extract thinking content from Opus response.

        Opus wraps thinking in <|thinking|>...</|thinking|> tags.
        Returns: (thinking_text, confidence_score)
        """
        # Look for thinking tags
        if "<|thinking|>" in opus_response and "<|/thinking|>" in opus_response:
            start = opus_response.find("<|thinking|>") + len("<|thinking|>")
            end = opus_response.find("<|/thinking|>")
            thinking = opus_response[start:end].strip()

            # Heuristic confidence: length and structure
            # Longer, more detailed thinking = higher confidence
            lines = [l.strip() for l in thinking.split("\n") if l.strip()]
            confidence = min(0.95, 0.5 + len(lines) * 0.05)

            return thinking, confidence

        # Fallback: treat entire response as thinking
        return opus_response, 0.6

    def _extract_key_insights(self, thinking_text: str) -> list[str]:
        """Extract key insights/conclusions from thinking text."""
        insights = []

        # Simple heuristic: sentences with conclusion-like keywords
        keywords = ["conclude", "therefore", "key", "main", "important", "critical", "summary", "result"]

        sentences = [s.strip() for s in thinking_text.split(".") if s.strip()]
        for sentence in sentences:
            if any(kw in sentence.lower() for kw in keywords):
                insights.append(sentence)

        # If no insights found, take first and last sentences
        if not insights and sentences:
            insights = [sentences[0], sentences[-1]] if len(sentences) > 1 else [sentences[0]]

        return insights[:3]  # Max 3 insights

    def _inject_thinking_into_prompt(self, thinking: str, user_message: str) -> str:
        """Create system prompt injecting thinking context."""
        system_prompt = (
            "You are a coding assistant. Based on the following analysis and reasoning, "
            "provide your response:\n\n"
            f"**Analysis:**\n{thinking}\n\n"
            "**User request:**\n{user_message}\n\n"
            "Provide a clear, actionable response based on this analysis."
        )
        return system_prompt

    def _score_response(self, response: str, thinking: str) -> float:
        """
        Score the execution model's response confidence.

        Heuristic scoring:
        - Length > 100 chars: +0.2
        - Contains code blocks: +0.1
        - Contains structured content (lists, etc): +0.1
        - Contains caveats/uncertainty: -0.1
        Returns: confidence 0.0-1.0
        """
        confidence = 0.5  # Base confidence

        if len(response) > 100:
            confidence += 0.2
        if "```" in response:
            confidence += 0.1
        if any(marker in response for marker in ["-", "*", "1.", "•"]):
            confidence += 0.1
        if any(term in response.lower() for term in ["uncertain", "may", "might", "unclear"]):
            confidence -= 0.1

        return min(1.0, max(0.0, confidence))

    def execute_with_thinking(
        self,
        user_input: str,
        thinking_model_client=None,
        execution_model_client=None,
        use_mock: bool = False,
    ) -> dict:
        """
        Full pipeline: Opus thinking → Qwen execution → Optional feedback loop.

        Args:
            user_input: User's question/request
            thinking_model_client: OllamaClient for thinking model (uses mock if None)
            execution_model_client: OllamaClient for execution model (uses mock if None)
            use_mock: Force mock mode for testing (default: False)

        Returns:
            {
                "response": str (user-facing response),
                "thinking_trace": ThinkingTrace,
                "confidence": float,
                "rounds_used": int,
            }
        """
        trace_id = str(uuid.uuid4())[:8]
        thinking_stages = []
        round_num = 0
        final_response = None
        final_confidence = 0.0
        breakout_reason = "unknown"

        try:
            # Phase 1: Initial thinking
            round_num = 1
            logger.info(f"[{trace_id}] Starting thinking pipeline, round {round_num}")

            # Call thinking model (use real client if available, else mock)
            if use_mock or thinking_model_client is None:
                thinking_response = self._mock_thinking_call(user_input)
            else:
                thinking_response = self._call_thinking_model(user_input, thinking_model_client)
            thinking_text, thinking_confidence = self._extract_thinking(thinking_response)
            key_insights = self._extract_key_insights(thinking_text)

            thinking_stages.append(ThinkingStage(
                stage_num=round_num,
                thinking_prompt=user_input,
                thinking_response=thinking_response,
                confidence=thinking_confidence,
                key_insights=key_insights,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

            # Phase 2: Execution with thinking context
            logger.info(f"[{trace_id}] Injecting thinking context into execution prompt")
            system_prompt = self._inject_thinking_into_prompt(thinking_text, user_input)

            # Call execution model (use real client if available, else mock)
            if use_mock or execution_model_client is None:
                final_response = self._mock_execution_call(system_prompt, user_input)
            else:
                final_response = self._call_execution_model(system_prompt, user_input, execution_model_client)
            final_confidence = self._score_response(final_response, thinking_text)

            logger.info(f"[{trace_id}] Execution confidence: {final_confidence:.2f}")

            # Phase 3: Optional feedback loop
            while final_confidence < self.confidence_threshold and round_num < self.max_feedback_rounds:
                round_num += 1
                logger.info(f"[{trace_id}] Low confidence ({final_confidence:.2f}), requesting re-think (round {round_num})")

                # Ask Opus to reconsider
                refinement_prompt = (
                    f"Previous response confidence: {final_confidence:.2f}\n"
                    f"Original request: {user_input}\n"
                    f"Initial thinking: {thinking_text}\n"
                    f"Response: {final_response}\n\n"
                    "Reconsider and provide refined thinking."
                )

                # Call thinking model for refinement
                if use_mock or thinking_model_client is None:
                    thinking_response = self._mock_thinking_call(refinement_prompt)
                else:
                    thinking_response = self._call_thinking_model(refinement_prompt, thinking_model_client)
                thinking_text, thinking_confidence = self._extract_thinking(thinking_response)
                key_insights = self._extract_key_insights(thinking_text)

                thinking_stages.append(ThinkingStage(
                    stage_num=round_num,
                    thinking_prompt=refinement_prompt,
                    thinking_response=thinking_response,
                    confidence=thinking_confidence,
                    key_insights=key_insights,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ))

                # Re-execute with refined thinking
                system_prompt = self._inject_thinking_into_prompt(thinking_text, user_input)
                if use_mock or execution_model_client is None:
                    final_response = self._mock_execution_call(system_prompt, user_input)
                else:
                    final_response = self._call_execution_model(system_prompt, user_input, execution_model_client)
                final_confidence = self._score_response(final_response, thinking_text)
                logger.info(f"[{trace_id}] Round {round_num} execution confidence: {final_confidence:.2f}")

            # Determine breakout reason
            if final_confidence >= self.confidence_threshold:
                breakout_reason = "confidence_met"
            else:
                breakout_reason = "round_limit"

            logger.info(f"[{trace_id}] Pipeline complete: {breakout_reason}, rounds={round_num}, confidence={final_confidence:.2f}")

        except Exception as e:
            logger.error(f"[{trace_id}] Pipeline error: {e}")
            breakout_reason = "error"
            final_response = f"Error in thinking pipeline: {str(e)}"
            final_confidence = 0.0

        # Log trace
        trace = ThinkingTrace(
            trace_id=trace_id,
            user_input=user_input,
            timestamp=datetime.now(timezone.utc).isoformat(),
            thinking_stages=thinking_stages,
            final_response=final_response,
            final_confidence=final_confidence,
            total_rounds=round_num,
            breakout_reason=breakout_reason,
        )

        self._save_trace(trace)

        return {
            "response": final_response,
            "thinking_trace": trace,
            "confidence": final_confidence,
            "rounds_used": round_num,
        }

    def _mock_thinking_call(self, prompt: str) -> str:
        """Mock Opus thinking call (replace with real Ollama/HF call in production)."""
        return (
            f"<|thinking|>\n"
            f"Analyzing request: {prompt[:50]}...\n"
            f"Key considerations:\n"
            f"1. Request complexity: medium\n"
            f"2. Required steps: multiple\n"
            f"3. Confidence level: high\n"
            f"<|/thinking|>\n"
            f"I've analyzed this request."
        )

    def _mock_execution_call(self, system_prompt: str, user_input: str) -> str:
        """Mock execution call (replace with real Ollama/HF call in production)."""
        return f"Based on the analysis, here's my response to: {user_input[:30]}..."

    def _call_thinking_model(self, prompt: str, client) -> str:
        """
        Call real Opus thinking model via Ollama client.

        Args:
            prompt: Input prompt
            client: OllamaClient instance

        Returns: Model response text
        """
        try:
            logger.debug(f"Calling thinking model ({self.thinking_model})")
            response = client.generate(
                model=self.thinking_model,
                prompt=prompt,
                temperature=0.5,
                top_p=0.9,
                num_predict=2000,
            )
            return response.text if response else ""
        except Exception as e:
            logger.error(f"Thinking model call failed: {e}")
            return self._mock_thinking_call(prompt)  # Fallback to mock

    def _call_execution_model(self, system_prompt: str, user_input: str, client) -> str:
        """
        Call real execution model (Qwen) via Ollama client.

        Args:
            system_prompt: System prompt with thinking injected
            user_input: Original user input
            client: OllamaClient instance

        Returns: Model response text
        """
        try:
            logger.debug(f"Calling execution model ({self.execution_model})")

            # Use chat format for structured conversation
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]

            response = client.chat(
                model=self.execution_model,
                messages=messages,
                temperature=0.2,
                top_p=0.9,
                num_predict=4096,
            )
            return response.text if response else ""
        except Exception as e:
            logger.error(f"Execution model call failed: {e}")
            return self._mock_execution_call(system_prompt, user_input)  # Fallback to mock

    def _save_trace(self, trace: ThinkingTrace) -> None:
        """Save thinking trace to disk for analysis."""
        try:
            trace_file = self.trace_dir / f"{trace.trace_id}.json"

            # Convert dataclass to JSON-serializable dict
            trace_dict = asdict(trace)
            trace_dict["thinking_stages"] = [
                asdict(stage) for stage in trace.thinking_stages
            ]

            with open(trace_file, "w") as f:
                json.dump(trace_dict, f, indent=2)

            logger.info(f"Trace saved: {trace_file}")
        except Exception as e:
            logger.error(f"Failed to save trace: {e}")

    def get_traces(self, limit: int = 10) -> list[dict]:
        """Retrieve recent thinking traces."""
        traces = []
        trace_files = sorted(self.trace_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]

        for trace_file in trace_files:
            try:
                with open(trace_file) as f:
                    traces.append(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load trace {trace_file}: {e}")

        return traces


def test_pipeline():
    """Test the thinking pipeline with mock data."""
    print("Testing Opus Thinking Pipeline...")

    pipeline = ThinkingPipeline(
        repo_root=Path.cwd(),
        thinking_model="opus-1.5",
        execution_model="qwen25-coder-14b",
    )

    # Test input
    test_input = "How should I debug a Python async function that's hanging?"

    result = pipeline.execute_with_thinking(test_input)

    print(f"\nTest Input: {test_input}")
    print(f"Response: {result['response']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Rounds: {result['rounds_used']}")
    print(f"Trace ID: {result['thinking_trace'].trace_id}")
    print(f"Breakout: {result['thinking_trace'].breakout_reason}")

    # Display trace
    trace = result['thinking_trace']
    print(f"\nThinking Stages: {len(trace.thinking_stages)}")
    for stage in trace.thinking_stages:
        print(f"  Stage {stage.stage_num}: confidence={stage.confidence:.2f}, insights={len(stage.key_insights)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_pipeline()
