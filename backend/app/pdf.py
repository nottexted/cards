from __future__ import annotations
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))

def render_pdf(template_name: str, context: dict) -> bytes:
    tpl = env.get_template(template_name)
    html = tpl.render(**context)
    return HTML(string=html, base_url=TEMPLATE_DIR).write_pdf()
