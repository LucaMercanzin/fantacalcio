import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.app import get_db_connection
from dashboard.components import render_role_page

render_role_page(get_db_connection(), "C", "Centrocampisti")
