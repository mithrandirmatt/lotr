#!/usr/bin/env python3
"""
Integration Test: Opus Thinking Pipeline with Real Ollama Client

Demonstrates end-to-end usage of the thinking pipeline with actual Ollama models.
Run this after ensuring Ollama is running with both models:
  - opus-research/opus-1.5 (thinking model)
  - qwen2.5-coder:14b (execution model)

To install models:
  ollama pull opus-research/opus-1.5
  ollama pull qwen2.5-coder:14b
"""

import logging
import sys
from pathlib import Path

# Add build/agent to path
sys.path.insert(0, str(Path(__file__).parent))

from thinking_pipeline import ThinkingPipeline
from ollama_client import OllamaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_ollama_client_only():
    """Test Ollama client connectivity (no thinking pipeline)."""
    print("\n" + "=" * 70)
    print("TEST 1: Ollama Client Connectivity")
    print("=" * 70)

    client = OllamaClient()

    # Health check
    is_healthy = client.health_check()
    print(f"Ollama service health: {'✓ RUNNING' if is_healthy else '✗ NOT RUNNING'}")

    if not is_healthy:
        print("\n⚠️  Ollama service is not running at http://localhost:11434")
        print("To use real models, start Ollama first:")
        print("  ollama serve")
        print("\nReturning to test with mock mode...\n")
        client.close()
        return False

    # List models
    models = client.list_models()
    print(f"Available models: {len(models)}")
    for model in models:
        print(f"  - {model}")

    # Check for required models
    opus_available = any("opus" in m for m in models)
    qwen_available = any("qwen" in m for m in models)

    print(f"\n✓ Opus model available: {opus_available}")
    print(f"✓ Qwen model available: {qwen_available}")

    client.close()
    return opus_available and qwen_available


def test_with_mock():
    """Test thinking pipeline with mock mode (no Ollama required)."""
    print("\n" + "=" * 70)
    print("TEST 2: Thinking Pipeline (Mock Mode)")
    print("=" * 70)

    pipeline = ThinkingPipeline(
        repo_root=Path(__file__).parent.parent.parent,
        thinking_model="opus-1.5",
        execution_model="qwen25-coder-14b",
    )

    test_input = "How do I optimize a slow Python function?"
    print(f"\nInput: {test_input}")

    # Run with mock (no clients needed)
    result = pipeline.execute_with_thinking(
        user_input=test_input,
        thinking_model_client=None,  # Use mock
        execution_model_client=None,  # Use mock
        use_mock=True,  # Force mock mode
    )

    print(f"\nOutput: {result['response'][:100]}...")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Rounds: {result['rounds_used']}")
    print(f"Trace ID: {result['thinking_trace'].trace_id}")
    print(f"Breakout: {result['thinking_trace'].breakout_reason}")


def test_with_real_models():
    """Test thinking pipeline with real Ollama models."""
    print("\n" + "=" * 70)
    print("TEST 3: Thinking Pipeline (Real Ollama Models)")
    print("=" * 70)

    # Initialize Ollama client
    client = OllamaClient(base_url="http://localhost:11434")

    # Health check
    if not client.health_check():
        print("✗ Ollama service not available")
        client.close()
        return False

    print("✓ Ollama connected")

    # Initialize thinking pipeline
    pipeline = ThinkingPipeline(
        repo_root=Path(__file__).parent.parent.parent,
        thinking_model="opus-research/opus-1.5",
        execution_model="qwen2.5-coder:14b",
    )

    test_input = "What's the best way to handle database transactions in Python?"
    print(f"\nInput: {test_input}")
    print("(This may take a minute with real models...)")

    # Run with real clients
    result = pipeline.execute_with_thinking(
        user_input=test_input,
        thinking_model_client=client,
        execution_model_client=client,
        use_mock=False,  # Use real models
    )

    print(f"\nOutput: {result['response'][:200]}...")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Rounds: {result['rounds_used']}")
    print(f"Trace ID: {result['thinking_trace'].trace_id}")

    # Show thinking stages
    trace = result['thinking_trace']
    print(f"\nThinking Pipeline:")
    for i, stage in enumerate(trace.thinking_stages, 1):
        print(f"  Stage {i}: confidence={stage.confidence:.2f}, insights={len(stage.key_insights)}")
        if stage.key_insights:
            for insight in stage.key_insights[:1]:
                print(f"    - {insight[:60]}...")

    client.close()
    return True


def main():
    """Run all integration tests."""
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  OPUS THINKING PIPELINE - INTEGRATION TESTS".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")

    # Test 1: Ollama client
    ollama_available = test_ollama_client_only()

    # Test 2: Mock mode (always runs)
    test_with_mock()

    # Test 3: Real models (only if Ollama available)
    if ollama_available:
        try:
            test_with_real_models()
            print("\n" + "=" * 70)
            print("✓ All tests completed successfully!")
            print("=" * 70)
        except Exception as e:
            print(f"\n✗ Real model test failed: {e}")
            print("This is expected if models are still being pulled/loaded.")
    else:
        print("\n" + "=" * 70)
        print("⚠️  Real model tests skipped (Ollama not available)")
        print("=" * 70)
        print("\nTo test with real models:")
        print("1. Start Ollama: ollama serve")
        print("2. Pull models: ollama pull opus-research/opus-1.5")
        print("3. Pull models: ollama pull qwen2.5-coder:14b")
        print("4. Re-run this script")


if __name__ == "__main__":
    main()
