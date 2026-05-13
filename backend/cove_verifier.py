"""Chain-of-Verification wrapper for improvement suggestions.

Uses CoVe to verify suggested improvements before auto-commit:
1. Generate verification questions about suggestion
2. Answer questions via code search + reasoning
3. Produce confidence score
4. Log Q&A in journal for future learning
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from learning_journal import record
from prompts_loader import load, render
from services import gemini

REPO_ROOT = Path(__file__).parent.parent


async def verify_improvement(suggestion: dict[str, str]) -> dict[str, Any]:
    """Verify improvement suggestion via Chain-of-Verification.

    Args:
        suggestion: {target, enhancement, rationale}

    Returns:
        {
            "verified": bool,
            "confidence": float (0-1),
            "questions": [...],
            "answers": [...],
            "reasoning": str,
            "llm_errors": [str],  # populated when a sub-call fell back.
                                  # Orchestrator uses this to skip ledger writes
                                  # so transient Gemini failures don't poison
                                  # the anti-brainrot filter's corpus.
        }
    """
    llm_errors: list[str] = []

    # Generate verification questions about the suggestion
    questions = await generate_verification_questions_llm(suggestion)

    if not questions:
        llm_errors.append("questions_fallback")
        # Fallback to rule-based questions if LLM fails
        questions = [
            f"Will the enhancement solve the stated problem in {suggestion.get('target')}?",
            "Could this introduce any breaking changes?",
            "Is there a simpler approach?",
            "Does the rationale stand up to scrutiny?",
            "Will this change pass the verify suite?",
        ]

    # Answer verification questions via LLM reasoning
    answers = await answer_questions_llm(questions, suggestion)
    # Detect the sentinel pattern from answer_questions_llm's except-branch:
    # every answer carrying "LLM analysis failed" means the LLM step degraded.
    if answers and all(
        isinstance(a, dict) and "LLM analysis failed" in str(a.get("answer", ""))
        for a in answers
    ):
        llm_errors.append("answers_fallback")

    # Assess confidence based on answers
    confidence = assess_confidence(questions, answers, suggestion)
    verified = confidence >= 0.75

    reasoning = generate_reasoning(questions, answers, confidence)

    record(
        phase="cove-verify",
        outcome="passed" if verified else "failed",
        lesson=f"Verified improvement: {suggestion.get('target', 'unknown')} (confidence: {confidence:.0%})",
        metadata={
            "suggestion": suggestion,
            "questions": questions,
            "confidence": confidence,
            "verified": verified,
            "llm_errors": llm_errors,
        },
    )

    return {
        "verified": verified,
        "confidence": confidence,
        "questions": questions,
        "answers": answers,
        "reasoning": reasoning,
        "llm_errors": llm_errors,
    }


async def generate_verification_questions_llm(suggestion: dict[str, str]) -> list[str]:
    """Use Gemini to generate skeptical verification questions."""
    tpl = load("cove_questions")
    prompt = render(
        tpl,
        {
            "target": suggestion.get("target", ""),
            "enhancement": suggestion.get("enhancement", ""),
            "rationale": suggestion.get("rationale", ""),
        },
    )
    try:
        res = await gemini.generate_json(prompt, model=tpl.model, phase="cove-questions")
        if isinstance(res, list):
            return res
        if isinstance(res, dict) and "questions" in res:
            return res["questions"]
        return []
    except Exception as exc:
        from error_logger import log_error

        log_error("cove-questions", exc, context={"target": suggestion.get("target")})
        return []


async def answer_questions_llm(
    questions: list[str], suggestion: dict[str, str]
) -> list[dict[str, str]]:
    """Use Gemini to answer the verification questions."""
    tpl = load("cove_answers")
    prompt = render(
        tpl,
        {
            "target": suggestion.get("target", ""),
            "enhancement": suggestion.get("enhancement", ""),
            "questions_json": json.dumps(questions, indent=2, ensure_ascii=False),
        },
    )
    try:
        answers = await gemini.generate_json(prompt, model=tpl.model, phase="cove-answers")
        if isinstance(answers, list):
            return answers
        return []
    except Exception as exc:
        from error_logger import log_error

        log_error("cove-answers", exc, context={"target": suggestion.get("target"), "n_questions": len(questions)})
        return [{"question": q, "answer": "LLM analysis failed, assuming neutral.", "sentiment": "neutral"} for q in questions]


def assess_confidence(
    questions: list[str],
    answers: list[dict[str, str]],
    suggestion: dict[str, str],
) -> float:
    """Assess confidence based on the sentiment of answers."""
    if not answers:
        return 0.5
    
    pos = sum(1 for a in answers if a.get("sentiment") == "positive")
    neg = sum(1 for a in answers if a.get("sentiment") == "negative")
    
    # negations have heavy weight
    score = (pos * 1.0 + neg * -2.0) / len(answers)
    # Map to 0-1 range, base 0.5
    confidence = 0.5 + (score * 0.5)
    
    # Boost if rationale mentions journal patterns
    if "journal" in suggestion.get("rationale", "").lower():
        confidence += 0.1

    return max(0.0, min(1.0, confidence))


def generate_reasoning(
    questions: list[str],
    answers: list[dict[str, str]],
    confidence: float,
) -> str:
    """Generate human-readable verification reasoning."""
    lines = [f"CoVe Verification (confidence: {confidence:.0%})"]
    lines.append("")
    lines.append("Analysis Results:")
    for qa in answers:
        sentiment = qa.get("sentiment", "neutral").upper()
        lines.append(f"  [{sentiment}] Q: {qa['question']}")
        lines.append(f"  A: {qa['answer']}")
    lines.append("")
    if confidence >= 0.75:
        lines.append("✓ Verification PASSED — Safe to commit")
    else:
        lines.append("✗ Verification FAILED — Review required")

    return "\n".join(lines)
