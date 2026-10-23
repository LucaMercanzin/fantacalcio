import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.access import require_read_access
from dashboard.common import get_db_connection
from dashboard.components import render_role_page

require_read_access("attaccanti")
render_role_page(get_db_connection(), "A", "Attaccanti")
