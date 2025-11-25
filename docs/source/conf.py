# flake8: noqa
"""Sphinx configuration for pyIEM documentation."""

from datetime import date

import pyiem

# -- Project information -----------------------------------------------------

project = "pyIEM"
author = "Daryl Herzmann"
copyright = f"2015-{date.today().year}, {author}"

# Version info
version = pyiem.__version__
release = version

# -- General configuration ---------------------------------------------------

# Minimum Sphinx version
needs_sphinx = "7.0"

# Extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.autodoc_pydantic",
]

# Napoleon settings for Google/NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Pydantic autodoc settings - show field descriptions from Field()
autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_validator_summary = False
autodoc_pydantic_model_show_field_summary = True
autodoc_pydantic_field_list_validators = False
autodoc_pydantic_field_show_constraints = True

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autodoc_typehints_format = "short"

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "geopandas": ("https://geopandas.org/en/stable/", None),
    "shapely": ("https://shapely.readthedocs.io/en/stable/", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
}

# Source settings
templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Syntax highlighting
pygments_style = "sphinx"

# -- Options for HTML output -------------------------------------------------

# Use pydata-sphinx-theme for modern navigation with expandable sidebar
html_theme = "pydata_sphinx_theme"

html_theme_options = {
    "github_url": "https://github.com/akrherz/pyIEM",
    "show_toc_level": 2,
    "navigation_with_keys": True,
    "show_nav_level": 2,
    "navigation_depth": 4,
    "collapse_navigation": False,
    "icon_links": [
        {
            "name": "IEM",
            "url": "https://mesonet.agron.iastate.edu",
            "icon": "fa-solid fa-cloud-sun",
        },
    ],
    "secondary_sidebar_items": ["page-toc", "edit-this-page"],
    "primary_sidebar_end": ["sidebar-ethical-ads"],
}

html_title = f"pyIEM {version}"
html_short_title = "pyIEM"

# Don't show source links
html_show_sourcelink = False

# Show last updated
html_last_updated_fmt = "%b %d, %Y"

# Output file base name for HTML help builder
htmlhelp_basename = "pyIEMdoc"

# -- Options for LaTeX output ------------------------------------------------

latex_elements = {}

latex_documents = [
    ("index", "pyIEM.tex", "pyIEM Documentation", author, "manual")
]

# -- Options for manual page output ------------------------------------------

man_pages = [("index", "pyiem", "pyIEM Documentation", [author], 1)]

# -- Options for Texinfo output ----------------------------------------------

texinfo_documents = [
    (
        "index",
        "pyIEM",
        "pyIEM Documentation",
        author,
        "pyIEM",
        "Python library for processing weather data from IEM and NWS.",
        "Miscellaneous",
    )
]

# -- Suppress warnings for optional packages ---------------------------------

# Don't fail on missing optional modules
autodoc_mock_imports = []
