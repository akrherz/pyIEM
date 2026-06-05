"""Bundled website templates."""

import importlib


def get_site_template(site: str, filename: str):
    """Helper for getting a template.

    Args:
      site (str): the site to get the template for, such as "dep"
      filename (str): the template file to open.
    """
    mod = importlib.import_module(f"pyiem.templates.{site}")

    return mod.get_template(filename)
