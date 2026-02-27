"""Label taxonomy system for annotation management.

Provides label organization, presets, and batch operations.
Supports hierarchical labels and label groups for reviewer workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class LabelColor(Enum):
    """Standard colors for labels."""
    RED = "#E74C3C"
    GREEN = "#27AE60"
    BLUE = "#3498DB"
    YELLOW = "#F39C12"
    PURPLE = "#9B59B6"
    CYAN = "#1ABC9C"
    GRAY = "#95A5A6"


@dataclass
class LabelDefinition:
    """Definition of a label/class.
    
    Parameters
    ----------
    name : str
        Canonical label name (unique).
    display_name : str
        Human-readable name for UI.
    description : str
        Help text and usage guidance.
    color : str
        Hex color code for UI rendering.
    aliases : List[str]
        Alternative names (for import normalization).
    category : str
        Group/category for organization.
    parent : Optional[str]
        Parent label for hierarchical organization.
    """
    
    name: str
    display_name: str
    description: str = ""
    color: str = LabelColor.GRAY.value
    aliases: List[str] = field(default_factory=list)
    category: str = "default"
    parent: Optional[str] = None
    
    def __post_init__(self):
        """Normalize name on creation."""
        if not self.display_name:
            self.display_name = self.name.replace("_", " ").title()


@dataclass
class LabelTaxonomy:
    """Hierarchical taxonomy of annotation labels.
    
    Supports:
    - Canonical label definitions with colors and descriptions
    - Label aliases for CSV import normalization
    - Hierarchical organization (parent-child)
    - Categories/groups for UI organization
    """
    
    labels: Dict[str, LabelDefinition] = field(default_factory=dict)
    categories: Dict[str, str] = field(default_factory=dict)  # category_name -> description
    
    def add_label(self, definition: LabelDefinition) -> None:
        """Add a label definition.
        
        Parameters
        ----------
        definition : LabelDefinition
            Label to add.
        
        Raises
        ------
        ValueError
            If label name already exists.
        """
        if definition.name in self.labels:
            raise ValueError(f"Label '{definition.name}' already exists")
        self.labels[definition.name] = definition
    
    def add_category(self, name: str, description: str = "") -> None:
        """Add a label category.
        
        Parameters
        ----------
        name : str
            Category name.
        description : str
            Category description.
        """
        self.categories[name] = description
    
    def get_label(self, name: str) -> Optional[LabelDefinition]:
        """Get label definition by name or alias.
        
        Parameters
        ----------
        name : str
            Label name or alias.
        
        Returns
        -------
        LabelDefinition or None
            Label definition if found.
        """
        # Direct match
        if name in self.labels:
            return self.labels[name]
        
        # Check aliases
        for label in self.labels.values():
            if name in label.aliases:
                return label
        
        return None
    
    def normalize_label(self, name: str) -> str:
        """Normalize label name to canonical form.
        
        Parameters
        ----------
        name : str
            Label name or alias.
        
        Returns
        -------
        str
            Canonical label name, or original if not found.
        """
        label = self.get_label(name)
        return label.name if label else name
    
    def get_labels_by_category(self, category: str) -> List[LabelDefinition]:
        """Get all labels in a category.
        
        Parameters
        ----------
        category : str
            Category name.
        
        Returns
        -------
        List[LabelDefinition]
            Labels in the category (sorted by name).
        """
        labels = [
            label for label in self.labels.values()
            if label.category == category
        ]
        return sorted(labels, key=lambda l: l.display_name)
    
    def get_all_labels(self) -> List[LabelDefinition]:
        """Get all labels (sorted by name)."""
        return sorted(self.labels.values(), key=lambda l: l.display_name)
    
    def get_categories(self) -> List[str]:
        """Get all category names."""
        return sorted(self.categories.keys())
    
    def get_label_names(self) -> List[str]:
        """Get all canonical label names."""
        return sorted(self.labels.keys())
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "labels": {
                name: {
                    "display_name": label.display_name,
                    "description": label.description,
                    "color": label.color,
                    "aliases": label.aliases,
                    "category": label.category,
                    "parent": label.parent,
                }
                for name, label in self.labels.items()
            },
            "categories": self.categories,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> LabelTaxonomy:
        """Deserialize from dictionary."""
        taxonomy = cls()
        
        # Load labels
        for name, label_data in data.get("labels", {}).items():
            definition = LabelDefinition(
                name=name,
                display_name=label_data.get("display_name", name),
                description=label_data.get("description", ""),
                color=label_data.get("color", LabelColor.GRAY.value),
                aliases=label_data.get("aliases", []),
                category=label_data.get("category", "default"),
                parent=label_data.get("parent"),
            )
            taxonomy.add_label(definition)
        
        # Load categories
        for category_name, description in data.get("categories", {}).items():
            taxonomy.add_category(category_name, description)
        
        return taxonomy


def create_default_taxonomy() -> LabelTaxonomy:
    """Create a default label taxonomy.
    
    Returns
    -------
    LabelTaxonomy
        Pre-populated taxonomy with common microscopy labels.
    """
    taxonomy = LabelTaxonomy()
    
    # Add categories
    taxonomy.add_category("particles", "Particle/feature labels")
    taxonomy.add_category("defects", "Defect/artifact labels")
    taxonomy.add_category("metadata", "Metadata/admin labels")
    
    # Add baseline labels
    taxonomy.add_label(LabelDefinition(
        name="phage",
        display_name="Phage",
        description="Bacteriophage particles",
        color=LabelColor.GREEN.value,
        category="particles",
    ))
    
    taxonomy.add_label(LabelDefinition(
        name="artifact",
        display_name="Artifact",
        description="Image artifact or dust",
        color=LabelColor.RED.value,
        category="defects",
    ))
    
    taxonomy.add_label(LabelDefinition(
        name="flagged",
        display_name="Flagged",
        description="Flagged for manual review",
        color=LabelColor.YELLOW.value,
        category="metadata",
    ))
    
    return taxonomy
