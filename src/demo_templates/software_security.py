"""
Software Security Demo Template

Target: Security companies, MSPs, compliance consultants.
"""

from typing import Dict, List, Any
from .base_template import BaseTemplate, DemoStep, DemoDeliverable, ValueProposition
from .template_registry import TemplateRegistry


@TemplateRegistry.register
class SoftwareSecurityTemplate(BaseTemplate):
    """Demo template for software security and compliance businesses."""

    SECTOR_ID = "software_security"
    SECTOR_NAME = "Software Security"
    DESCRIPTION = "Security assessments, compliance mapping, threat analysis"
    PAIN_POINTS = [
        "Threat analysis speed",
        "Compliance documentation burden",
        "Scaling security expertise",
        "Client assessment turnaround"
    ]

    def get_demo_steps(self) -> List[DemoStep]:
        return [
            DemoStep(
                agent="prax",
                action="coordinate",
                description="Coordinate security assessment workflow",
                expected_output="Task delegation for threat modeling and compliance",
                duration_estimate_seconds=15
            ),
            DemoStep(
                agent="cairn",
                action="research",
                description="Analyze tech stack for relevant CVEs",
                expected_output="Top 10 CVEs with severity ratings",
                canvas_section="threat_analysis",
                tools_used=["web_search", "deepseek"],
                duration_estimate_seconds=60
            ),
            DemoStep(
                agent="cairn",
                action="analyze",
                description="Map to SOC2 compliance controls",
                expected_output="Control mapping with gap identification",
                canvas_section="compliance_mapping",
                tools_used=["deepseek"],
                duration_estimate_seconds=45
            ),
            DemoStep(
                agent="koda",
                action="generate",
                description="Generate compliance checklist",
                expected_output="47-point SOC2 checklist with priorities",
                canvas_section="checklist",
                tools_used=["deepseek"],
                duration_estimate_seconds=45
            ),
            DemoStep(
                agent="koda",
                action="generate",
                description="Create remediation roadmap",
                expected_output="Prioritized remediation steps",
                canvas_section="roadmap",
                tools_used=["deepseek"],
                duration_estimate_seconds=30
            ),
            DemoStep(
                agent="prax",
                action="synthesize",
                description="Compile client-ready assessment report",
                expected_output="Executive summary with risk scores",
                canvas_section="summary",
                duration_estimate_seconds=30
            )
        ]

    def get_sample_input(self) -> Dict[str, Any]:
        return {
            "client_type": "SaaS Platform",
            "tech_stack": {
                "cloud": "AWS",
                "backend": "Node.js",
                "database": "PostgreSQL",
                "frontend": "React",
                "auth": "Auth0"
            },
            "compliance_target": "SOC2 Type II",
            "question": "New client needs SOC2 compliance assessment for their SaaS platform running on AWS with Node.js and PostgreSQL"
        }

    def get_deliverable(self) -> DemoDeliverable:
        return DemoDeliverable(
            title="SOC2 Gap Analysis & Remediation Report",
            format="pdf",
            description="Comprehensive security assessment with prioritized remediation",
            sections=[
                "Executive Summary",
                "Tech Stack Risk Analysis",
                "CVE Assessment",
                "SOC2 Control Mapping",
                "Gap Analysis",
                "Remediation Roadmap",
                "Timeline Estimates"
            ]
        )

    def get_value_proposition(self) -> ValueProposition:
        return ValueProposition(
            time_saved="8-hour assessment → 30 minutes",
            cost_saved="Offer AI-augmented assessments at premium pricing",
            competitive_advantage="10x assessment capacity with same team"
        )

    def get_security_callouts(self) -> List[str]:
        """Security-specific talking points for the demo."""
        return [
            "All data stays in YOUR environment—no external API data sharing",
            "Every AI action logged in audit trail (show Phase 4C.4 database)",
            "Tool permissions controlled per-agent (show Phase 4C.3 gateway)",
            "You can offer AI-assisted audits to YOUR clients using this platform"
        ]
