---
inclusion: always
---
# Product: SentinelDesk

SentinelDesk is an incident triage and grounded resolution copilot for IT helpdesks.
For every incoming ticket (subject + body, English or German) it:

1. Predicts `type`, `queue` and `priority` with calibrated confidence.
2. Runs an escalation and safety gate (Auto-Draft Ready vs Escalate to On-Call Engineer, with reasons).
3. Retrieves the top-k most similar resolved tickets from the historical knowledge base.
4. Drafts a reply in the requester's language that cites the ticket IDs it used and never
   invents prices, refunds, SLA credits, legal guarantees or integrations.

Non-negotiables:
- Zero data leakage: nothing from the 20% holdout split (answer, type, queue, priority) is ever
  indexed, trained on, or shown to the pipeline at inference time.
- Missing subjects must never crash the pipeline.
- When in doubt, escalate. A false escalation is cheap; a missed outage is expensive.
