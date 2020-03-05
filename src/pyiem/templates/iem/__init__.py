"""Our default IEM template environ."""
import datetime

from jinja2 import Environment, PackageLoader, select_autoescape


TEMPLATE_ENV = Environment(
    loader=PackageLoader("pyiem", "templates/iem"),
    autoescape=select_autoescape(["html", "xml"]),
)

# Default template used downstream.
TEMPLATE = TEMPLATE_ENV.get_template("full.j2")
TEMPLATE.globals["footer_year"] = datetime.date.today().year
