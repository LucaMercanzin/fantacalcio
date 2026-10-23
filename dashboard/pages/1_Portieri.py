import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.access import require_read_access
from dashboard.common import get_db_connection
from dashboard.components import render_goalkeeper_depth_chart

require_read_access("portieri")
render_goalkeeper_depth_chart(get_db_connection())
