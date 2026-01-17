"""
Demo Templates for Investor Presentations

Sector-specific templates that deliver real value during demos.
"""

from .base_template import BaseTemplate
from .template_registry import TemplateRegistry, get_template, list_templates

__all__ = [
    'BaseTemplate',
    'TemplateRegistry',
    'get_template',
    'list_templates'
]
