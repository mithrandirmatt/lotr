---
name: lotr-reinforcement-generic
---
# Generic Reinforcement Notes

This file is for lessons that are broadly applicable across repositories, languages, tools, and workflows.

## Use this file for
- Debugging patterns.
- Planning or refactoring lessons.
- Tool usage habits that improve agent reliability.
- Testing and verification practices.
- Ways to reduce ambiguity, duplication, or wasted work.

## Entry template
- Date:
- Trigger:
- Learning:
- Evidence:
- Why it is generic:
- Replaces or refines:
- Status:

## Entries

- Date: 2026-08-24
- Trigger: TRAINING
- Learning: Prefer trimming context to only what the current step needs -- read the
  smallest relevant slice of a file/log/doc instead of the whole thing, skip re-reading
  content already held in context unless it may have changed, and summarize large tool
  output instead of quoting it back verbatim. This is now also encoded as literal SFT
  examples (not just a prompt rule) in `build/agent/custom_sft_examples.jsonl`, merged
  into the training corpus by `build.sft_corpus.py`.
- Evidence: Root-caused a "no response returned"/dropped-stream failure on the
  `qwen35-9b_lotr_lora` model to `build.modelfile.py` baking the full contents of all
  22 files under `assets/reference/agent/` into the permanent SYSTEM prompt (~273KB /
  ~69K tokens per request, confirmed via `/api/generate` prompt_eval_count). Fixed by
  replacing full-content concatenation with a lightweight path+title index (model reads
  only what's relevant on demand).
- Why it is generic: Applies to any file/log/doc-heavy task, not just this repo's
  reference docs -- unnecessary full-context loading wastes tokens and increases the
  chance of timeouts/OOM on local models regardless of project.
- Replaces or refines:
- Status: new

## Current focus areas
- Clear task framing.
- Minimal, verified edits.
- Evidence-first troubleshooting.
- Strong validation after changes.
- Reusable ways to keep notes high-signal and non-repetitive.

## Writing rules
- Keep entries short and directly reusable.
- Avoid restating the same learning in different words.
- If the lesson is useful everywhere, keep it here even if it was discovered during LotR work.
- If the lesson depends on repository-specific details, move it to the LotR file instead.
