#!/usr/bin/env python3
"""
Ollama Client for Thinking Pipeline

Provides integration with Ollama API for both thinking (Opus 1.5) and execution (Qwen) models.
Handles model communication, response parsing, and error handling.
"""

import httpx
import json
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OllamaResponse:
    """Response from Ollama model."""
    text: str
    model: str
    done: bool
    context: list[int] = None
    total_duration: int = None
    load_duration: int = None
    prompt_eval_count: int = None
    eval_count: int = None


class OllamaClient:
    """
    Client for Ollama API.

    Supports both thinking models (Opus 1.5) and execution models (Qwen).
    """

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 120.0):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama API base URL (default: http://localhost:11434)
            timeout: Request timeout in seconds (default: 120s)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

        logger.info(f"OllamaClient initialized: {self.base_url}")

    def health_check(self) -> bool:
        """
        Check if Ollama service is running.

        Returns: True if healthy, False otherwise
        """
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def list_models(self) -> list[str]:
        """List available models in Ollama."""
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def generate(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        num_predict: int = 2000,
        stream: bool = False,
    ) -> OllamaResponse | None:
        """
        Generate response from model.

        Args:
            model: Model name (e.g., "opus-research/opus-1.5", "qwen2.5-coder:14b")
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Temperature (0.0-1.0)
            top_p: Top-p sampling
            top_k: Top-k sampling
            num_predict: Max tokens to generate
            stream: Whether to stream response (not yet implemented)

        Returns:
            OllamaResponse or None if failed
        """
        try:
            # Construct request
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "top_k": top_k,
                    "num_predict": num_predict,
                }
            }

            if system_prompt:
                payload["system"] = system_prompt

            logger.debug(f"Calling Ollama generate: model={model}, prompt_len={len(prompt)}")

            response = self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()

            data = response.json()

            return OllamaResponse(
                text=data.get("response", ""),
                model=data.get("model", model),
                done=data.get("done", True),
                context=data.get("context"),
                total_duration=data.get("total_duration"),
                load_duration=data.get("load_duration"),
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
            )

        except Exception as e:
            logger.error(f"Ollama generate failed: {e}")
            return None

    def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        num_predict: int = 2000,
    ) -> OllamaResponse | None:
        """
        Chat with model using message format.

        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
                     [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            temperature: Temperature
            top_p: Top-p sampling
            top_k: Top-k sampling
            num_predict: Max tokens

        Returns:
            OllamaResponse or None if failed
        """
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "top_k": top_k,
                    "num_predict": num_predict,
                }
            }

            logger.debug(f"Calling Ollama chat: model={model}, messages={len(messages)}")

            response = self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()

            data = response.json()

            return OllamaResponse(
                text=data.get("message", {}).get("content", ""),
                model=data.get("model", model),
                done=data.get("done", True),
                total_duration=data.get("total_duration"),
                load_duration=data.get("load_duration"),
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
            )

        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            return None

    def pull(self, model: str) -> bool:
        """
        Pull model from registry.

        Args:
            model: Model name (e.g., "opus-research/opus-1.5")

        Returns: True if successful, False otherwise
        """
        try:
            logger.info(f"Pulling model: {model}")
            response = self.client.post(
                f"{self.base_url}/api/pull",
                json={"name": model}
            )
            response.raise_for_status()
            logger.info(f"Successfully pulled: {model}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull model {model}: {e}")
            return False

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def test_ollama_client():
    """Test Ollama client connectivity."""
    print("Testing Ollama Client...")

    client = OllamaClient()

    # Check health
    is_healthy = client.health_check()
    print(f"Ollama health: {'✓' if is_healthy else '✗'}")

    if not is_healthy:
        print("Warning: Ollama service not running at http://localhost:11434")
        print("To use the thinking pipeline with real models, start Ollama first:")
        print("  ollama serve")
        client.close()
        return

    # List models
    models = client.list_models()
    print(f"Available models: {models}")

    # Test generate if models available
    if models:
        print(f"\nTesting generate with {models[0]}...")
        response = client.generate(
            model=models[0],
            prompt="Say 'Hello from Ollama' and nothing else.",
            num_predict=20
        )
        if response:
            print(f"Response: {response.text[:100]}...")
        else:
            print("Generate failed")

    client.close()
    print("\nOllama client test complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_ollama_client()
