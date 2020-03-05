"""Our default IEM template environ."""
import datetime

from jinja2 import Environment, PackageLoader, select_autoescape


TEMPLATE_ENV = Environment(
    loader=PackageLoader("pyiem", "templates/iem"),
    autoescape=select_autoescape(["html", "xml"]),
)


def get_template(filename):
    """Helper for getting a template.

    Args:
      filename (str): the template file to open.
    """
    tpl = TEMPLATE_ENV.get_template(filename)
    tpl.globals["footer_year"] = datetime.date.today().year
    return tpl


# Default template used downstream.
TEMPLATE = get_template("full.j2")
