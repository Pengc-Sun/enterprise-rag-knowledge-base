from typing import TypedDict

from backend.app.models.workspace import WorkspaceTemplateCategory


class BuiltInWorkspaceTemplate(TypedDict):
    id: str
    name: str
    description: str
    category: WorkspaceTemplateCategory
    version: str
    directory_schema: dict[str, object]
    analysis_task_schema: dict[str, object]
    report_schema: dict[str, object]


BUILT_IN_WORKSPACE_TEMPLATES: tuple[BuiltInWorkspaceTemplate, ...] = (
    {
        "id": "10000000-0000-4000-8000-000000000001",
        "name": "General Knowledge Workspace",
        "description": "A general-purpose workspace for private document Q&A.",
        "category": WorkspaceTemplateCategory.GENERAL,
        "version": "1.0",
        "directory_schema": {
            "version": "1.0",
            "directories": [
                {
                    "key": "source_documents",
                    "name": "Source Documents",
                    "path": "source-documents",
                    "description": "Original files uploaded for retrieval and review.",
                    "parent_key": None,
                    "sort_order": 10,
                },
                {
                    "key": "notes",
                    "name": "Notes",
                    "path": "notes",
                    "description": "Reviewer notes and working observations.",
                    "parent_key": None,
                    "sort_order": 20,
                },
                {
                    "key": "reports",
                    "name": "Reports",
                    "path": "reports",
                    "description": "Draft and final generated reports.",
                    "parent_key": None,
                    "sort_order": 30,
                },
            ],
            "knowledge_bases": [
                {
                    "key": "source_documents",
                    "name": "Source Documents",
                    "description": "Default knowledge base for uploaded source documents.",
                    "directory_key": "source_documents",
                    "visibility": "private",
                    "sort_order": 10,
                },
            ],
        },
        "analysis_task_schema": {
            "version": "1.0",
            "tasks": [
                {
                    "key": "document_summary",
                    "name": "Document Summary",
                    "description": "Summarize the uploaded corpus with cited key points.",
                    "task_type": "summary",
                    "prompt_template": (
                        "Summarize the workspace documents. Return cited key findings, "
                        "open questions, and source references."
                    ),
                    "default_enabled": True,
                    "sort_order": 10,
                    "output_schema": {
                        "type": "object",
                        "required": ["summary", "key_findings", "citations"],
                        "properties": {
                            "summary": {"type": "string"},
                            "key_findings": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                {
                    "key": "action_items",
                    "name": "Action Item Extraction",
                    "description": "Find explicit next steps, owners, and unresolved decisions.",
                    "task_type": "extraction",
                    "prompt_template": (
                        "Extract action items from the workspace documents with owner, "
                        "due date, status, and citation when available."
                    ),
                    "default_enabled": True,
                    "sort_order": 20,
                    "output_schema": {
                        "type": "object",
                        "required": ["items", "citations"],
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["action", "status"],
                                    "properties": {
                                        "action": {"type": "string"},
                                        "owner": {"type": "string"},
                                        "due_date": {"type": "string"},
                                        "status": {"type": "string"},
                                    },
                                },
                            },
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            ],
        },
        "report_schema": {
            "version": "1.0",
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "Short summary of the workspace corpus.",
                    "source_task_keys": ["document_summary"],
                    "required": True,
                    "sort_order": 10,
                },
                {
                    "key": "key_findings",
                    "title": "Key Findings",
                    "description": "Approved cited findings from the summary task.",
                    "source_task_keys": ["document_summary"],
                    "required": True,
                    "sort_order": 20,
                },
                {
                    "key": "actions",
                    "title": "Action Items",
                    "description": "Approved extracted follow-up items.",
                    "source_task_keys": ["action_items"],
                    "required": False,
                    "sort_order": 30,
                },
                {
                    "key": "references",
                    "title": "References",
                    "description": "Citations used by approved sections.",
                    "source_task_keys": ["document_summary", "action_items"],
                    "required": True,
                    "sort_order": 40,
                },
            ],
            "export_formats": ["markdown", "docx", "pdf"],
        },
    },
    {
        "id": "10000000-0000-4000-8000-000000000002",
        "name": "Policy Review Workspace",
        "description": "A workspace for reviewing company policies and compliance evidence.",
        "category": WorkspaceTemplateCategory.POLICY_REVIEW,
        "version": "1.0",
        "directory_schema": {
            "version": "1.0",
            "directories": [
                {
                    "key": "policies",
                    "name": "Policies",
                    "path": "policies",
                    "description": "Policy documents under review.",
                    "parent_key": None,
                    "sort_order": 10,
                },
                {
                    "key": "evidence",
                    "name": "Evidence",
                    "path": "evidence",
                    "description": "Supporting controls, audits, and implementation evidence.",
                    "parent_key": None,
                    "sort_order": 20,
                },
                {
                    "key": "exceptions",
                    "name": "Exceptions",
                    "path": "exceptions",
                    "description": "Known gaps, waivers, or exception records.",
                    "parent_key": None,
                    "sort_order": 30,
                },
                {
                    "key": "reports",
                    "name": "Reports",
                    "path": "reports",
                    "description": "Approved policy review reports.",
                    "parent_key": None,
                    "sort_order": 40,
                },
            ],
            "knowledge_bases": [
                {
                    "key": "policies",
                    "name": "Policies",
                    "description": "Policy documents under review.",
                    "directory_key": "policies",
                    "visibility": "private",
                    "sort_order": 10,
                },
                {
                    "key": "evidence",
                    "name": "Evidence",
                    "description": "Supporting controls, audits, and implementation evidence.",
                    "directory_key": "evidence",
                    "visibility": "private",
                    "sort_order": 20,
                },
                {
                    "key": "exceptions",
                    "name": "Exceptions",
                    "description": "Known gaps, waivers, and exception records.",
                    "directory_key": "exceptions",
                    "visibility": "private",
                    "sort_order": 30,
                },
            ],
        },
        "analysis_task_schema": {
            "version": "1.0",
            "tasks": [
                {
                    "key": "policy_requirements",
                    "name": "Policy Requirement Extraction",
                    "description": "Extract obligations, controls, owners, and deadlines.",
                    "task_type": "extraction",
                    "prompt_template": (
                        "Extract policy requirements with obligation, responsible party, "
                        "evidence expectation, deadline, and citation."
                    ),
                    "default_enabled": True,
                    "sort_order": 10,
                    "output_schema": {
                        "type": "object",
                        "required": ["requirements", "citations"],
                        "properties": {
                            "requirements": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["requirement", "evidence_required"],
                                    "properties": {
                                        "requirement": {"type": "string"},
                                        "owner": {"type": "string"},
                                        "deadline": {"type": "string"},
                                        "evidence_required": {"type": "string"},
                                    },
                                },
                            },
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                {
                    "key": "policy_risk_review",
                    "name": "Policy Risk Review",
                    "description": "Identify policy gaps, risk severity, and remediation notes.",
                    "task_type": "risk_review",
                    "prompt_template": (
                        "Compare policies and evidence. Identify gaps, risk severity, "
                        "recommended remediation, and citations."
                    ),
                    "default_enabled": True,
                    "sort_order": 20,
                    "output_schema": {
                        "type": "object",
                        "required": ["risks", "citations"],
                        "properties": {
                            "risks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["risk", "severity", "remediation"],
                                    "properties": {
                                        "risk": {"type": "string"},
                                        "severity": {"type": "string"},
                                        "remediation": {"type": "string"},
                                    },
                                },
                            },
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            ],
        },
        "report_schema": {
            "version": "1.0",
            "sections": [
                {
                    "key": "executive_summary",
                    "title": "Executive Summary",
                    "description": "Reviewer-approved summary of policy posture.",
                    "source_task_keys": ["policy_requirements", "policy_risk_review"],
                    "required": True,
                    "sort_order": 10,
                },
                {
                    "key": "requirements",
                    "title": "Policy Requirements",
                    "description": "Approved requirement extraction results.",
                    "source_task_keys": ["policy_requirements"],
                    "required": True,
                    "sort_order": 20,
                },
                {
                    "key": "risk_findings",
                    "title": "Risk Findings",
                    "description": "Approved gaps, risks, and remediation recommendations.",
                    "source_task_keys": ["policy_risk_review"],
                    "required": True,
                    "sort_order": 30,
                },
                {
                    "key": "citations",
                    "title": "Citations",
                    "description": "Evidence references used in the report.",
                    "source_task_keys": ["policy_requirements", "policy_risk_review"],
                    "required": True,
                    "sort_order": 40,
                },
            ],
            "export_formats": ["markdown", "docx", "pdf"],
        },
    },
    {
        "id": "10000000-0000-4000-8000-000000000003",
        "name": "IT Support Workspace",
        "description": "A workspace for IT runbooks, incident procedures, and support answers.",
        "category": WorkspaceTemplateCategory.IT_SUPPORT,
        "version": "1.0",
        "directory_schema": {
            "version": "1.0",
            "directories": [
                {
                    "key": "runbooks",
                    "name": "Runbooks",
                    "path": "runbooks",
                    "description": "Operational runbooks and troubleshooting steps.",
                    "parent_key": None,
                    "sort_order": 10,
                },
                {
                    "key": "incidents",
                    "name": "Incident Procedures",
                    "path": "incidents",
                    "description": "Incident response procedures and escalation rules.",
                    "parent_key": None,
                    "sort_order": 20,
                },
                {
                    "key": "sla",
                    "name": "SLA",
                    "path": "sla",
                    "description": "Service levels and priority definitions.",
                    "parent_key": None,
                    "sort_order": 30,
                },
                {
                    "key": "reports",
                    "name": "Reports",
                    "path": "reports",
                    "description": "Reviewed support knowledge reports.",
                    "parent_key": None,
                    "sort_order": 40,
                },
            ],
            "knowledge_bases": [
                {
                    "key": "runbooks",
                    "name": "Runbooks",
                    "description": "Operational runbooks and troubleshooting procedures.",
                    "directory_key": "runbooks",
                    "visibility": "private",
                    "sort_order": 10,
                },
                {
                    "key": "incidents",
                    "name": "Incident Procedures",
                    "description": "Incident response procedures and escalation rules.",
                    "directory_key": "incidents",
                    "visibility": "private",
                    "sort_order": 20,
                },
                {
                    "key": "sla",
                    "name": "SLA",
                    "description": "Service levels and priority definitions.",
                    "directory_key": "sla",
                    "visibility": "private",
                    "sort_order": 30,
                },
            ],
        },
        "analysis_task_schema": {
            "version": "1.0",
            "tasks": [
                {
                    "key": "support_steps",
                    "name": "Support Step Extraction",
                    "description": "Extract ordered troubleshooting steps with prerequisites.",
                    "task_type": "extraction",
                    "prompt_template": (
                        "Extract support steps with prerequisites, expected result, "
                        "rollback guidance, and citations."
                    ),
                    "default_enabled": True,
                    "sort_order": 10,
                    "output_schema": {
                        "type": "object",
                        "required": ["procedures", "citations"],
                        "properties": {
                            "procedures": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["name", "steps"],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "priority": {"type": "string"},
                                        "steps": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                {
                    "key": "incident_priority_summary",
                    "name": "Incident Priority Summary",
                    "description": "Classify incidents by priority, response target, and owner.",
                    "task_type": "classification",
                    "prompt_template": (
                        "Classify incident priorities with impact, urgency, response "
                        "target, escalation path, and citations."
                    ),
                    "default_enabled": True,
                    "sort_order": 20,
                    "output_schema": {
                        "type": "object",
                        "required": ["priorities", "citations"],
                        "properties": {
                            "priorities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["priority", "response_target"],
                                    "properties": {
                                        "priority": {"type": "string"},
                                        "impact": {"type": "string"},
                                        "urgency": {"type": "string"},
                                        "response_target": {"type": "string"},
                                    },
                                },
                            },
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            ],
        },
        "report_schema": {
            "version": "1.0",
            "sections": [
                {
                    "key": "support_scope",
                    "title": "Support Scope",
                    "description": "Approved summary of supported services and boundaries.",
                    "source_task_keys": ["support_steps"],
                    "required": True,
                    "sort_order": 10,
                },
                {
                    "key": "priority_matrix",
                    "title": "Priority Matrix",
                    "description": "Approved incident priority definitions and response targets.",
                    "source_task_keys": ["incident_priority_summary"],
                    "required": True,
                    "sort_order": 20,
                },
                {
                    "key": "runbook_references",
                    "title": "Runbook References",
                    "description": "Cited runbook entries used by the report.",
                    "source_task_keys": ["support_steps", "incident_priority_summary"],
                    "required": True,
                    "sort_order": 30,
                },
            ],
            "export_formats": ["markdown", "docx", "pdf"],
        },
    },
    {
        "id": "10000000-0000-4000-8000-000000000004",
        "name": "Research Review Workspace",
        "description": "A workspace for literature review, evidence tables, and cited reports.",
        "category": WorkspaceTemplateCategory.RESEARCH_REVIEW,
        "version": "1.0",
        "directory_schema": {
            "version": "1.0",
            "directories": [
                {
                    "key": "papers",
                    "name": "Papers",
                    "path": "papers",
                    "description": "Primary papers and source material.",
                    "parent_key": None,
                    "sort_order": 10,
                },
                {
                    "key": "notes",
                    "name": "Notes",
                    "path": "notes",
                    "description": "Research notes and reviewer observations.",
                    "parent_key": None,
                    "sort_order": 20,
                },
                {
                    "key": "evidence_tables",
                    "name": "Evidence Tables",
                    "path": "evidence-tables",
                    "description": "Structured extracted evidence.",
                    "parent_key": None,
                    "sort_order": 30,
                },
                {
                    "key": "reports",
                    "name": "Reports",
                    "path": "reports",
                    "description": "Draft and final review reports.",
                    "parent_key": None,
                    "sort_order": 40,
                },
            ],
            "knowledge_bases": [
                {
                    "key": "papers",
                    "name": "Papers",
                    "description": "Primary papers and source material.",
                    "directory_key": "papers",
                    "visibility": "private",
                    "sort_order": 10,
                },
                {
                    "key": "evidence_tables",
                    "name": "Evidence Tables",
                    "description": "Structured extracted research evidence.",
                    "directory_key": "evidence_tables",
                    "visibility": "private",
                    "sort_order": 20,
                },
            ],
        },
        "analysis_task_schema": {
            "version": "1.0",
            "tasks": [
                {
                    "key": "evidence_table",
                    "name": "Evidence Table Extraction",
                    "description": "Extract study design, population, methods, and findings.",
                    "task_type": "extraction",
                    "prompt_template": (
                        "Create a cited evidence table with study design, population, "
                        "methods, outcomes, limitations, and citation."
                    ),
                    "default_enabled": True,
                    "sort_order": 10,
                    "output_schema": {
                        "type": "object",
                        "required": ["rows", "citations"],
                        "properties": {
                            "rows": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["source", "finding", "limitation"],
                                    "properties": {
                                        "source": {"type": "string"},
                                        "study_design": {"type": "string"},
                                        "population": {"type": "string"},
                                        "finding": {"type": "string"},
                                        "limitation": {"type": "string"},
                                    },
                                },
                            },
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                {
                    "key": "paper_comparison",
                    "name": "Paper Comparison",
                    "description": "Compare sources for agreement, disagreement, and gaps.",
                    "task_type": "comparison",
                    "prompt_template": (
                        "Compare the research sources. Return agreements, conflicts, "
                        "evidence gaps, and citations."
                    ),
                    "default_enabled": True,
                    "sort_order": 20,
                    "output_schema": {
                        "type": "object",
                        "required": ["agreements", "conflicts", "gaps", "citations"],
                        "properties": {
                            "agreements": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "conflicts": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "gaps": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "citations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            ],
        },
        "report_schema": {
            "version": "1.0",
            "sections": [
                {
                    "key": "research_question",
                    "title": "Research Question",
                    "description": "Approved framing and scope for the review.",
                    "source_task_keys": ["paper_comparison"],
                    "required": True,
                    "sort_order": 10,
                },
                {
                    "key": "evidence_table",
                    "title": "Evidence Table",
                    "description": "Reviewer-approved structured evidence.",
                    "source_task_keys": ["evidence_table"],
                    "required": True,
                    "sort_order": 20,
                },
                {
                    "key": "synthesis",
                    "title": "Synthesis",
                    "description": "Approved synthesis of agreements, conflicts, and gaps.",
                    "source_task_keys": ["paper_comparison"],
                    "required": True,
                    "sort_order": 30,
                },
                {
                    "key": "references",
                    "title": "References",
                    "description": "Citations used by the review.",
                    "source_task_keys": ["evidence_table", "paper_comparison"],
                    "required": True,
                    "sort_order": 40,
                },
            ],
            "export_formats": ["markdown", "docx", "pdf"],
        },
    },
)
