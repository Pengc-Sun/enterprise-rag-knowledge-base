# Report Workflow Demo Policy Pack

This synthetic policy pack is designed for the v2.0 workspace report workflow demo. It contains
short, reviewable findings that can be extracted by analysis tasks, approved by a reviewer, and used
as formal report section sources.

## Vendor Risk

Critical vendors must complete a security review before production access is granted. The review
must confirm data classification, authentication method, incident contact, and contractual support
coverage.

Approved vendor risk conclusion:

- Critical vendors require security review before production access.
- The minimum review evidence is data classification, authentication method, incident contact, and
  contractual support coverage.

## Travel Controls

International travel must be requested at least 14 days before departure. Reimbursement requires an
itemized receipt, proof of payment, traveler name, dates, taxes, and total amount paid.

Approved travel control conclusion:

- International travel requires 14 days of lead time.
- Hotel reimbursement requires itemized receipt evidence and proof of payment.

## Incident Response

A P1 support incident is a production-critical workflow failure affecting many users. The first
response target is 15 minutes during staffed hours. The incident owner must post status updates every
30 minutes until service is restored.

Approved incident response conclusion:

- P1 incidents require first response within 15 minutes during staffed hours.
- The incident owner must post updates every 30 minutes until recovery.

## Engineering Change Review

Production changes require peer review, passing automated tests, and rollback instructions. Changes
that touch authentication, authorization, billing, or customer data require an additional senior
reviewer.

Approved engineering control conclusion:

- Production changes require peer review, passing tests, and rollback instructions.
- Sensitive changes require an additional senior reviewer.

## Report Outline Example

A formal policy review report can use the following sections after reviewer approval:

1. Executive Summary
2. Vendor Risk Controls
3. Travel and Reimbursement Controls
4. Incident Response Controls
5. Engineering Change Controls

All report sections should reference only approved or reviewer-edited analysis results. Draft AI
results, rejected findings, and findings still marked `needs_review` should not be included in the
formal report preview.
