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
from typing import List, Tuple, Union

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
this.distanceCalc = None  # type DistanceCalc

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
    #logger.addHandler(this.logger_channel)


class SettingsUiElements(object):
    def __init__(self, system_entry: nb.Entry, x_entry: nb.Entry, y_entry: nb.Entry, z_entry: nb.Entry,
                 edsm_button: nb.Button, has_data: bool = False, success: bool = False,
                 x: Union[float, int] = 0, y: Union[float, int] = 0, z: Union[float, int] = 0,
                 system_name: str = "", error_text: str = ""):
        self.system_entry = system_entry
        self.x_entry = x_entry
        self.y_entry = y_entry
        self.z_entry = z_entry
        self.edsm_button = edsm_button
        self.has_data = has_data
        self.success = success
        self.x = x
        self.y = y
        self.z = z
        self.system_name = system_name
        self.status_text = error_text

    def reset_response_data(self):
        self.has_data = False
        self.success = False
        self.x = 0
        self.y = 0
        self.z = 0
        self.system_name = ""
        self.status_text = ""


class DistanceCalc(object):
    EVENT_EDSM_RESPONSE = "<<DistanceCalc-EDSM-Response>>"

    def __init__(self):
        distances = json.loads(config.get_str("DistanceCalc") or "[]")
        self.distances = distances[:this.NUMBER_OF_SYSTEMS]
        self.coordinates: Union[Tuple[float, float, float], None] = None
        self.distance_total: float = float(config.get_int("DistanceCalc_travelled") or 0) / 1000.0
        self.distance_session: float = 0.0
        a, b, c = self.get_settings_travelled()
        self.travelled_total_option: tk.IntVar = tk.IntVar(value=a and 1)
        self.travelled_session_option: tk.IntVar = tk.IntVar(value=b and 1)
        self.travelled_session_selected: tk.IntVar = tk.IntVar(value=c and 1)
        self.error_label: Union[tk.Label, None] = None
        self.settings_ui_elements: List[SettingsUiElements] = list()
        self.distance_labels: List[Tuple[tk.Label, tk.Label]] = list()
        self.travelled_labels: List[tk.Label] = list()
        self.empty_frame: Union[tk.Frame, None] = None
        self.update_notification_label: Union[HyperlinkLabel, None] = None
        self.prefs_frame: Union[tk.Frame, None] = None

    # region static and helper methods
    @staticmethod
    def fill_entries(system_name: str, x: Union[str, int, float], y: Union[str, int, float], z: Union[str, int, float],
                     system_entry: nb.Entry, x_entry: nb.Entry, y_entry: nb.Entry, z_entry: nb.Entry):
        system_entry.insert(0, system_name)
        if type(x) == str:
            x_entry.insert(0, x)
        else:
            x_entry.insert(0, Locale.string_from_number(x, 3))
        if type(y) == str:
            y_entry.insert(0, y)
        else:
            y_entry.insert(0, Locale.string_from_number(y, 3))
        if type(z) == str:
            z_entry.insert(0, z)
        else:
            z_entry.insert(0, Locale.string_from_number(z, 3))

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
    def get_settings_travelled():
        settings = config.get_int("DistanceCalc_options")
        setting_total = settings & 1  # calculate total distance travelled
        setting_session = (settings >> 1) & 1  # calculate for session only
        setting_session_option = (settings >> 2) & 1  # 1 = calculate for ED session; 0 = calculate for EDMC session
        return setting_total, setting_session, setting_session_option

    @staticmethod
    def calculate_distance(x1: Union[int, float], y1: Union[int, float], z1: Union[int, float], x2: Union[int, float], y2: Union[int, float], z2: Union[int, float]):
        return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)
    # endregion

    # region interface methods
    def plugin_app(self, parent: tk.Frame):
        frame = tk.Frame(parent)
        self.empty_frame = tk.Frame(frame)
        frame.columnconfigure(1, weight=1)
        for i in range(this.NUMBER_OF_SYSTEMS):
            self.distance_labels.append((tk.Label(frame), tk.Label(frame)))

            self.travelled_labels = list()
        for i in range(2):  # total and session
            self.travelled_labels.append((tk.Label(frame), tk.Label(frame)))

        self.update_notification_label = HyperlinkLabel(frame, text="Plugin update available", background=nb.Label().cget("background"),
                                                        url="https://github.com/Thurion/DistanceCalc/releases", underline=True)

        self.update_main_ui()
        return frame

    def open_prefs(self, parent, cmdr: str, is_beta: bool):
        row_top = 0

        def next_row_top():
            nonlocal row_top
            row_top += 1
            return row_top

        self.prefs_frame = nb.Frame(parent)
        self.prefs_frame.bind_all(DistanceCalc.EVENT_EDSM_RESPONSE, self.update_prefs_ui)
        frame_top = nb.Frame(self.prefs_frame)
        frame_top.grid(row=0, column=0, sticky=tk.W)
        frame_bottom = nb.Frame(self.prefs_frame)
        frame_bottom.grid(row=1, column=0, sticky=tk.SW)

        # headline
        nb.Label(frame_top, text="Systems").grid(row=row_top, column=2, sticky=tk.EW)
        nb.Label(frame_top, text="X").grid(row=row_top, column=3, sticky=tk.EW)
        nb.Label(frame_top, text="Y").grid(row=row_top, column=4, sticky=tk.EW)
        nb.Label(frame_top, text="Z").grid(row=row_top, column=5, sticky=tk.EW)

        self.error_label = nb.Label(frame_top, text="")

        self.settings_ui_elements = list()
        vcmd = (frame_top.register(self.validate), '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')

        # create and add fields to enter systems
        for i in range(this.NUMBER_OF_SYSTEMS):
            next_row_top()

            up_button = nb.Button(frame_top, text="\u25B2", command=partial(self.rearrange_order, i, i - 1))
            up_button.grid(row=row_top, column=0, padx=(this.PADX * 2, 1), sticky=tk.W)
            up_button.config(width=3)
            if i == 0:
                up_button["state"] = tk.DISABLED

            down_button = nb.Button(frame_top, text="\u25BC", command=partial(self.rearrange_order, i, i + 1))
            down_button.grid(row=row_top, column=1, padx=(1, this.PADX), sticky=tk.W)
            down_button.config(width=3)
            if i == this.NUMBER_OF_SYSTEMS - 1:
                down_button["state"] = tk.DISABLED

            system_entry = nb.Entry(frame_top)
            system_entry.grid(row=row_top, column=2, padx=this.PADX, sticky=tk.W)
            system_entry.config(width=this.WIDTH * 4)  # set fixed width. columnconfigure doesn't work because it already fits

            x_entry = nb.Entry(frame_top, validate='key', validatecommand=vcmd)
            x_entry.grid(row=row_top, column=3, padx=this.PADX, sticky=tk.W)
            x_entry.config(width=this.WIDTH)  # set fixed width. columnconfigure doesn't work because it already fits

            y_entry = nb.Entry(frame_top, validate='key', validatecommand=vcmd)
            y_entry.grid(row=row_top, column=4, padx=this.PADX, sticky=tk.W)
            y_entry.config(width=this.WIDTH)  # set fixed width. columnconfigure doesn't work because it already fits

            z_entry = nb.Entry(frame_top, validate='key', validatecommand=vcmd)
            z_entry.grid(row=row_top, column=5, padx=this.PADX, sticky=tk.W)
            z_entry.config(width=this.WIDTH)  # set fixed width. columnconfigure doesn't work because it already fits

            clear_button = nb.Button(frame_top, text="Clear", command=partial(self.clear_input_fields, i))
            clear_button.grid(row=row_top, column=6, padx=this.PADX, sticky=tk.W)
            clear_button.config(width=7)

            edsm_button = nb.Button(frame_top, text="EDSM")
            edsm_button.grid(row=row_top, column=7, padx=(this.PADX, this.PADX * 2), sticky=tk.W)
            edsm_button.config(width=7, command=partial(self.fill_system_information_from_edsm_async, i, system_entry))

            self.settings_ui_elements.append(SettingsUiElements(system_entry, x_entry, y_entry, z_entry, edsm_button))

        # EDSM result label and information about what coordinates can be entered
        self.error_label.grid(row=next_row_top(), column=0, columnspan=6, padx=this.PADX * 2, sticky=tk.W)
        nb.Label(frame_top, text="You can get coordinates from EDDB or EDSM or enter any valid coordinate.").grid(row=next_row_top(), column=0, columnspan=6,
                                                                                                                 padx=this.PADX * 2,
                                                                                                                 sticky=tk.W)
        ttk.Separator(frame_top, orient=tk.HORIZONTAL).grid(row=next_row_top(), columnspan=6, padx=this.PADX * 2, pady=8, sticky=tk.EW)

        row_bottom = 0

        def next_row_bottom():
            nonlocal row_bottom
            row_bottom += 1
            return row_bottom

        # total travelled distance
        travelled_total = nb.Checkbutton(frame_bottom, variable=self.travelled_total_option, text="Calculate total travelled distance")
        travelled_total.var = self.travelled_total_option
        travelled_total.grid(row=row_bottom, column=0, padx=this.PADX * 2, sticky=tk.W)
        reset_button = nb.Button(frame_bottom, text="Reset", command=self.reset_total_travelled_distance)
        reset_button.grid(row=next_row_bottom(), column=0, padx=this.PADX * 4, pady=5, sticky=tk.W)

        travelled_session = nb.Checkbutton(frame_bottom, variable=self.travelled_session_option, text="Calculate travelled distance for current session")
        travelled_session.var = self.travelled_session_option
        travelled_session.grid(row=next_row_bottom(), column=0, padx=this.PADX * 2, sticky=tk.W)

        # radio button value: 1 = calculate for ED session; 0 = calculate for EDMC session
        travelled_session_edmc = nb.Radiobutton(frame_bottom, variable=self.travelled_session_selected, value=0, text="EDMC session")
        travelled_session_edmc.var = self.travelled_session_selected
        travelled_session_edmc.grid(row=next_row_bottom(), column=0, padx=this.PADX * 4, sticky=tk.W)

        travelled_session_elite = nb.Radiobutton(frame_bottom, variable=self.travelled_session_selected, value=1, text="Elite session")
        travelled_session_elite.var = self.travelled_session_selected
        travelled_session_elite.grid(row=next_row_bottom(), column=0, padx=this.PADX * 4, sticky=tk.W)

        self.set_state_radio_buttons(travelled_session_edmc, travelled_session_elite)
        travelled_session.config(command=partial(self.set_state_radio_buttons, travelled_session_edmc, travelled_session_elite))

        nb.Label(frame_bottom).grid(row=next_row_bottom())  # spacer
        nb.Label(frame_bottom).grid(row=next_row_bottom())  # spacer
        nb.Label(frame_bottom, text="Plugin version: {0}".format(this.VERSION)).grid(row=next_row_bottom(), column=0, padx=this.PADX, sticky=tk.W)
        HyperlinkLabel(self.prefs_frame, text="Open the Github page for this plugin", background=nb.Label().cget("background"),
                       url="https://github.com/Thurion/DistanceCalc/", underline=True).grid(row=next_row_bottom(), column=0, padx=this.PADX, sticky=tk.W)
        HyperlinkLabel(self.prefs_frame, text="Get estimated coordinates from EDTS", background=nb.Label().cget("background"),
                       url="http://edts.thargoid.space/", underline=True).grid(row=next_row_bottom(), column=0, padx=this.PADX, sticky=tk.W)

        row = 0
        if len(self.distances) > 0:
            for var in self.distances:
                settings_ui_element = self.settings_ui_elements[row]
                self.fill_entries(var["system"], var["x"], var["y"], var["z"],
                                  settings_ui_element.system_entry,
                                  settings_ui_element.x_entry,
                                  settings_ui_element.y_entry,
                                  settings_ui_element.z_entry)
                row += 1

        return self.prefs_frame

    def prefs_changed(self, cmdr: str, is_beta: bool):
        distances = list()
        for settings_ui_element in self.settings_ui_elements:
            system_text = settings_ui_element.system_entry.get()
            x_text = settings_ui_element.x_entry.get()
            y_text = settings_ui_element.y_entry.get()
            z_text = settings_ui_element.z_entry.get()
            if system_text and x_text and y_text and z_text:
                try:
                    distances.append({
                        "system": system_text.strip(),
                        "x": Locale.number_from_string(x_text.strip()),
                        "y": Locale.number_from_string(y_text.strip()),
                        "z": Locale.number_from_string(z_text.strip())
                    })

                except Exception as e:  # error while parsing the numbers
                    logger.exception(f"DistanceCalc: Error while parsing the coordinates for {system_text.strip()}")
                    continue
        self.distances = distances
        config.set("DistanceCalc", json.dumps(self.distances))

        settings = self.travelled_total_option.get() | (self.travelled_session_option.get() << 1) | (self.travelled_session_selected.get() << 2)
        config.set("DistanceCalc_options", settings)

        self.update_main_ui()
        self.update_distances()
        self.prefs_frame = None

    def journal_entry(self, cmdr, is_beta, system, station, entry, state):
        if entry["event"] in ["FSDJump", "Location", "CarrierJump", "StartUp"]:
            # We arrived at a new system!
            if "StarPos" in entry:
                self.coordinates = tuple(entry["StarPos"])
            if "JumpDist" in entry:
                distance = entry["JumpDist"]
                if self.travelled_total_option.get():
                    self.distance_total += distance
                    config.set("DistanceCalc_travelled", int(self.distance_total * 1000))
                if self.travelled_session_option.get():
                    self.distance_session += distance
            self.update_distances()
        if entry["event"] == "LoadGame" and self.travelled_session_option.get() and self.travelled_session_selected.get():
            self.distance_session = 0.0
            self.update_distances()
    # endregion

    # region user interface
    def clear_input_fields(self, index):
        settings_ui_elements = self.settings_ui_elements[index]  # type SettingsUiElements
        settings_ui_elements.system_entry.delete(0, tk.END)
        settings_ui_elements.x_entry.delete(0, tk.END)
        settings_ui_elements.y_entry.delete(0, tk.END)
        settings_ui_elements.z_entry.delete(0, tk.END)

    def rearrange_order(self, old_index: int, new_index: int):
        if old_index < 0 or old_index >= len(self.settings_ui_elements) or new_index < 0 or new_index >= len(self.settings_ui_elements):
            logger.error(f"DistanceCalc: Can't rearrange system from index {old_index} to {new_index}")
            return  # something went wrong with the indexes

        old_system_text = self.settings_ui_elements[old_index].system_entry.get()
        old_x_text = self.settings_ui_elements[old_index].x_entry.get()
        old_y_text = self.settings_ui_elements[old_index].y_entry.get()
        old_z_text = self.settings_ui_elements[old_index].z_entry.get()

        new_system_text = self.settings_ui_elements[new_index].system_entry.get()
        new_x_text = self.settings_ui_elements[new_index].x_entry.get()
        new_y_text = self.settings_ui_elements[new_index].y_entry.get()
        new_z_text = self.settings_ui_elements[new_index].z_entry.get()

        self.clear_input_fields(old_index)
        self.clear_input_fields(new_index)
        uiElements = self.settings_ui_elements[old_index]  # type: SettingsUiElements
        self.fill_entries(new_system_text, new_x_text, new_y_text, new_z_text, uiElements.system_entry, uiElements.x_entry, uiElements.y_entry, uiElements.z_entry)
        uiElements = self.settings_ui_elements[new_index]  # type: SettingsUiElements
        self.fill_entries(old_system_text, old_x_text, old_y_text, old_z_text, uiElements.system_entry, uiElements.x_entry, uiElements.y_entry, uiElements.z_entry)

    def update_main_ui(self):
        # labels for distances to systems
        row = 0
        for (system, distance) in self.distance_labels:
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
        setting_total, setting_session, setting_session_option = self.get_settings_travelled()

        for i in range(len(self.travelled_labels)):
            description, distance = self.travelled_labels[i]
            if (i == 0 and setting_total) or (i == 1 and setting_session):
                description.grid(row=row, column=0, sticky=tk.W)
                description["text"] = "Travelled ({0}):".format("total" if i == 0 else "session")
                distance.grid(row=row, column=1, sticky=tk.W)
                distance["text"] = "{0} Ly".format(Locale.string_from_number(self.distance_total, 2) if i == 0 else Locale.string_from_number(self.distance_session, 2))
                row += 1
            else:
                description.grid_remove()
                distance.grid_remove()

        if row == 0:
            self.empty_frame.grid(row=0)
        else:
            self.empty_frame.grid_remove()

    def update_prefs_ui(self, event=None):
        for i, settings_ui_element in enumerate(self.settings_ui_elements):
            if settings_ui_element.has_data:
                if settings_ui_element.success:
                    self.clear_input_fields(i)
                    settings_ui_element.system_entry.insert(0, settings_ui_element.system_name)
                    settings_ui_element.x_entry.insert(0, Locale.string_from_number(settings_ui_element.x))
                    settings_ui_element.y_entry.insert(0, Locale.string_from_number(settings_ui_element.y))
                    settings_ui_element.z_entry.insert(0, Locale.string_from_number(settings_ui_element.z))
                    self.error_label["text"] = settings_ui_element.status_text
                    self.error_label.config(foreground="dark green")
                else:
                    self.error_label["text"] = settings_ui_element.status_text
                    self.error_label.config(foreground="red")

                settings_ui_element.edsm_button["state"] = tk.NORMAL
                settings_ui_element.reset_response_data()

    def set_state_radio_buttons(self, travelled_session_edmc, travelled_session_elite):
        if self.travelled_session_option.get() == 1:
            travelled_session_edmc["state"] = "normal"
            travelled_session_elite["state"] = "normal"
        else:
            travelled_session_edmc["state"] = "disabled"
            travelled_session_elite["state"] = "disabled"

    def update_distances(self):
        if not self.coordinates:
            for (_, distance) in self.distance_labels:
                distance["text"] = "? Ly"
        else:
            for i in range(len(self.distances)):
                system = self.distances[i]
                distance = self.calculate_distance(system["x"], system["y"], system["z"], *self.coordinates)
                self.distance_labels[i][1]["text"] = "{0} Ly".format(Locale.string_from_number(distance, 2))

        _, distance = self.travelled_labels[0]
        distance["text"] = "{0} Ly".format(Locale.string_from_number(self.distance_total, 2))
        _, distance = self.travelled_labels[1]
        distance["text"] = "{0} Ly".format(Locale.string_from_number(self.distance_session, 2))
    # endregion

    # region EDSM
    def get_system_information_from_edsm(self, button_number: int, system_name: str):
        # Don't access UI elements from here because of thread safety. Use the regular (int, str, bool) variables and fire an event
        settings_ui_elements = self.settings_ui_elements[button_number]
        settings_ui_elements.reset_response_data()

        edsmUrl = "https://www.edsm.net/api-v1/system?systemName={SYSTEM}&showCoordinates=1".format(SYSTEM=parse.quote(system_name))
        try:
            url = request.urlopen(edsmUrl, timeout=15)
            response = url.read()
            edsm_json = json.loads(response)
            if "name" in edsm_json and "coords" in edsm_json:
                settings_ui_elements.success = True
                settings_ui_elements.system_name = edsm_json["name"]
                settings_ui_elements.x = edsm_json["coords"]["x"]
                settings_ui_elements.y = edsm_json["coords"]["y"]
                settings_ui_elements.z = edsm_json["coords"]["z"]
                settings_ui_elements.status_text = f"Coordinates filled in for system {edsm_json['name']}"
            else:
                settings_ui_elements.status_text = f"Could not get system information for {system_name} from EDSM"
        except:
            settings_ui_elements.status_text = f"Could not get system information for {system_name} from EDSM"
            logger.error(f"Could not get system information for {system_name} from EDSM")
        finally:
            settings_ui_elements.has_data = True
            if self.prefs_frame:
                self.prefs_frame.event_generate(DistanceCalc.EVENT_EDSM_RESPONSE, when="tail")

    def fill_system_information_from_edsm_async(self, button_number: int, system_entry: nb.Entry):
        if system_entry.get() == "":
            self.error_label["text"] = "No system name provided."
            self.error_label.config(foreground="red")
        else:
            self.settings_ui_elements[button_number].edsm_button["state"] = tk.DISABLED
            t = Thread(name="EDSM_caller_{0}".format(button_number), target=self.get_system_information_from_edsm, args=(button_number, system_entry.get()))
            t.start()
    # endregion

    def reset_total_travelled_distance(self):
        config.set("DistanceCalc_travelled", 0)
        self.distance_total = 0.0


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
