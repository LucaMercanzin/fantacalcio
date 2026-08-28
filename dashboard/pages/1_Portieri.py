import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from dashboard.common import get_db_connection
from dashboard.components import render_goalkeeper_depth_chart

render_goalkeeper_depth_chart(get_db_connection())
