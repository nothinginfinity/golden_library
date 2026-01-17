"""
Real Estate Demo Template

Target: Real estate investors, property managers, REITs.
"""

from typing import Dict, List, Any
from .base_template import BaseTemplate, DemoStep, DemoDeliverable, ValueProposition
from .template_registry import TemplateRegistry


@TemplateRegistry.register
class RealEstateTemplate(BaseTemplate):
    """Demo template for real estate investment analysis."""

    SECTOR_ID = "real_estate"
    SECTOR_NAME = "Real Estate"
    DESCRIPTION = "Property analysis, market research, ROI modeling"
    PAIN_POINTS = [
        "Property analysis time",
        "Market research depth",
        "Investment decision speed",
        "Comparable sales analysis"
    ]

    def get_demo_steps(self) -> List[DemoStep]:
        return [
            DemoStep(
                agent="prax",
                action="coordinate",
                description="Coordinate investment analysis workflow",
                expected_output="Task delegation for market research and ROI modeling",
                duration_estimate_seconds=15
            ),
            DemoStep(
                agent="cairn",
                action="research",
                description="Research neighborhood and market data",
                expected_output="Area appreciation trends, demographics, development plans",
                canvas_section="market_research",
                tools_used=["web_search", "deepseek"],
                duration_estimate_seconds=60
            ),
            DemoStep(
                agent="cairn",
                action="analyze",
                description="Analyze comparable sales",
                expected_output="Comp analysis with price range estimates",
                canvas_section="comp_analysis",
                tools_used=["deepseek"],
                duration_estimate_seconds=45
            ),
            DemoStep(
                agent="koda",
                action="generate",
                description="Calculate ROI scenarios",
                expected_output="Rental and flip ROI projections",
                canvas_section="roi_analysis",
                tools_used=["deepseek"],
                duration_estimate_seconds=45
            ),
            DemoStep(
                agent="prax",
                action="synthesize",
                description="Create investment summary with risk factors",
                expected_output="Executive summary with buy/hold/pass recommendation",
                canvas_section="summary",
                duration_estimate_seconds=30
            )
        ]

    def get_sample_input(self) -> Dict[str, Any]:
        return {
            "property_address": "123 Main St, Austin, TX 78701",
            "property_type": "Single Family Home",
            "asking_price": 400000,
            "square_feet": 1800,
            "bedrooms": 3,
            "bathrooms": 2,
            "year_built": 1985,
            "investment_strategy": ["rental", "flip"],
            "question": "Analyze 123 Main St, Austin TX for investment potential"
        }

    def get_deliverable(self) -> DemoDeliverable:
        return DemoDeliverable(
            title="Property Investment Analysis",
            format="pdf",
            description="Comprehensive investment analysis with ROI scenarios",
            sections=[
                "Executive Summary",
                "Property Overview",
                "Neighborhood Analysis",
                "Market Trends (3-year)",
                "Comparable Sales (5 properties)",
                "Rental ROI Projection",
                "Flip ROI Projection",
                "Risk Factors",
                "Recommendation"
            ]
        )

    def get_value_proposition(self) -> ValueProposition:
        return ValueProposition(
            time_saved="4 hours research → 10 minutes",
            cost_saved="Analyze 10 properties while competitors analyze 1",
            competitive_advantage="Faster offers, better data-driven decisions"
        )
