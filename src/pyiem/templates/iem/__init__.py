"""Our default IEM template environ."""

import datetime
import json
import os

from jinja2 import Environment, PackageLoader, select_autoescape

TEMPLATE_ENV = Environment(
    loader=PackageLoader("pyiem", "templates/iem"),
    autoescape=select_autoescape(
        enabled_extensions=("html", "xml", "j2"),
        default_for_string=True,
    ),
)
NAVBAR_JSON_FN = "/opt/iem/config/navbar.json"


def get_template(filename):
    """Helper for getting a template.

    Args:
      filename (str): the template file to open.
    """
    tpl = TEMPLATE_ENV.get_template(filename)
    tpl.globals["footer_year"] = datetime.date.today().year
    tpl.globals["navbardata"] = []
    if os.path.isfile(NAVBAR_JSON_FN):
        with open(NAVBAR_JSON_FN, "r", encoding="utf8") as fh:
            tpl.globals["navbardata"] = json.load(fh)["tabs"]
    return tpl


# Default template used downstream.
TEMPLATE = get_template("full.j2")
