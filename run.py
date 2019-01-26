#!/usr/bin/env python3
import os, sys
from subprocess import Popen

os.chdir(os.path.dirname(os.path.abspath(__file__)))

Popen((sys.executable, 'powershell_bot.py'))
Popen((sys.executable, 'powershell_bot-recheck.py'))
