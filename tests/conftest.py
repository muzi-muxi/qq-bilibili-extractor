import sys
import os

# Ensure tests can import the top-level module when running pytest from any CWD
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
