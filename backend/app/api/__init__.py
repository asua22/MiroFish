"""
API Routes Module
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
config_bp = Blueprint('config', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import config  # noqa: E402, F401
from .data_ingestion import data_ingestion_bp  # noqa: E402, F401

__all__ = ['graph_bp', 'simulation_bp', 'report_bp', 'config_bp', 'data_ingestion_bp']
