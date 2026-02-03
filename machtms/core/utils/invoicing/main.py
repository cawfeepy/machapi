import io
import logging
import os
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSS_FILE = os.path.join(BASE_DIR, 'templates/static/styles.css')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

file_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def get_template(template_file):
    return file_env.get_template(template_file)


def get_filename(S_load: dict) -> str:
    return f"{S_load['customer']['shorthand']}_{S_load['invoice_id']}_{S_load['reference']}_invoice.pdf"


def invoice_write_bytes(serialized_load) -> bytes | None:
    # Lazy import to avoid loading weasyprint at module import time
    from weasyprint import HTML, CSS

    template = get_template('invoice.jinja')
    html_string = template.render(serialized_load)
    css_file = os.path.join(BASE_DIR, 'templates/static/styles.css')
    pdf = HTML(string=html_string).write_pdf(stylesheets=[CSS(filename=css_file)])
    return pdf


def generate_invoice(S_load) -> io.BytesIO:
    # time_ms, pdf = time_execution(write_to_file, load_data)
    # logger.debug(time_ms)
    pdf = invoice_write_bytes(S_load)

    if pdf is not None:
        return io.BytesIO(pdf)
    else:
        raise Exception("pdf data is empty")
