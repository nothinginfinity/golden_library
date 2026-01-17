"""
Legal Services Demo Template

Target: Law firms, legal departments, paralegals.
"""

from typing import Dict, List, Any
from .base_template import BaseTemplate, DemoStep, DemoDeliverable, ValueProposition
from .template_registry import TemplateRegistry


@TemplateRegistry.register
class LegalTemplate(BaseTemplate):
    """Demo template for legal services."""

    SECTOR_ID = "legal"
    SECTOR_NAME = "Legal Services"
    DESCRIPTION = "Document drafting, legal research, contract analysis"
    PAIN_POINTS = [
        "Research time for case law",
        "Document drafting bottleneck",
        "Client intake capacity",
        "Consistency across documents"
    ]

    def get_demo_steps(self) -> List[DemoStep]:
        return [
            DemoStep(
                agent="prax",
                action="coordinate",
                description="Coordinate contract drafting workflow",
                expected_output="Task delegation for research and drafting",
                duration_estimate_seconds=15
            ),
            DemoStep(
                agent="cairn",
                action="research",
                description="Research jurisdiction-specific requirements",
                expected_output="Key legal considerations for the jurisdiction",
                canvas_section="legal_research",
                tools_used=["web_search", "deepseek"],
                duration_estimate_seconds=45
            ),
            DemoStep(
                agent="cairn",
                action="analyze",
                description="Identify required clauses and provisions",
                expected_output="Clause checklist with legal basis",
                canvas_section="clause_analysis",
                tools_used=["deepseek"],
                duration_estimate_seconds=30
            ),
            DemoStep(
                agent="koda",
                action="generate",
                description="Draft contract document",
                expected_output="First draft with standard and custom clauses",
                canvas_section="draft",
                tools_used=["deepseek"],
                duration_estimate_seconds=60
            ),
            DemoStep(
                agent="prax",
                action="synthesize",
                description="Review and flag items for attorney attention",
                expected_output="Summary with flagged sections requiring review",
                canvas_section="review_notes",
                duration_estimate_seconds=30
            )
        ]

    def get_sample_input(self) -> Dict[str, Any]:
        return {
            "document_type": "Non-Disclosure Agreement",
            "jurisdiction": "California",
            "context": "Software development partnership",
            "parties": {
                "disclosing": "Tech Startup Inc.",
                "receiving": "Development Agency LLC"
            },
            "special_considerations": [
                "IP ownership for joint developments",
                "Non-solicitation of employees",
                "Term: 2 years with auto-renewal"
            ],
            "question": "Draft an NDA for a software development partnership in California"
        }

    def get_deliverable(self) -> DemoDeliverable:
        return DemoDeliverable(
            title="Draft NDA with Legal Analysis",
            format="markdown",
            description="First-draft contract ready for attorney review",
            sections=[
                "Document Summary",
                "Jurisdiction Analysis",
                "Standard Clauses (12)",
                "California-Specific Provisions (3)",
                "Flagged Items for Review",
                "Appendix: Legal References"
            ]
        )

    def get_value_proposition(self) -> ValueProposition:
        return ValueProposition(
            time_saved="2 hours → 5 minutes per document",
            cost_saved="Paralegals handle 5x more intake",
            competitive_advantage="Faster turnaround, consistent quality"
        )

    def get_disclaimer(self) -> str:
        """Legal disclaimer for the demo."""
        return """
**Important:** AI-generated legal documents require attorney review before use.
This tool assists with drafting and research but does not replace legal counsel.
"""
