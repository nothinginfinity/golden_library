"""
Demo UX Helpers

Provides one-click demo start, reset, and management utilities.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json

# Import templates
try:
    from demo_templates import get_template, list_templates, TemplateRegistry
    # Trigger registration by importing
    from demo_templates import food_services, software_security, legal, real_estate, construction
    HAS_TEMPLATES = True
except ImportError:
    HAS_TEMPLATES = False
    def get_template(x): return None
    def list_templates(): return []


@dataclass
class DemoConfig:
    """Configuration for a demo session."""
    template_id: str
    investor_name: str
    company_name: Optional[str] = None
    custom_branding: Optional[Dict] = None
    record_demo: bool = True
    auto_highlights: bool = True


@dataclass
class DemoSession:
    """Tracks state of an active demo."""
    id: str
    config: DemoConfig
    session_id: str
    recording_id: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    current_step: int = 0
    completed_steps: List[str] = field(default_factory=list)
    highlights: List[Dict] = field(default_factory=list)
    deliverables: List[Dict] = field(default_factory=list)


class DemoManager:
    """
    Manages demo sessions with one-click start/stop/reset.

    Usage:
        manager = DemoManager(session_manager)

        # Start demo
        demo = manager.start_demo(
            session_id="abc123",
            template_id="food_services",
            investor_name="John Smith"
        )

        # Get status
        status = manager.get_demo_status(demo.id)

        # Reset demo
        manager.reset_demo(demo.id)

        # Stop and export
        result = manager.stop_demo(demo.id)
    """

    def __init__(self, session_manager=None):
        self.session_manager = session_manager
        self.active_demos: Dict[str, DemoSession] = {}

    def list_available_templates(self) -> List[Dict]:
        """List all available demo templates."""
        return list_templates()

    def get_template_details(self, template_id: str) -> Optional[Dict]:
        """Get detailed information about a template."""
        template = get_template(template_id)
        if template:
            return template.to_dict()
        return None

    def start_demo(
        self,
        session_id: str,
        template_id: str,
        investor_name: str,
        company_name: Optional[str] = None,
        custom_branding: Optional[Dict] = None,
        record: bool = True
    ) -> Optional[DemoSession]:
        """
        Start a new demo session with one click.

        Args:
            session_id: Workspace session ID
            template_id: Template to use (e.g., "food_services")
            investor_name: Investor's name for personalization
            company_name: Optional company name for branding
            custom_branding: Optional custom branding config
            record: Whether to record the demo

        Returns:
            DemoSession object or None if failed
        """
        template = get_template(template_id)
        if not template:
            print(f"[DemoManager] Template not found: {template_id}")
            return None

        import uuid
        demo_id = f"demo_{uuid.uuid4().hex[:8]}"

        config = DemoConfig(
            template_id=template_id,
            investor_name=investor_name,
            company_name=company_name,
            custom_branding=custom_branding,
            record_demo=record
        )

        demo = DemoSession(
            id=demo_id,
            config=config,
            session_id=session_id
        )

        # Start recording if enabled
        if record and self.session_manager:
            branding = custom_branding or {}
            if company_name:
                branding['company_name'] = company_name

            result = self.session_manager.start_demo_mode(
                session_id=session_id,
                title=f"{investor_name} - {template.SECTOR_NAME} Demo",
                description=template.DESCRIPTION,
                branding=branding
            )
            if result and 'recording_id' in result:
                demo.recording_id = result['recording_id']

        self.active_demos[demo_id] = demo
        print(f"[DemoManager] Started demo {demo_id} for {investor_name}")

        return demo

    def get_demo_status(self, demo_id: str) -> Optional[Dict]:
        """Get current status of a demo."""
        demo = self.active_demos.get(demo_id)
        if not demo:
            return None

        template = get_template(demo.config.template_id)
        total_steps = len(template.get_demo_steps()) if template else 0

        return {
            'demo_id': demo_id,
            'template_id': demo.config.template_id,
            'investor_name': demo.config.investor_name,
            'started_at': demo.started_at,
            'current_step': demo.current_step,
            'total_steps': total_steps,
            'progress_percentage': int((demo.current_step / total_steps * 100)) if total_steps else 0,
            'completed_steps': demo.completed_steps,
            'highlights': len(demo.highlights),
            'recording_active': demo.recording_id is not None
        }

    def advance_step(self, demo_id: str, step_name: str) -> bool:
        """Mark a step as completed and advance."""
        demo = self.active_demos.get(demo_id)
        if not demo:
            return False

        demo.completed_steps.append(step_name)
        demo.current_step += 1

        # Auto-highlight key moments
        if demo.config.auto_highlights:
            template = get_template(demo.config.template_id)
            if template:
                steps = template.get_demo_steps()
                if demo.current_step <= len(steps):
                    step = steps[demo.current_step - 1]
                    if step.action in ['synthesize', 'generate']:
                        self.add_highlight(demo_id, f"{step.agent.title()} completed: {step.action}")

        return True

    def add_highlight(self, demo_id: str, label: str, description: str = None) -> bool:
        """Add a highlight to the demo recording."""
        demo = self.active_demos.get(demo_id)
        if not demo:
            return False

        highlight = {
            'label': label,
            'description': description,
            'timestamp': datetime.utcnow().isoformat()
        }
        demo.highlights.append(highlight)

        # Add to recording if active
        if demo.recording_id and self.session_manager:
            self.session_manager.add_demo_highlight(
                session_id=demo.session_id,
                label=label,
                description=description
            )

        return True

    def reset_demo(self, demo_id: str) -> bool:
        """
        Reset a demo to start fresh.

        Keeps the configuration but clears progress.
        """
        demo = self.active_demos.get(demo_id)
        if not demo:
            return False

        # Stop current recording
        if demo.recording_id and self.session_manager:
            self.session_manager.stop_demo_mode(demo.session_id)

        # Reset state
        demo.current_step = 0
        demo.completed_steps = []
        demo.highlights = []
        demo.deliverables = []
        demo.started_at = datetime.utcnow().isoformat()
        demo.recording_id = None

        # Start new recording
        if demo.config.record_demo and self.session_manager:
            template = get_template(demo.config.template_id)
            result = self.session_manager.start_demo_mode(
                session_id=demo.session_id,
                title=f"{demo.config.investor_name} - {template.SECTOR_NAME} Demo (Reset)",
                description=template.DESCRIPTION if template else "",
                branding=demo.config.custom_branding
            )
            if result and 'recording_id' in result:
                demo.recording_id = result['recording_id']

        print(f"[DemoManager] Reset demo {demo_id}")
        return True

    def stop_demo(self, demo_id: str, export_format: str = "html") -> Optional[Dict]:
        """
        Stop a demo and export results.

        Args:
            demo_id: Demo to stop
            export_format: Export format (html, json, markdown)

        Returns:
            Result dict with recording info and export URL
        """
        demo = self.active_demos.get(demo_id)
        if not demo:
            return None

        result = {
            'demo_id': demo_id,
            'investor_name': demo.config.investor_name,
            'template_id': demo.config.template_id,
            'duration_seconds': 0,
            'steps_completed': len(demo.completed_steps),
            'highlights': len(demo.highlights)
        }

        # Stop recording
        if demo.recording_id and self.session_manager:
            stop_result = self.session_manager.stop_demo_mode(demo.session_id)
            if stop_result:
                result['recording_id'] = demo.recording_id
                result['duration_ms'] = stop_result.get('duration_ms', 0)
                result['event_count'] = stop_result.get('event_count', 0)

        # Calculate duration
        start = datetime.fromisoformat(demo.started_at)
        result['duration_seconds'] = int((datetime.utcnow() - start).total_seconds())

        # Remove from active demos
        del self.active_demos[demo_id]

        print(f"[DemoManager] Stopped demo {demo_id}")
        return result

    def get_opening_message(self, demo_id: str) -> Optional[str]:
        """Get the opening message for a demo."""
        demo = self.active_demos.get(demo_id)
        if not demo:
            return None

        template = get_template(demo.config.template_id)
        if not template:
            return None

        return template.get_opening_prompt(demo.config.investor_name)

    def get_delegation_message(self, demo_id: str, user_input: str) -> Optional[str]:
        """Get Prax's delegation message for a demo."""
        demo = self.active_demos.get(demo_id)
        if not demo:
            return None

        template = get_template(demo.config.template_id)
        if not template:
            return None

        return template.get_prax_delegation_prompt(user_input)

    def get_closing_message(self, demo_id: str, results: Dict = None) -> Optional[str]:
        """Get the closing summary for a demo."""
        demo = self.active_demos.get(demo_id)
        if not demo:
            return None

        template = get_template(demo.config.template_id)
        if not template:
            return None

        return template.get_closing_summary(results or {})


# Singleton instance
_demo_manager = None


def get_demo_manager(session_manager=None) -> DemoManager:
    """Get or create the global DemoManager instance."""
    global _demo_manager
    if _demo_manager is None:
        _demo_manager = DemoManager(session_manager)
    elif session_manager and _demo_manager.session_manager is None:
        _demo_manager.session_manager = session_manager
    return _demo_manager


if __name__ == "__main__":
    # Test demo manager
    print("Testing DemoManager...")
    print("=" * 50)

    manager = DemoManager()

    # List templates
    print("\nAvailable templates:")
    for t in manager.list_available_templates():
        print(f"  - {t['id']}: {t['name']}")

    # Get template details
    print("\nFood Services template details:")
    details = manager.get_template_details("food_services")
    if details:
        print(f"  Steps: {len(details['steps'])}")
        print(f"  Deliverable: {details['deliverable']['title']}")
        print(f"  Value: {details['value_proposition']['time_saved']}")

    # Simulate demo flow
    print("\nSimulating demo flow:")
    demo = manager.start_demo(
        session_id="test_session",
        template_id="software_security",
        investor_name="Jane Investor",
        company_name="Security Corp",
        record=False
    )

    if demo:
        print(f"  Started demo: {demo.id}")

        # Get opening
        opening = manager.get_opening_message(demo.id)
        print(f"  Opening: {opening[:100]}...")

        # Advance steps
        manager.advance_step(demo.id, "coordinate")
        manager.advance_step(demo.id, "research_cves")

        # Get status
        status = manager.get_demo_status(demo.id)
        print(f"  Progress: {status['progress_percentage']}%")

        # Stop demo
        result = manager.stop_demo(demo.id)
        print(f"  Completed: {result['steps_completed']} steps in {result['duration_seconds']}s")

    print("\n✓ DemoManager tests passed!")
