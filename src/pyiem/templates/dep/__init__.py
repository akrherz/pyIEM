"""Our default DEP template environ."""

import datetime

from jinja2 import Environment, PackageLoader, select_autoescape

TEMPLATE_ENV = Environment(
    loader=PackageLoader("pyiem", "templates/dep"),
    autoescape=select_autoescape(
        enabled_extensions=("html", "xml", "j2"),
        default_for_string=True,
    ),
)


def get_template(filename):
    """Helper for getting a template.

    Args:
      filename (str): the template file to open.
    """
    tpl = TEMPLATE_ENV.get_template(filename)
    tpl.globals["footer_year"] = datetime.date.today().year
    tpl.globals["navbardata"] = []
    return tpl


# Default template used downstream.
TEMPLATE = get_template("full.j2")
