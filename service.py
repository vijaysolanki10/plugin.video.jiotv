# -*- coding: utf-8 -*-

import xbmc
from resources.lib.utils import getBool, runPgMain

try:
    if getBool("m3ugen"):
        xbmc.executebuiltin(f"{runPgMain}m3ugen/?notify=no")
except Exception as e:
    xbmc.log(f"Error in service.py: {e}", level=xbmc.LOGERROR)