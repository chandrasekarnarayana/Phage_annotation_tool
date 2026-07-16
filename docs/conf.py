"""Sphinx configuration for the Phage Annotator documentation site."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = DOCS_ROOT.parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(DOCS_ROOT / "_build" / "matplotlib"))

project = "Phage Annotator"
author = "Chandrasekar Subramani Narayana"
copyright = f"{datetime.now().year}, {author}"
release = "1.0.1"
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]

if os.environ.get("PHAGE_DOCS_INTERSPHINX") == "1":
    extensions.append("sphinx.ext.intersphinx")

autosummary_generate = False
autodoc_typehints = "none"
autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
napoleon_google_docstring = True
napoleon_numpy_docstring = True
suppress_warnings = ["ref.python"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "_generated"]
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

html_theme = os.environ.get("PHAGE_DOCS_THEME", "pydata_sphinx_theme")
html_static_path = ["_static"]
html_css_files = ["phage-docs.css"]
html_title = "Phage Annotator Documentation"
html_logo = None
html_favicon = None
html_theme_options = {
    "show_toc_level": 2,
    "navigation_depth": 4,
    "collapse_navigation": False,
    "secondary_sidebar_items": ["page-toc", "sourcelink"],
    "navbar_align": "left",
}

myst_heading_anchors = 3
myst_enable_extensions = ["colon_fence", "deflist", "fieldlist", "substitution"]

intersphinx_mapping = (
    {
        "python": ("https://docs.python.org/3", None),
        "numpy": ("https://numpy.org/doc/stable/", None),
        "matplotlib": ("https://matplotlib.org/stable/", None),
        "sklearn": ("https://scikit-learn.org/stable/", None),
        "pandas": ("https://pandas.pydata.org/docs/", None),
    }
    if "sphinx.ext.intersphinx" in extensions
    else {}
)
