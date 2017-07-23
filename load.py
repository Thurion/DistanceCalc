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

from config import config
import myNotebook as nb

VERSION = "1.10 beta"

this = sys.modules[__name__]	# For holding module globals

def plugin_start():
    this.distances = json.loads(config.get("DistanceCalc") or "[]")
    return 'DistanceCalc'


def getSystemInformationFromEDSM(system):
    edsmUrl ="https://www.edsm.net/api-v1/system?systemName={SYSTEM}&showCoordinates=1".format(SYSTEM=system)
    systemInformation = None
    try:
        url = urllib2.urlopen(edsmUrl)
        response = url.read()
        edsmJson = json.loads(response)
        if "name" in edsmJson and "coords" in edsmJson:
            return (edsmJson["name"], float(edsmJson["coords"]["x"]), float(edsmJson["coords"]["y"]), float(edsmJson["coords"]["z"]))
    except:
        return None


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


def plugin_prefs(parent):
    frame = nb.Frame(parent)
    frameTop = nb.Frame(frame)
    frameTop.grid(row = 0, column = 0, sticky=tk.W)
    frameBottom = nb.Frame(frame)
    frameBottom.grid(row = 1, column = 0, sticky=tk.SW)

    nb.Label(frameTop, text="Systems").grid(row = 0, column = 0, sticky=tk.EW)
    nb.Label(frameTop, text="X").grid(row = 0, column = 1, sticky=tk.EW)
    nb.Label(frameTop, text="Y").grid(row = 0, column = 2, sticky=tk.EW)
    nb.Label(frameTop, text="Z").grid(row = 0, column = 3, sticky=tk.EW)

    this.settingUiEntries = list()
    vcmd = (frameTop.register(validate), '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')

    for i in range(3):
        systemEntry = nb.Entry(frameTop)
        systemEntry.grid(row = i + 1, column = 0, padx = 5, sticky=tk.W)
        systemEntry.config(width = 40) # set fixed width. columnconfigure doesn't work because it already fits
        xEntry = nb.Entry(frameTop, validate = 'key', validatecommand = vcmd)
        xEntry.grid(row = i + 1, column = 1, padx = 5, sticky=tk.W)
        xEntry.config(width = 10) # set fixed width. columnconfigure doesn't work because it already fits
        yEntry = nb.Entry(frameTop, validate = 'key', validatecommand = vcmd)
        yEntry.grid(row = i + 1, column = 2, padx = 5, sticky=tk.W)
        yEntry.config(width = 10) # set fixed width. columnconfigure doesn't work because it already fits
        zEntry = nb.Entry(frameTop, validate = 'key', validatecommand = vcmd)
        zEntry.grid(row = i + 1, column = 3, padx = 5, sticky=tk.W)
        zEntry.config(width = 10) # set fixed width. columnconfigure doesn't work because it already fits
        nb.Button(frameTop, text="EDSM").grid(row = i + 1, column = 4, padx = 5, sticky=tk.W)

        this.settingUiEntries.append([systemEntry, xEntry, yEntry, zEntry])

    nb.Label(frameTop).grid()	# spacer
    nb.Label(frameBottom, text="You can get coordinates from EDDB or EDSM or enter any valid coordinate.").grid(row = 0, column = 0, sticky=tk.W)
    nb.Label(frameBottom).grid()	# spacer
    nb.Label(frameBottom, text="Plugin version: {0}".format(VERSION)).grid(row = 2, column = 0, sticky=tk.W)

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
        # possible bug in tkinter: when everythng is removed from frame it isn't resized. add this instead
        this.unspecified.grid(row = row, column = 0, sticky=tk.W)
    else:
        this.unspecified.grid_remove()
    for (system, distance) in this.distanceLabels:
        if len(this.distances) >= row + 1:
            s = this.distances[row]
            system.grid(row = row, column = 0, sticky=tk.W)
            system["text"] =  "Distance {0}:".format(s["system"])
            distance.grid(row = row, column = 1, sticky=tk.W)
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


def plugin_app(parent):
    frame = tk.Frame(parent)
    frame.columnconfigure(1, weight=1)
    this.unspecified = tk.Label(frame, text="No systems specified")
    this.distanceLabels = list()
    for i in range(3):
        this.distanceLabels.append((tk.Label(frame), tk.Label(frame)))
    updateUi()
    return frame


def calculateDistance(x1, y1, z1, x2, y2, z2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)

def updateDistances(coordinates = None):
    if not coordinates:
        for (_, distance) in this.distanceLabels:
            distance["text"] = "? Ly"
    else:
        for i in range(len(this.distances)):
            system = this.distances[i]
            distance = calculateDistance(system["x"], system["y"], system["z"], *coordinates)
            this.distanceLabels[i][1]["text"] = "{0:.2f} Ly".format(distance)


def journal_entry(cmdr, system, station, entry, state):
    if entry["event"] == "FSDJump" or entry["event"] == "Location":
        # We arrived at a new system!
        if 'StarPos' in entry:
            updateDistances(tuple(entry['StarPos']))
        else:
            updateDistances()
