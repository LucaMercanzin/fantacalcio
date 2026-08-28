import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.common import get_db_connection
from dashboard.components import render_role_page

render_role_page(get_db_connection(), "D", "Difensori")
