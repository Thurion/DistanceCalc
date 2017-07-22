"""
A Skeleton EDMC Plugin
"""
import sys
import ttk
import math
import Tkinter as tk

from config import config
import myNotebook as nb


this = sys.modules[__name__]	# For holding module globals

def plugin_start():
    """
    Start this plugin
    :return: Plugin name
    """
    sys.stderr.write("example plugin started\n")	# appears in %TMP%/EDMarketConnector.log in packaged Windows app
    return 'DistanceCalc'


def plugin_prefs(parent):
    """
    Return a TK Frame for adding to the EDMC settings dialog.
    """
    frame = nb.Frame(parent)
    frameTop = nb.Frame(frame)
    frameTop.grid(row = 0, column = 0, sticky=tk.W)
    frameBottom = nb.Frame(frame)
    frameBottom.grid(row = 1, column = 0, sticky=tk.W)

    this.settings = list()

    frameTop.columnconfigure(0, weight=10)
    frameTop.columnconfigure(1, weight=1)
    frameTop.columnconfigure(2, weight=1)
    frameTop.columnconfigure(3, weight=1)
    nb.Label(frameTop, text="Systems").grid(row = 0, column = 0, sticky=tk.W)
    nb.Label(frameTop, text="X").grid(row = 0, column = 1, sticky=tk.W)
    nb.Label(frameTop, text="Y").grid(row = 0, column = 2, sticky=tk.W)
    nb.Label(frameTop, text="Z").grid(row = 0, column = 3, sticky=tk.W)

    for i in range(3):
        systemEntry = nb.Entry(frameTop)
        systemEntry.grid(row = i + 1, column = 0, sticky=tk.W)
        xEntry = nb.Entry(frameTop)
        xEntry.grid(row = i + 1, column = 1, sticky=tk.W)
        yEntry = nb.Entry(frameTop)
        yEntry.grid(row = i + 1, column = 2, sticky=tk.W)
        zEntry = nb.Entry(frameTop)
        zEntry.grid(row = i + 1, column = 3, sticky=tk.W)
        this.settings.append((systemEntry, xEntry, yEntry, zEntry))

    nb.Label(frameTop).grid()	# spacer
    nb.Label(frameBottom, text="You can get coordinates from EDDB or EDSM or enter whatever you like.").grid(row = 4, column = 0, sticky=tk.W)

    return frame


def plugin_app(parent):
    """
    Return a TK Widget for the EDMC main window.
    :param parent:
    :return:
    """
    frame = tk.Frame(parent)
    frame.columnconfigure(1, weight=1)
    label = tk.Label(frame, text = "Distance Merope: ").grid(row = 0, column = 0, sticky=tk.W)
    this.ditanceLabel = tk.Label(frame, text="0 Ly").grid(row = 0, column = 1, sticky=tk.W)
    return frame

def calculateDistance(x, y, z):
    return math.sqrt((-78.59375 - x) ** 2 + (-149.625 - y) ** 2 + (-340.53125 - z) ** 2)


def journal_entry(cmdr, system, station, entry, state):
    """
    E:D client made a journal entry
    :param cmdr: The Cmdr name, or None if not yet known
    :param system: The current system, or None if not yet known
    :param station: The current station, or None if not docked or not yet known
    :param entry: The journal entry as a dictionary
    :param state: A dictionary containing info about the Cmdr, current ship and cargo
    :return:
    """
    if entry['event'] == 'FSDJump':
        # We arrived at a new system!
        if 'StarPos' in entry:
            #sys.stderr.write("Arrived at {} ({},{},{})\n".format(entry['StarSystem'], *tuple(entry['StarPos'])))
            this.ditanceLabel["text"] = "{0:.2f} Ly".format(calculateDistance(*tuple(entry['StarPos'])))
        else:
            this.ditanceLabel["text"] = "? LY"
