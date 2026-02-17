import json
import os


try:
    from aqt import mw

    config = mw.addonManager.getConfig(__name__)
except AttributeError:
    with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
        config = json.loads(f.read())

def write_config():
    return mw.addonManager.writeConfig(__name__, config)
