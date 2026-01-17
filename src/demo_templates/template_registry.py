"""
Template Registry - Auto-discovers and manages demo templates.
"""

from typing import Dict, List, Optional, Type
from .base_template import BaseTemplate


class TemplateRegistry:
    """
    Registry for demo templates with auto-discovery.

    Usage:
        @TemplateRegistry.register
        class FoodServicesTemplate(BaseTemplate):
            SECTOR_ID = "food_services"
            ...

        # Get template
        template = TemplateRegistry.get_template("food_services")

        # List all
        templates = TemplateRegistry.list_templates()
    """

    _templates: Dict[str, Type[BaseTemplate]] = {}

    @classmethod
    def register(cls, template_class: Type[BaseTemplate]) -> Type[BaseTemplate]:
        """
        Decorator to register a template class.

        Usage:
            @TemplateRegistry.register
            class MyTemplate(BaseTemplate):
                SECTOR_ID = "my_sector"
                ...
        """
        if not template_class.SECTOR_ID:
            raise ValueError(f"Template {template_class.__name__} must define SECTOR_ID")

        cls._templates[template_class.SECTOR_ID] = template_class
        return template_class

    @classmethod
    def get_template(cls, sector_id: str) -> Optional[BaseTemplate]:
        """
        Get a template instance by sector ID.

        Args:
            sector_id: The sector identifier (e.g., "food_services")

        Returns:
            Template instance or None if not found
        """
        template_class = cls._templates.get(sector_id)
        if template_class:
            return template_class()
        return None

    @classmethod
    def list_templates(cls) -> List[Dict]:
        """
        List all registered templates.

        Returns:
            List of template info dicts with id, name, description, pain_points
        """
        return [
            {
                'id': t.SECTOR_ID,
                'name': t.SECTOR_NAME,
                'description': t.DESCRIPTION,
                'pain_points': t.PAIN_POINTS
            }
            for t in cls._templates.values()
        ]

    @classmethod
    def get_all_templates(cls) -> Dict[str, BaseTemplate]:
        """Get all template instances."""
        return {
            sector_id: template_class()
            for sector_id, template_class in cls._templates.items()
        }

    @classmethod
    def clear(cls):
        """Clear all registered templates (for testing)."""
        cls._templates.clear()


# Convenience functions
def get_template(sector_id: str) -> Optional[BaseTemplate]:
    """Get a template by sector ID."""
    return TemplateRegistry.get_template(sector_id)


def list_templates() -> List[Dict]:
    """List all available templates."""
    return TemplateRegistry.list_templates()
