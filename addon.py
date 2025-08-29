import xbmc
from resources.lib import main

try:
    main.run()
except Exception as e:
    xbmc.log(f"Error in addon.py: {e}", level=xbmc.LOGERROR)