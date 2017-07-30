"""
DistanceCalc a plugin for EDMC
Copyright (C) 2017 Sebastian Bauer

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import sys
import ttk
import math
import json
import Tkinter as tk
import urllib2
import webbrowser
from threading import Thread
from functools import partial
from config import config
import myNotebook as nb

VERSION = "1.20 Beta"
PADX = 5
WIDTH = 10

this = sys.modules[__name__]	# For holding module globals

def plugin_start():
    this.distances = json.loads(config.get("DistanceCalc") or "[]")
    this.coordinates = None
    return 'DistanceCalc'


def clearInputFields(system, x, y, z):
    system.delete(0, tk.END)
    x.delete(0, tk.END)
    y.delete(0, tk.END)
    z.delete(0, tk.END)


def fillSystemInformationFromEDSM(label, systemEntry, xEntry, yEntry, zEntry):
    if systemEntry.get() == "":
        label["text"] = "No system name provided."
        label.config(foreground="red")
        return # nothing to do here

    edsmUrl = "https://www.edsm.net/api-v1/system?systemName={SYSTEM}&showCoordinates=1".format(SYSTEM=urllib2.quote(systemEntry.get()))
    systemInformation = None
    try:
        url = urllib2.urlopen(edsmUrl, timeout=5)
        response = url.read()
        edsmJson = json.loads(response)
        if "name" in edsmJson and "coords" in edsmJson:
            clearInputFields(systemEntry, xEntry, yEntry, zEntry)
            systemEntry.insert(0, edsmJson["name"])
            xEntry.insert(0, edsmJson["coords"]["x"])
            yEntry.insert(0, edsmJson["coords"]["y"])
            zEntry.insert(0, edsmJson["coords"]["z"])
            label["text"] = "Coordinates filled in for system {0}".format(edsmJson["name"])
            label.config(foreground="dark green")
        else:
            label["text"] = "Could not get system information for {0} from EDSM".format(systemEntry.get())
            label.config(foreground="red")
    except:
        label["text"] = "Could not get system information for {0} from EDSM".format(systemEntry.get())
        label.config(foreground="red")
        sys.stderr.write("DistanceCalc: Could not get system information for {0} from EDSM".format(systemEntry.get()))


def fillSystemInformationFromEdmsAsync(label, systemEntry, xEntry, yEntry, zEntry):
    t = Thread(name="EDSM_caller_{0}".format(label), target=fillSystemInformationFromEDSM, args=(label, systemEntry, xEntry, yEntry, zEntry))
    t.start()


def validate(action, index, value_if_allowed,  prior_value, text, validation_type, trigger_type, widget_name):
    if value_if_allowed == "-" or value_if_allowed == "":
        return True
    elif text in "0123456789.," or text == value_if_allowed:
        try:
            float(value_if_allowed.replace(",", "."))
            return True
        except ValueError:
            return False
    return False


def openGithub(event):
    webbrowser.open_new(r"https://github.com/Thurion/DistanceCalc")


def plugin_prefs(parent):
    frame = nb.Frame(parent)
    frameTop = nb.Frame(frame)
    frameTop.grid(row=0, column=0, sticky=tk.W)
    frameBottom = nb.Frame(frame)
    frameBottom.grid(row=1, column=0, sticky=tk.SW)

    nb.Label(frameTop, text="Systems").grid(row=0, column=0, sticky=tk.EW)
    nb.Label(frameTop, text="X").grid(row=0, column=1, sticky=tk.EW)
    nb.Label(frameTop, text="Y").grid(row=0, column=2, sticky=tk.EW)
    nb.Label(frameTop, text="Z").grid(row=0, column=3, sticky=tk.EW)

    errorLabel = nb.Label(frameTop, text = "")

    this.settingUiEntries = list()
    vcmd = (frameTop.register(validate), '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')

    for i in range(3):
        systemEntry = nb.Entry(frameTop)
        systemEntry.grid(row=i+1, column=0, padx=(PADX*2, PADX), sticky=tk.W)
        systemEntry.config(width=WIDTH*4) # set fixed width. columnconfigure doesn't work because it already fits

        xEntry = nb.Entry(frameTop, validate='key', validatecommand = vcmd)
        xEntry.grid(row=i+1, column=1, padx=PADX, sticky=tk.W)
        xEntry.config(width=WIDTH) # set fixed width. columnconfigure doesn't work because it already fits

        yEntry = nb.Entry(frameTop, validate='key', validatecommand = vcmd)
        yEntry.grid(row=i+1, column=2, padx=PADX, sticky=tk.W)
        yEntry.config(width=WIDTH) # set fixed width. columnconfigure doesn't work because it already fits

        zEntry = nb.Entry(frameTop, validate='key', validatecommand = vcmd)
        zEntry.grid(row=i+1, column=3, padx=PADX, sticky=tk.W)
        zEntry.config(width=WIDTH) # set fixed width. columnconfigure doesn't work because it already fits

        clearButton = nb.Button(frameTop, text="Clear", command=partial(clearInputFields, systemEntry, xEntry, yEntry, zEntry))
        clearButton.grid(row=i+1, column=4, padx=PADX, sticky=tk.W)
        clearButton.config(width=7)

        edsmButton = nb.Button(frameTop, text="EDSM")
        edsmButton.grid(row=i+1, column=5, padx=(PADX, PADX*2), sticky=tk.W)
        edsmButton.config(width=7, command=partial(fillSystemInformationFromEdmsAsync, errorLabel, systemEntry, xEntry, yEntry, zEntry))

        this.settingUiEntries.append([systemEntry, xEntry, yEntry, zEntry])

    errorLabel.grid(row=4, column=0, columnspan=6, padx=PADX*2, sticky=tk.W)
    nb.Label(frameTop, text="You can get coordinates from EDDB or EDSM or enter any valid coordinate.").grid(row=5, column=0, columnspan=6, padx=PADX*2, sticky=tk.W)
    ttk.Separator(frameTop, orient=tk.HORIZONTAL).grid(row=6, columnspan=6, padx=PADX*2, pady=8, sticky=tk.EW)

    nb.Label(frameBottom, text="Plugin version: {0}".format(VERSION)).grid(row=5, column=0, padx=PADX, sticky=tk.W)
    link = nb.Label(frameBottom, text="Open the Github page for this plugin", fg="blue", cursor="hand2")
    link.grid(row=6, column=0, padx=PADX, sticky=tk.W)
    link.bind("<Button-1>", openGithub)


    def fillEntries(s, x, y, z, systemEntry, xEntry, yEntry, zEntry):
        systemEntry.insert(0, s)
        xEntry.insert(0, x)
        yEntry.insert(0, y)
        zEntry.insert(0, z)

    row = 0
    if len(this.distances) > 0:
        for var in this.distances:
            systemEntry, xEntry, yEntry, zEntry = this.settingUiEntries[row]
            fillEntries(var["system"], var["x"], var["y"], var["z"], systemEntry, xEntry, yEntry, zEntry)
            row += 1

    return frame


def updateUi():
    row = 0
    if len(this.distances) == 0:
        # possible bug in tkinter: when everythng is removed from frame it isn't resized. set height to 1 pixel
        system, _ = this.distanceLabels[0]
        system.master.config(height = 1)
    else:
        # set height back to default
        system, _ = this.distanceLabels[0]
        system.master.config(height = 0)
    for (system, distance) in this.distanceLabels:
        if len(this.distances) >= row + 1:
            s = this.distances[row]
            system.grid(row=row, column=0, sticky=tk.W)
            system["text"] =  "Distance {0}:".format(s["system"])
            distance.grid(row=row, column=1, sticky=tk.W)
            distance["text"] = "? Ly"
        else:
            system.grid_remove()
            distance.grid_remove()
        row += 1


def prefs_changed():
    this.distances = list()
    for (system, x, y, z) in this.settingUiEntries:
        systemText = system.get()
        xText = x.get()
        yText = y.get()
        zText = z.get()
        if systemText and xText and yText and zText:
            try:
                d = dict()
                d["system"] = systemText.strip()
                d["x"] = float(xText.strip().replace(",", "."))
                d["y"] = float(yText.strip().replace(",", "."))
                d["z"] = float(zText.strip().replace(",", "."))
                this.distances.append(d)
            except: # error while parsing the numbers
                sys.stderr.write("DistanceCalc: Error while parsing the coordinates for {0}".format(systemText.strip()))
                continue
    config.set("DistanceCalc", json.dumps(this.distances))
    updateUi()
    updateDistances()


def plugin_app(parent):
    frame = tk.Frame(parent)
    frame.columnconfigure(1, weight=1)
    this.distanceLabels = list()
    for i in range(3):
        this.distanceLabels.append((tk.Label(frame), tk.Label(frame)))
    updateUi()
    return frame


def calculateDistance(x1, y1, z1, x2, y2, z2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)


def updateDistances():
    if not this.coordinates:
        for (_, distance) in this.distanceLabels:
            distance["text"] = "? Ly"
    else:
        for i in range(len(this.distances)):
            system = this.distances[i]
            distance = calculateDistance(system["x"], system["y"], system["z"], *this.coordinates)
            this.distanceLabels[i][1]["text"] = "{0:.2f} Ly".format(distance)


def journal_entry(cmdr, system, station, entry, state):
    if entry["event"] == "FSDJump" or entry["event"] == "Location":
        # We arrived at a new system!
        if 'StarPos' in entry:
            this.coordinates = tuple(entry['StarPos'])
        updateDistances()
