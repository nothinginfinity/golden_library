"""
Construction Demo Template

Target: Construction companies, general contractors, project managers.
"""

from typing import Dict, List, Any
from .base_template import BaseTemplate, DemoStep, DemoDeliverable, ValueProposition
from .template_registry import TemplateRegistry


@TemplateRegistry.register
class ConstructionTemplate(BaseTemplate):
    """Demo template for construction bid preparation and project planning."""

    SECTOR_ID = "construction"
    SECTOR_NAME = "Construction"
    DESCRIPTION = "Bid preparation, project estimation, timeline planning"
    PAIN_POINTS = [
        "Bid accuracy and speed",
        "Project timeline estimation",
        "Subcontractor coordination",
        "Material cost tracking"
    ]

    def get_demo_steps(self) -> List[DemoStep]:
        return [
            DemoStep(
                agent="prax",
                action="coordinate",
                description="Coordinate bid preparation workflow",
                expected_output="Task delegation for scope analysis and estimation",
                duration_estimate_seconds=15
            ),
            DemoStep(
                agent="cairn",
                action="analyze",
                description="Break down project scope into phases",
                expected_output="Phase breakdown with dependencies and critical path",
                canvas_section="scope_analysis",
                tools_used=["deepseek"],
                duration_estimate_seconds=45
            ),
            DemoStep(
                agent="cairn",
                action="research",
                description="Research permit requirements and regulations",
                expected_output="Permit checklist and timeline estimates",
                canvas_section="permits",
                tools_used=["web_search", "deepseek"],
                duration_estimate_seconds=30
            ),
            DemoStep(
                agent="koda",
                action="generate",
                description="Generate material and labor estimates",
                expected_output="Itemized cost breakdown with contingency",
                canvas_section="estimates",
                tools_used=["deepseek"],
                duration_estimate_seconds=60
            ),
            DemoStep(
                agent="koda",
                action="generate",
                description="Create project timeline",
                expected_output="Gantt-style timeline with milestones",
                canvas_section="timeline",
                tools_used=["deepseek"],
                duration_estimate_seconds=30
            ),
            DemoStep(
                agent="prax",
                action="synthesize",
                description="Compile bid package with risk assessment",
                expected_output="Complete bid with payment schedule and risk factors",
                canvas_section="bid_summary",
                duration_estimate_seconds=30
            )
        ]

    def get_sample_input(self) -> Dict[str, Any]:
        return {
            "project_type": "Commercial Office Renovation",
            "square_feet": 5000,
            "location": "Downtown",
            "scope": [
                "Demolition of existing layout",
                "New electrical throughout",
                "HVAC system upgrade",
                "Interior finishing (paint, flooring, ceilings)",
                "Accessibility compliance updates"
            ],
            "constraints": {
                "budget_range": "$200,000 - $300,000",
                "timeline": "Must complete within 90 days",
                "working_hours": "After 6pm and weekends only"
            },
            "question": "Prepare a bid for a 5,000 sq ft commercial office renovation in downtown"
        }

    def get_deliverable(self) -> DemoDeliverable:
        return DemoDeliverable(
            title="Construction Bid Package",
            format="pdf",
            description="Complete bid with estimates, timeline, and risk assessment",
            sections=[
                "Executive Summary",
                "Scope of Work",
                "Phase Breakdown",
                "Material Estimates",
                "Labor Estimates",
                "Permit Requirements",
                "Project Timeline",
                "Risk Assessment",
                "Payment Schedule",
                "Terms and Conditions"
            ]
        )

    def get_value_proposition(self) -> ValueProposition:
        return ValueProposition(
            time_saved="2 days → 1 hour",
            cost_saved="More accurate bids = better margins",
            competitive_advantage="Submit more bids, win more contracts"
        )

    def get_cost_breakdown_template(self) -> Dict[str, Any]:
        """Sample cost breakdown structure."""
        return {
            "categories": [
                {"name": "Materials", "percentage": 50},
                {"name": "Labor", "percentage": 35},
                {"name": "Permits", "percentage": 2},
                {"name": "Equipment", "percentage": 5},
                {"name": "Contingency", "percentage": 8}
            ],
            "typical_margins": {
                "competitive": "8-12%",
                "standard": "15-20%",
                "premium": "20-25%"
            }
        }
