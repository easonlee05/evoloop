"""Retry, timeout, and circuit-break policy runtime for workflow steps."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from app.core.task import WorkflowStep


class RetryDecision(str, Enum):
    RETRY = "retry"
    GIVE_UP = "give_up"
    TIMEOUT = "timeout"
    CIRCUIT_OPEN = "circuit_open"


@dataclass(frozen=True)
class RetryPolicyDecision:
    """A deterministic retry decision for one failed step attempt."""

    decision: RetryDecision
    step_id: str
    attempt: int
    next_attempt: int
    max_attempts: int
    delay_seconds: float
    reason: str
    error_code: Optional[str] = None

    @property
    def should_retry(self) -> bool:
        return self.decision == RetryDecision.RETRY


@dataclass
class RetryPolicyRuntime:
    """Interprets `WorkflowStep.retry_policy` without executing sleeps itself."""

    default_max_attempts: int = 1
    default_backoff_seconds: float = 0
    default_timeout_ms: Optional[int] = None

    def evaluate(
        self,
        step: WorkflowStep,
        *,
        attempt: int,
        elapsed_ms: int,
        error_code: Optional[str] = None,
    ) -> RetryPolicyDecision:
        policy = dict(step.retry_policy or {})
        max_attempts = int(policy.get("max_attempts", policy.get("retries", self.default_max_attempts)))
        if "retries" in policy and "max_attempts" not in policy:
            max_attempts = int(policy["retries"]) + 1
        timeout_ms = policy.get("timeout_ms", self.default_timeout_ms)
        if timeout_ms is not None and elapsed_ms > int(timeout_ms):
            return self._decision(RetryDecision.TIMEOUT, step, attempt, max_attempts, 0, "timeout_exceeded", error_code)

        non_retryable = {str(item) for item in policy.get("non_retryable_errors", [])}
        if error_code and error_code in non_retryable:
            return self._decision(RetryDecision.CIRCUIT_OPEN, step, attempt, max_attempts, 0, "non_retryable_error", error_code)

        if attempt >= max_attempts:
            return self._decision(RetryDecision.GIVE_UP, step, attempt, max_attempts, 0, "max_attempts_exhausted", error_code)

        delay = self._delay_seconds(policy, attempt)
        return self._decision(RetryDecision.RETRY, step, attempt, max_attempts, delay, "retry_allowed", error_code)

    def _delay_seconds(self, policy: Dict[str, Any], attempt: int) -> float:
        base = float(policy.get("backoff_seconds", self.default_backoff_seconds))
        strategy = str(policy.get("backoff", policy.get("backoff_strategy", "fixed"))).lower()
        if strategy == "exponential":
            return base * (2 ** max(0, attempt - 1))
        if strategy == "linear":
            return base * max(1, attempt)
        return base

    @staticmethod
    def _decision(
        decision: RetryDecision,
        step: WorkflowStep,
        attempt: int,
        max_attempts: int,
        delay_seconds: float,
        reason: str,
        error_code: Optional[str],
    ) -> RetryPolicyDecision:
        return RetryPolicyDecision(
            decision=decision,
            step_id=step.id,
            attempt=attempt,
            next_attempt=attempt + 1,
            max_attempts=max_attempts,
            delay_seconds=delay_seconds,
            reason=reason,
            error_code=error_code,
        )

    def to_event_payload(
        self,
        step: WorkflowStep,
        decision: RetryPolicyDecision,
        *,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "step_id": step.id,
            "step_type": step.type,
            "decision": decision.decision.value,
            "attempt": decision.attempt,
            "next_attempt": decision.next_attempt,
            "max_attempts": decision.max_attempts,
            "delay_seconds": decision.delay_seconds,
            "reason": decision.reason,
            "error_code": decision.error_code,
            "error_message_redacted": bool(error_message),
        }
