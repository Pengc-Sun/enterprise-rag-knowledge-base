# Demo Data

This directory contains synthetic enterprise documents for local demonstrations.

Suggested demo flow:

1. Register or log in through the frontend.
2. Create a knowledge base named `Enterprise Policy Demo`.
3. Upload these Markdown files from `docs/demo-data/`.
4. Wait for processing to complete.
5. Open chat and ask one of the sample questions below.
6. For the v2.0 report workflow, run analysis tasks, review the results, approve or edit findings,
   and generate report sections only from approved content.

## Files

- `travel_policy_demo.md`
- `security_handbook_demo.md`
- `engineering_workflow_demo.md`
- `support_sla_demo.md`
- `report_workflow_demo.md`

## Sample Questions

- What is the daily meal allowance for approved business travel?
- How far in advance should international travel be submitted?
- What should an employee do if a laptop is lost?
- What is the first response target for a P1 support incident?
- What review is required before merging a production change?
- What evidence is required for a critical vendor security review?
- Which report sections can be created from approved policy findings?

## v2.0 Report Workflow Demo

Use `report_workflow_demo.md` when demonstrating the Week 7 report builder and approved-content
rules.

Suggested report workflow:

1. Create a workspace from a template that includes analysis tasks and a report outline.
2. Upload `report_workflow_demo.md` into the workspace knowledge base.
3. Run analysis tasks against the uploaded document.
4. In the review queue, approve one result and edit one result.
5. Reject or leave at least one result in `needs_review`.
6. Create a report section from the approved result.
7. Generate another draft section from the reviewer-edited result.
8. Attempt to reference the rejected or unreviewed result and confirm the API returns a 400 error.
9. Reorder the sections and open the Markdown report preview.

Expected outcome:

- Approved and reviewer-edited findings can be used in report sections.
- Unreviewed, rejected, or cross-workspace findings are blocked.
- Report preview shows ordered Markdown sections with source result IDs retained by the backend.

These records are synthetic and contain no real company data.
