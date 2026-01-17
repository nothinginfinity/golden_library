"""
Food Services Demo Template

Target: Coffee shop owners, restaurant chains, food service businesses.
"""

from typing import Dict, List, Any
from .base_template import BaseTemplate, DemoStep, DemoDeliverable, ValueProposition
from .template_registry import TemplateRegistry


@TemplateRegistry.register
class FoodServicesTemplate(BaseTemplate):
    """Demo template for food service businesses (coffee shops, restaurants)."""

    SECTOR_ID = "food_services"
    SECTOR_NAME = "Food Services"
    DESCRIPTION = "Multi-location performance analysis, inventory optimization, staffing recommendations"
    PAIN_POINTS = [
        "Inventory waste across locations",
        "Staffing optimization",
        "Menu performance variance",
        "Location-specific insights"
    ]

    def get_demo_steps(self) -> List[DemoStep]:
        return [
            DemoStep(
                agent="prax",
                action="coordinate",
                description="Coordinate location performance analysis",
                expected_output="Task delegation to Cairn and Koda",
                duration_estimate_seconds=15
            ),
            DemoStep(
                agent="cairn",
                action="analyze",
                description="Analyze sales patterns across locations",
                expected_output="Location variance report, top/bottom performers",
                canvas_section="analysis",
                tools_used=["deepseek"],
                duration_estimate_seconds=45
            ),
            DemoStep(
                agent="cairn",
                action="research",
                description="Identify inventory waste patterns",
                expected_output="Waste hotspots by location and product",
                canvas_section="analysis",
                tools_used=["deepseek"],
                duration_estimate_seconds=30
            ),
            DemoStep(
                agent="koda",
                action="generate",
                description="Generate optimization recommendations",
                expected_output="Actionable inventory and staffing adjustments",
                canvas_section="recommendations",
                tools_used=["deepseek"],
                duration_estimate_seconds=45
            ),
            DemoStep(
                agent="prax",
                action="synthesize",
                description="Create location-specific action plan",
                expected_output="Executive summary with prioritized actions",
                canvas_section="summary",
                duration_estimate_seconds=30
            )
        ]

    def get_sample_input(self) -> Dict[str, Any]:
        return {
            "business_type": "Coffee Shop Chain",
            "locations": 5,
            "sample_data": {
                "location_1": {
                    "name": "Downtown",
                    "monthly_sales": 45000,
                    "top_items": ["Latte", "Croissant", "Cold Brew"],
                    "waste_percentage": 12
                },
                "location_2": {
                    "name": "University",
                    "monthly_sales": 38000,
                    "top_items": ["Cold Brew", "Bagel", "Espresso"],
                    "waste_percentage": 8
                },
                "location_3": {
                    "name": "Mall",
                    "monthly_sales": 52000,
                    "top_items": ["Frappuccino", "Muffin", "Latte"],
                    "waste_percentage": 15
                },
                "location_4": {
                    "name": "Suburbs",
                    "monthly_sales": 28000,
                    "top_items": ["Drip Coffee", "Scone", "Tea"],
                    "waste_percentage": 18
                },
                "location_5": {
                    "name": "Airport",
                    "monthly_sales": 65000,
                    "top_items": ["Espresso", "Sandwich", "Bottled Water"],
                    "waste_percentage": 5
                }
            },
            "question": "Analyze my 5 coffee shop locations and tell me where to cut waste and optimize inventory"
        }

    def get_deliverable(self) -> DemoDeliverable:
        return DemoDeliverable(
            title="Location Performance & Optimization Report",
            format="pdf",
            description="Multi-location analysis with specific recommendations per site",
            sections=[
                "Executive Summary",
                "Location Performance Rankings",
                "Inventory Waste Analysis",
                "Product Mix Recommendations",
                "Staffing Optimization",
                "30-Day Action Plan"
            ]
        )

    def get_value_proposition(self) -> ValueProposition:
        return ValueProposition(
            time_saved="4 hours/week → 5 minutes",
            cost_saved="~$10,000/year in reduced waste + manager time",
            competitive_advantage="Data-driven decisions across all locations"
        )
