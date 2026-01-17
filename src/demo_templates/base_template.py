"""
Base Template for Demo Scenarios

All sector-specific templates inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DemoStep:
    """A single step in a demo flow."""
    agent: str  # prax, cairn, koda
    action: str  # analyze, research, generate, synthesize
    description: str
    expected_output: str
    canvas_section: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    duration_estimate_seconds: int = 30


@dataclass
class DemoDeliverable:
    """Output deliverable from a demo."""
    title: str
    format: str  # pdf, markdown, json, spreadsheet
    description: str
    sections: List[str] = field(default_factory=list)


@dataclass
class ValueProposition:
    """Value proposition for the demo."""
    time_saved: str  # e.g., "4 hours → 5 minutes"
    cost_saved: Optional[str] = None  # e.g., "$10,000/year"
    competitive_advantage: Optional[str] = None


class BaseTemplate(ABC):
    """
    Base class for demo templates.

    Subclasses must implement:
    - SECTOR_ID: Unique identifier (e.g., "food_services")
    - SECTOR_NAME: Display name (e.g., "Food Services")
    - DESCRIPTION: Brief description
    - PAIN_POINTS: List of problems this solves
    - get_demo_steps(): Returns list of DemoStep
    - get_sample_input(): Returns sample input data
    - get_deliverable(): Returns DemoDeliverable spec
    """

    # Must be overridden by subclasses
    SECTOR_ID: str = ""
    SECTOR_NAME: str = ""
    DESCRIPTION: str = ""
    PAIN_POINTS: List[str] = []

    def __init__(self):
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.results: Dict[str, Any] = {}

    @abstractmethod
    def get_demo_steps(self) -> List[DemoStep]:
        """Return the sequence of demo steps."""
        pass

    @abstractmethod
    def get_sample_input(self) -> Dict[str, Any]:
        """Return sample input data for the demo."""
        pass

    @abstractmethod
    def get_deliverable(self) -> DemoDeliverable:
        """Return the deliverable specification."""
        pass

    def get_value_proposition(self) -> ValueProposition:
        """Return the value proposition. Override for custom values."""
        return ValueProposition(
            time_saved="Hours → Minutes",
            cost_saved=None,
            competitive_advantage=None
        )

    def get_opening_prompt(self, investor_name: str = "Investor") -> str:
        """Generate the opening prompt for the demo."""
        return f"""
Hello {investor_name}! I'm Prax, and I'll be coordinating today's demo.

We're going to show you how our multi-agent system can help with {self.SECTOR_NAME.lower()}.

**Pain points we address:**
{chr(10).join(f'- {p}' for p in self.PAIN_POINTS)}

Let me know what specific challenge you'd like us to tackle, or I can use a sample scenario.
"""

    def get_prax_delegation_prompt(self, user_input: str) -> str:
        """Generate Prax's delegation message."""
        steps = self.get_demo_steps()
        cairn_steps = [s for s in steps if s.agent == 'cairn']
        koda_steps = [s for s in steps if s.agent == 'koda']

        prompt = f"I'll coordinate this analysis. Here's the plan:\n\n"

        if cairn_steps:
            prompt += f"**Cairn** will handle:\n"
            for s in cairn_steps:
                prompt += f"- {s.description}\n"
            prompt += "\n"

        if koda_steps:
            prompt += f"**Koda** will handle:\n"
            for s in koda_steps:
                prompt += f"- {s.description}\n"
            prompt += "\n"

        prompt += "Let's begin."
        return prompt

    def get_closing_summary(self, results: Dict[str, Any]) -> str:
        """Generate the closing summary."""
        vp = self.get_value_proposition()
        deliverable = self.get_deliverable()

        summary = f"""
## Summary

We've completed the {self.SECTOR_NAME} analysis.

**Deliverable:** {deliverable.title} ({deliverable.format})

**Value delivered:**
- Time saved: {vp.time_saved}
"""
        if vp.cost_saved:
            summary += f"- Cost impact: {vp.cost_saved}\n"
        if vp.competitive_advantage:
            summary += f"- Competitive advantage: {vp.competitive_advantage}\n"

        summary += "\nThis deliverable is yours to keep. How would you like to proceed?"
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary for API responses."""
        return {
            'sector_id': self.SECTOR_ID,
            'sector_name': self.SECTOR_NAME,
            'description': self.DESCRIPTION,
            'pain_points': self.PAIN_POINTS,
            'steps': [
                {
                    'agent': s.agent,
                    'action': s.action,
                    'description': s.description,
                    'canvas_section': s.canvas_section,
                    'duration_estimate': s.duration_estimate_seconds
                }
                for s in self.get_demo_steps()
            ],
            'deliverable': {
                'title': self.get_deliverable().title,
                'format': self.get_deliverable().format,
                'description': self.get_deliverable().description
            },
            'value_proposition': {
                'time_saved': self.get_value_proposition().time_saved,
                'cost_saved': self.get_value_proposition().cost_saved,
                'competitive_advantage': self.get_value_proposition().competitive_advantage
            }
        }
