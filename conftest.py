# -*- coding: utf-8 -*-
"""让 pytest 能把项目根目录加进 sys.path，从而 import diagnose / app / partners。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
