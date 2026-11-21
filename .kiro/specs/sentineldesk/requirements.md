# Requirements: SentinelDesk

## Introduction
SentinelDesk triages raw helpdesk tickets, decides whether they are safe to auto-answer, retrieves
historical precedents and drafts grounded replies in English or German.

## Requirement 1: Leakage-safe data split
**User story:** As a judge, I want a strict 80/20 split so that holdout metrics are honest.
1. WHEN the build script runs THE SYSTEM SHALL shuffle with seed 42, assign `TKT-xxxxx` ids and split 80% KB / 20% holdout.
2. THE SYSTEM SHALL train the classifier and build the vector index from the KB split only.
3. WHEN evaluating THE SYSTEM SHALL pass only `subject` and `body` of holdout tickets to the pipeline.
4. THE SYSTEM SHALL assert that no holdout ticket id is present in the vector index.

## Requirement 2: Multi-task triage
**User story:** As an operator, I want type, queue and priority predicted with confidence.
1. WHEN a ticket arrives THE SYSTEM SHALL output `type`, `queue`, `priority`, each with a calibrated probability.
2. IF the subject is null or empty THEN THE SYSTEM SHALL classify from the body alone without error.
3. THE SYSTEM SHALL report Macro-F1 per target and high-priority recall on the holdout split.

## Requirement 3: Language detection
1. WHEN a ticket arrives THE SYSTEM SHALL detect `en` or `de` from the raw text.
2. IF detection is ambiguous THEN THE SYSTEM SHALL fall back to a stop-word heuristic and default to `en`.

## Requirement 4: Escalation & safety gate
**User story:** As an on-call engineer, I want risky tickets routed to me with a reason.
1. WHEN predicted priority is `high` AND predicted type is `Incident` THE SYSTEM SHALL escalate.
2. WHEN any target confidence is below `CONF_THRESHOLD` THE SYSTEM SHALL escalate.
3. WHEN the best retrieval similarity is below `SIM_THRESHOLD` THE SYSTEM SHALL escalate (no precedent).
4. WHEN the ticket asks for refunds, compensation, pricing, legal or contractual commitments not covered by retrieved answers THE SYSTEM SHALL escalate.
5. WHEN the ticket contains critical-outage or prompt-injection language THE SYSTEM SHALL escalate.
6. THE SYSTEM SHALL return a status (`AUTO_DRAFT_READY` | `ESCALATE_TO_ON_CALL`) and a list of human-readable reasons.

## Requirement 5: Retrieval (RAG)
1. THE SYSTEM SHALL return the top-k (3–5) KB tickets with `ticket_id`, similarity and answer snippet.
2. THE SYSTEM SHALL support cross-lingual matching (German query, English precedent and vice versa).

## Requirement 6: Grounded reply
1. THE SYSTEM SHALL draft the reply in the detected language.
2. THE SYSTEM SHALL cite only ticket ids that were retrieved; invalid citations are stripped.
3. IF the draft contains prices, percentages or durations absent from the evidence THEN THE SYSTEM SHALL flag it and escalate.
4. IF no LLM is configured THEN THE SYSTEM SHALL produce a deterministic extractive draft.

## Requirement 7: PII guardrail (bonus)
1. THE SYSTEM SHALL mask emails, phone numbers, IP addresses, IBANs, card and account numbers before any external LLM call.

## Requirement 8: Outage burst detection (bonus)
1. WHEN at least `BURST_MIN` semantically similar tickets arrive within `BURST_WINDOW_MIN` minutes THE SYSTEM SHALL raise a major-incident banner and escalate.

## Requirement 9: Triage console
1. THE SYSTEM SHALL let a user paste a ticket and see predictions, confidences, latency, escalation badge with reasons, top precedents and the draft.
