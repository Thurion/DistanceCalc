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
import os
import math
import json
import logging
from urllib import request, parse
from threading import Thread
from functools import partial
from typing import List, Tuple

from config import config, appname
from l10n import Locale
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb
import tkinter as tk
import tkinter.ttk as ttk

this = sys.modules[__name__]  # For holding module globals

this.VERSION = "1.3"
this.BG_UPDATE_JSON = "bg_update_json"
this.NUMBER_OF_SYSTEMS = 10
this.PADX = 5
this.WIDTH = 10

logger = logging.getLogger(f"{appname}.{os.path.basename(os.path.dirname(__file__))}")
if not logger.hasHandlers():
    level = logging.INFO  # So logger.info(...) is equivalent to print()

    logger.setLevel(logging.INFO)
    logger_channel = logging.StreamHandler()
    logger_channel.setLevel(level)
    logger_formatter = logging.Formatter(f"%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d:%(funcName)s: %(message)s")
    logger_formatter.default_time_format = "%Y-%m-%d %H:%M:%S"
    logger_formatter.default_msec_format = "%s.%03d"
    logger_channel.setFormatter(logger_formatter)
    logger.addHandler(this.logger_channel)


class SettingsUiElements(object):
    def __init__(self, systemEntry, xEntry, yEntry, zEntry, edsmButton, hasData=False, success=False, x=0, y=0, z=0, systemName="", errorText=""):
        self.systemEntry = systemEntry
        self.xEntry = xEntry
        self.yEntry = yEntry
        self.zEntry = zEntry
        self.edsmButton = edsmButton
        self.hasData = hasData
        self.success = success
        self.x = x
        self.y = y
        self.z = z
        self.systemName = systemName
        self.statusText = errorText

    def resetResponseData(self):
        self.hasData = False
        self.success = False
        self.x = 0
        self.y = 0
        self.z = 0
        self.systemName = ""
        self.statusText = ""


class DistanceCalc(object):
    EVENT_EDSM_RESPONSE = "<<DistanceCalc-EDSM-Response>>"

    def __init__(self):
        distances = json.loads(config.get_str("DistanceCalc") or "[]")
        self.distances = distances[:this.NUMBER_OF_SYSTEMS]
        self.coordinates: Tuple[float, float, float] = None
        self.distanceTotal: float = float(config.get_int("DistanceCalc_travelled") or 0) / 1000.0
        self.distanceSession: float = 0.0
        a, b, c = self.getSettingsTravelled()
        self.travelledTotalOption: tk.IntVar = tk.IntVar(value=a and 1)
        self.travelledSessionOption: tk.IntVar = tk.IntVar(value=b and 1)
        self.travelledSessionSelected: tk.IntVar = tk.IntVar(value=c and 1)
        self.errorLabel: tk.Label = None
        self.settingsUiElements = list()
        self.distanceLabels: List[Tuple[tk.Label, tk.Label]] = list()
        self.travelledLabels: List[tk.Label] = list()
        self.emptyFrame: tk.Frame = None
        self.updateNotificationLabel: HyperlinkLabel = None
        self.prefs_frame: tk.Frame = None

    # region static and helper methods
    @staticmethod
    def fillEntries(s, x, y, z, systemEntry, xEntry, yEntry, zEntry):
        systemEntry.insert(0, s)
        if type(x) == str:
            xEntry.insert(0, x)
        else:
            xEntry.insert(0, Locale.string_from_number(x, 3))
        if type(y) == str:
            yEntry.insert(0, y)
        else:
            yEntry.insert(0, Locale.string_from_number(y, 3))
        if type(z) == str:
            zEntry.insert(0, z)
        else:
            zEntry.insert(0, Locale.string_from_number(z, 3))

    @staticmethod
    def validate(action, index, value_if_allowed, prior_value, text, validation_type, trigger_type, widget_name):
        if value_if_allowed == "-" or value_if_allowed == "":
            return True
        elif text in "0123456789.," or text == value_if_allowed:
            try:
                t = type(Locale.number_from_string(value_if_allowed))
                if t is float or t is int:
                    return True
            except ValueError:
                return False
        return False

    @staticmethod
    def getSettingsTravelled():
        settings = config.get_int("DistanceCalc_options")
        settingTotal = settings & 1  # calculate total distance travelled
        settingSession = (settings >> 1) & 1  # calculate for session only
        settingSessionOption = (settings >> 2) & 1  # 1 = calculate for ED session; 0 = calculate for EDMC session
        return settingTotal, settingSession, settingSessionOption

    @staticmethod
    def calculateDistance(x1, y1, z1, x2, y2, z2):
        return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)
    # endregion

    # region interface methods
    def plugin_app(self, parent: tk.Frame):
        frame = tk.Frame(parent)
        self.emptyFrame = tk.Frame(frame)
        frame.columnconfigure(1, weight=1)
        for i in range(this.NUMBER_OF_SYSTEMS):
            self.distanceLabels.append((tk.Label(frame), tk.Label(frame)))

            self.travelledLabels = list()
        for i in range(2):  # total and session
            self.travelledLabels.append((tk.Label(frame), tk.Label(frame)))

        self.updateNotificationLabel = HyperlinkLabel(frame, text="Plugin update available", background=nb.Label().cget("background"),
                                                      url="https://github.com/Thurion/DistanceCalc/releases", underline=True)

        self.updateMainUi()
        return frame

    def open_prefs(self, parent, cmdr: str, is_beta: bool):
        row_top = 0

        def next_row_top():
            nonlocal row_top
            row_top += 1
            return row_top

        self.prefs_frame = nb.Frame(parent)
        self.prefs_frame.bind_all(DistanceCalc.EVENT_EDSM_RESPONSE, self.updatePrefsUI)
        frameTop = nb.Frame(self.prefs_frame)
        frameTop.grid(row=0, column=0, sticky=tk.W)
        frameBottom = nb.Frame(self.prefs_frame)
        frameBottom.grid(row=1, column=0, sticky=tk.SW)

        # headline
        nb.Label(frameTop, text="Systems").grid(row=row_top, column=2, sticky=tk.EW)
        nb.Label(frameTop, text="X").grid(row=row_top, column=3, sticky=tk.EW)
        nb.Label(frameTop, text="Y").grid(row=row_top, column=4, sticky=tk.EW)
        nb.Label(frameTop, text="Z").grid(row=row_top, column=5, sticky=tk.EW)

        self.errorLabel = nb.Label(frameTop, text="")

        self.settingsUiElements = list()
        vcmd = (frameTop.register(self.validate), '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')

        # create and add fields to enter systems
        for i in range(this.NUMBER_OF_SYSTEMS):
            next_row_top()

            upButton = nb.Button(frameTop, text="\u25B2", command=partial(self.rearrangeOrder, i, i - 1))
            upButton.grid(row=row_top, column=0, padx=(this.PADX * 2, 1), sticky=tk.W)
            upButton.config(width=3)
            if i == 0:
                upButton["state"] = tk.DISABLED

            downButton = nb.Button(frameTop, text="\u25BC", command=partial(self.rearrangeOrder, i, i + 1))
            downButton.grid(row=row_top, column=1, padx=(1, this.PADX), sticky=tk.W)
            downButton.config(width=3)
            if i == this.NUMBER_OF_SYSTEMS - 1:
                downButton["state"] = tk.DISABLED

            systemEntry = nb.Entry(frameTop)
            systemEntry.grid(row=row_top, column=2, padx=this.PADX, sticky=tk.W)
            systemEntry.config(width=this.WIDTH * 4)  # set fixed width. columnconfigure doesn't work because it already fits

            xEntry = nb.Entry(frameTop, validate='key', validatecommand=vcmd)
            xEntry.grid(row=row_top, column=3, padx=this.PADX, sticky=tk.W)
            xEntry.config(width=this.WIDTH)  # set fixed width. columnconfigure doesn't work because it already fits

            yEntry = nb.Entry(frameTop, validate='key', validatecommand=vcmd)
            yEntry.grid(row=row_top, column=4, padx=this.PADX, sticky=tk.W)
            yEntry.config(width=this.WIDTH)  # set fixed width. columnconfigure doesn't work because it already fits

            zEntry = nb.Entry(frameTop, validate='key', validatecommand=vcmd)
            zEntry.grid(row=row_top, column=5, padx=this.PADX, sticky=tk.W)
            zEntry.config(width=this.WIDTH)  # set fixed width. columnconfigure doesn't work because it already fits

            clearButton = nb.Button(frameTop, text="Clear", command=partial(self.clearInputFields, i))
            clearButton.grid(row=row_top, column=6, padx=this.PADX, sticky=tk.W)
            clearButton.config(width=7)

            edsmButton = nb.Button(frameTop, text="EDSM")
            edsmButton.grid(row=row_top, column=7, padx=(this.PADX, this.PADX * 2), sticky=tk.W)
            edsmButton.config(width=7, command=partial(self.fillSystemInformationFromEdsmAsync, i, systemEntry))

            self.settingsUiElements.append(SettingsUiElements(systemEntry, xEntry, yEntry, zEntry, edsmButton))

        # EDSM result label and information about what coordinates can be entered
        self.errorLabel.grid(row=next_row_top(), column=0, columnspan=6, padx=this.PADX * 2, sticky=tk.W)
        nb.Label(frameTop, text="You can get coordinates from EDDB or EDSM or enter any valid coordinate.").grid(row=next_row_top(), column=0, columnspan=6,
                                                                                                                 padx=this.PADX * 2,
                                                                                                                 sticky=tk.W)
        ttk.Separator(frameTop, orient=tk.HORIZONTAL).grid(row=next_row_top(), columnspan=6, padx=this.PADX * 2, pady=8, sticky=tk.EW)

        row_bottom = 0

        def next_row_bottom():
            nonlocal row_bottom
            row_bottom += 1
            return row_bottom

        # total travelled distance
        travelledTotal = nb.Checkbutton(frameBottom, variable=self.travelledTotalOption, text="Calculate total travelled distance")
        travelledTotal.var = self.travelledTotalOption
        travelledTotal.grid(row=row_bottom, column=0, padx=this.PADX * 2, sticky=tk.W)
        resetButton = nb.Button(frameBottom, text="Reset", command=self.resetTotalTravelledDistance)
        resetButton.grid(row=next_row_bottom(), column=0, padx=this.PADX * 4, pady=5, sticky=tk.W)

        travelledSession = nb.Checkbutton(frameBottom, variable=self.travelledSessionOption, text="Calculate travelled distance for current session")
        travelledSession.var = self.travelledSessionOption
        travelledSession.grid(row=next_row_bottom(), column=0, padx=this.PADX * 2, sticky=tk.W)

        # radio button value: 1 = calculate for ED session; 0 = calculate for EDMC session
        travelledSessionEdmc = nb.Radiobutton(frameBottom, variable=self.travelledSessionSelected, value=0, text="EDMC session")
        travelledSessionEdmc.var = self.travelledSessionSelected
        travelledSessionEdmc.grid(row=next_row_bottom(), column=0, padx=this.PADX * 4, sticky=tk.W)

        travelledSessionElite = nb.Radiobutton(frameBottom, variable=self.travelledSessionSelected, value=1, text="Elite session")
        travelledSessionElite.var = self.travelledSessionSelected
        travelledSessionElite.grid(row=next_row_bottom(), column=0, padx=this.PADX * 4, sticky=tk.W)

        self.setStateRadioButtons(travelledSessionEdmc, travelledSessionElite)
        travelledSession.config(command=partial(self.setStateRadioButtons, travelledSessionEdmc, travelledSessionElite))

        nb.Label(frameBottom).grid(row=next_row_bottom())  # spacer
        nb.Label(frameBottom).grid(row=next_row_bottom())  # spacer
        nb.Label(frameBottom, text="Plugin version: {0}".format(this.VERSION)).grid(row=next_row_bottom(), column=0, padx=this.PADX, sticky=tk.W)
        HyperlinkLabel(self.prefs_frame, text="Open the Github page for this plugin", background=nb.Label().cget("background"),
                       url="https://github.com/Thurion/DistanceCalc/", underline=True).grid(row=next_row_bottom(), column=0, padx=this.PADX, sticky=tk.W)
        HyperlinkLabel(self.prefs_frame, text="Get estimated coordinates from EDTS", background=nb.Label().cget("background"),
                       url="http://edts.thargoid.space/", underline=True).grid(row=next_row_bottom(), column=0, padx=this.PADX, sticky=tk.W)

        row = 0
        if len(self.distances) > 0:
            for var in self.distances:
                settingsUiElement = self.settingsUiElements[row]
                self.fillEntries(var["system"], var["x"], var["y"], var["z"],
                                 settingsUiElement.systemEntry,
                                 settingsUiElement.xEntry,
                                 settingsUiElement.yEntry,
                                 settingsUiElement.zEntry)
                row += 1

        return self.prefs_frame

    def prefs_changed(self, cmdr: str, is_beta: bool):
        distances = list()
        for settingsUiElement in self.settingsUiElements:
            systemText = settingsUiElement.systemEntry.get()
            xText = settingsUiElement.xEntry.get()
            yText = settingsUiElement.yEntry.get()
            zText = settingsUiElement.zEntry.get()
            if systemText and xText and yText and zText:
                try:
                    distances.append({
                        "system": systemText.strip(),
                        "x": Locale.number_from_string(xText.strip()),
                        "y": Locale.number_from_string(yText.strip()),
                        "z": Locale.number_from_string(zText.strip())
                    })

                except Exception as e:  # error while parsing the numbers
                    logger.exception(f"DistanceCalc: Error while parsing the coordinates for {systemText.strip()}")
                    continue
        self.distances = distances
        config.set("DistanceCalc", json.dumps(self.distances))

        settings = self.travelledTotalOption.get() | (self.travelledSessionOption.get() << 1) | (self.travelledSessionSelected.get() << 2)
        config.set("DistanceCalc_options", settings)

        self.updateMainUi()
        self.updateDistances()
        self.prefs_frame = None

    def journal_entry(self, cmdr, is_beta, system, station, entry, state):
        if entry["event"] in ["FSDJump", "Location", "CarrierJump", "StartUp"]:
            # We arrived at a new system!
            if "StarPos" in entry:
                self.coordinates = tuple(entry["StarPos"])
            if "JumpDist" in entry:
                distance = entry["JumpDist"]
                if self.travelledTotalOption.get():
                    self.distanceTotal += distance
                    config.set("DistanceCalc_travelled", int(self.distanceTotal * 1000))
                if self.travelledSessionOption.get():
                    self.distanceSession += distance
            self.updateDistances()
        if entry["event"] == "LoadGame" and self.travelledSessionOption.get() and self.travelledSessionSelected.get():
            self.distanceSession = 0.0
            self.updateDistances()
    # endregion

    # region user interface
    def clearInputFields(self, index):
        settingsUiElements = self.settingsUiElements[index]  # type SettingsUiElements
        settingsUiElements.systemEntry.delete(0, tk.END)
        settingsUiElements.xEntry.delete(0, tk.END)
        settingsUiElements.yEntry.delete(0, tk.END)
        settingsUiElements.zEntry.delete(0, tk.END)

    def rearrangeOrder(self, oldIndex, newIndex):
        if oldIndex < 0 or oldIndex >= len(self.settingsUiElements) or newIndex < 0 or newIndex >= len(self.settingsUiElements):
            logger.error(f"DistanceCalc: Can't rearrange system from index {oldIndex} to {newIndex}")
            return  # something went wrong with the indexes

        old_systemText = self.settingsUiElements[oldIndex].systemEntry.get()
        old_xText = self.settingsUiElements[oldIndex].xEntry.get()
        old_yText = self.settingsUiElements[oldIndex].yEntry.get()
        old_zText = self.settingsUiElements[oldIndex].zEntry.get()

        new_systemText = self.settingsUiElements[newIndex].systemEntry.get()
        new_xText = self.settingsUiElements[newIndex].xEntry.get()
        new_yText = self.settingsUiElements[newIndex].yEntry.get()
        new_zText = self.settingsUiElements[newIndex].zEntry.get()

        self.clearInputFields(oldIndex)
        self.clearInputFields(newIndex)
        uiElements = self.settingsUiElements[oldIndex]  # type: SettingsUiElements
        self.fillEntries(new_systemText, new_xText, new_yText, new_zText, uiElements.systemEntry, uiElements.xEntry, uiElements.yEntry, uiElements.zEntry)
        uiElements = self.settingsUiElements[newIndex]  # type: SettingsUiElements
        self.fillEntries(old_systemText, old_xText, old_yText, old_zText, uiElements.systemEntry, uiElements.xEntry, uiElements.yEntry, uiElements.zEntry)

    def updateMainUi(self):
        # labels for distances to systems
        row = 0
        for (system, distance) in self.distanceLabels:
            if len(self.distances) >= row + 1:
                s = self.distances[row]
                system.grid(row=row, column=0, sticky=tk.W)
                system["text"] = "Distance {0}:".format(s["system"])
                distance.grid(row=row, column=1, sticky=tk.W)
                distance["text"] = "? Ly"
                row += 1
            else:
                system.grid_remove()
                distance.grid_remove()

        # labels for total travelled distance
        settingTotal, settingSession, settingSessionOption = self.getSettingsTravelled()

        for i in range(len(self.travelledLabels)):
            description, distance = self.travelledLabels[i]
            if (i == 0 and settingTotal) or (i == 1 and settingSession):
                description.grid(row=row, column=0, sticky=tk.W)
                description["text"] = "Travelled ({0}):".format("total" if i == 0 else "session")
                distance.grid(row=row, column=1, sticky=tk.W)
                distance["text"] = "{0} Ly".format(Locale.string_from_number(self.distanceTotal, 2) if i == 0 else Locale.string_from_number(self.distanceSession, 2))
                row += 1
            else:
                description.grid_remove()
                distance.grid_remove()

        if row == 0:
            self.emptyFrame.grid(row=0)
        else:
            self.emptyFrame.grid_remove()

    def updatePrefsUI(self, event=None):
        for i, settingsUiElement in enumerate(self.settingsUiElements):
            if settingsUiElement.hasData:
                if settingsUiElement.success:
                    self.clearInputFields(i)
                    settingsUiElement.systemEntry.insert(0, settingsUiElement.systemName)
                    settingsUiElement.xEntry.insert(0, Locale.string_from_number(settingsUiElement.x))
                    settingsUiElement.yEntry.insert(0, Locale.string_from_number(settingsUiElement.y))
                    settingsUiElement.zEntry.insert(0, Locale.string_from_number(settingsUiElement.z))
                    self.errorLabel["text"] = settingsUiElement.statusText
                    self.errorLabel.config(foreground="dark green")
                else:
                    self.errorLabel["text"] = settingsUiElement.statusText
                    self.errorLabel.config(foreground="red")

                settingsUiElement.edsmButton["state"] = tk.NORMAL
                settingsUiElement.resetResponseData()

    def setStateRadioButtons(self, travelledSessionEdmc, travelledSessionElite):
        if self.travelledSessionOption.get() == 1:
            travelledSessionEdmc["state"] = "normal"
            travelledSessionElite["state"] = "normal"
        else:
            travelledSessionEdmc["state"] = "disabled"
            travelledSessionElite["state"] = "disabled"

    def updateDistances(self):
        if not self.coordinates:
            for (_, distance) in self.distanceLabels:
                distance["text"] = "? Ly"
        else:
            for i in range(len(self.distances)):
                system = self.distances[i]
                distance = self.calculateDistance(system["x"], system["y"], system["z"], *self.coordinates)
                self.distanceLabels[i][1]["text"] = "{0} Ly".format(Locale.string_from_number(distance, 2))

        _, distance = self.travelledLabels[0]
        distance["text"] = "{0} Ly".format(Locale.string_from_number(self.distanceTotal, 2))
        _, distance = self.travelledLabels[1]
        distance["text"] = "{0} Ly".format(Locale.string_from_number(self.distanceSession, 2))
    # endregion

    # region EDSM
    def getSystemInformationFromEDSM(self, buttonNumber, systemName):
        # Don't access UI elements from here because of thread safety. Use the regular (int, str, bool) variables and fire an event
        settingsUiElements = self.settingsUiElements[buttonNumber]
        settingsUiElements.resetResponseData()

        edsmUrl = "https://www.edsm.net/api-v1/system?systemName={SYSTEM}&showCoordinates=1".format(SYSTEM=parse.quote(systemName))
        try:
            url = request.urlopen(edsmUrl, timeout=15)
            response = url.read()
            edsmJson = json.loads(response)
            if "name" in edsmJson and "coords" in edsmJson:
                settingsUiElements.success = True
                settingsUiElements.systemName = edsmJson["name"]
                settingsUiElements.x = edsmJson["coords"]["x"]
                settingsUiElements.y = edsmJson["coords"]["y"]
                settingsUiElements.z = edsmJson["coords"]["z"]
                settingsUiElements.statusText = f"Coordinates filled in for system {edsmJson['name']}"
            else:
                settingsUiElements.statusText = f"Could not get system information for {systemName} from EDSM"
        except:
            settingsUiElements.statusText = f"Could not get system information for {systemName} from EDSM"
            logger.error(f"Could not get system information for {systemName} from EDSM")
        finally:
            settingsUiElements.hasData = True
            if self.prefs_frame:
                self.prefs_frame.event_generate(DistanceCalc.EVENT_EDSM_RESPONSE, when="tail")

    def fillSystemInformationFromEdsmAsync(self, buttonNumber, systemEntry):
        if systemEntry.get() == "":
            self.errorLabel["text"] = "No system name provided."
            self.errorLabel.config(foreground="red")
        else:
            self.settingsUiElements[buttonNumber].edsmButton["state"] = tk.DISABLED
            t = Thread(name="EDSM_caller_{0}".format(buttonNumber), target=self.getSystemInformationFromEDSM, args=(buttonNumber, systemEntry.get()))
            t.start()
    # endregion

    def resetTotalTravelledDistance(self):
        config.set("DistanceCalc_travelled", 0)
        self.distanceTotal = 0.0


"""
    def showUpdateNotification(self, event=None):
        updateVersionInfo = this.rseData.lastEventInfo.get(this.BG_UPDATE_JSON, None)
        if updateVersionInfo:
            url = updateVersionInfo["url"]
            text = "Plugin update to {version} available".format(version=updateVersionInfo["version"])
        else:
            url = "https://github.com/Thurion/DistanceCalc/releases"
            text = "Plugin update available"
        this.updateNotificationLabel["url"] = url
        this.updateNotificationLabel["text"] = text
        this.updateNotificationLabel.grid(row=99, column=0, columnspan=2, sticky=tk.W)  # always put in last row
    
    def checkVersion(self):
        try:
            response = urllib.request.urlopen("https://api.github.com/repos/Thurion/DistanceCalc/releases", timeout=10)
            releasesInfo = json.loads(response.read())
            runningVersion = tuple(this.VERSION.split("."))
            for releaseInfo in releasesInfo:
                if not releaseInfo["draft"] and not releaseInfo["prerelease"]:
                    newVersionText = releaseInfo["tag_name"].split("_")[1]
                    newVersionInfo = tuple(newVersionText.split("."))
                    if runningVersion < newVersionInfo:
                        self.rseData.lastEventInfo[RseData.BG_UPDATE_JSON] = {"version": newVersionText, "url": releaseInfo["html_url"]}
                        self.rseData.frame.event_generate(RseData.EVENT_RSE_UPDATE_AVAILABLE, when="tail")
                        break
    
        except Exception as e:
            logger.exception("Failed to retrieve information about available updates.")
"""


def plugin_start3(plugin_dir):
    this.distanceCalc = DistanceCalc()
    return "DistanceCalc"


def plugin_prefs(parent, cmdr, is_beta):
    return this.distanceCalc.open_prefs(parent, cmdr, is_beta)


def prefs_changed(cmdr, is_beta):
    this.distanceCalc.prefs_changed(cmdr, is_beta)


def plugin_app(parent):
    return this.distanceCalc.plugin_app(parent)


def journal_entry(cmdr, is_beta, system, station, entry, state):
    this.distanceCalc.journal_entry(cmdr, is_beta, system, station, entry, state)
