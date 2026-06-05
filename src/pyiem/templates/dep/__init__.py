"""Our default DEP template environ."""

import datetime

from jinja2 import Environment, PackageLoader

# Can not support auto_escape at this time as parts of the template are
# being provided verbatim.
TEMPLATE_ENV = Environment(loader=PackageLoader("pyiem", "templates/dep"))


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
