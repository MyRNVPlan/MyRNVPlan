from flask import Flask, render_template, Markup
from multi_key_dict import multi_key_dict
from collections import OrderedDict

import datetime
import threading
import time
import sys
import os
import re

import pyrnvapi

app = Flask(__name__)

if "DEBUG" in os.environ:
    DEBUG = True
    os.environ["FLASK_DEBUG"] = "True"
    print("***Running in DEBUG mode!***")
else:
    DEBUG = False


# receives environment variables
def get_env_variable(varname, *, default=None, defaulttext=None, check_debug=True):
    try:
        value = os.environ[varname]
    except KeyError:
        if default is None or (check_debug and not DEBUG):
            print("ENV Variable '{}' not set. Exiting program.".format(varname))
            sys.exit(1)
        else:
            if defaulttext:
                print("   " + defaulttext)
            value = default
    if DEBUG:
        print("{:20} {}".format(varname + ":", value))
    return value


def gen_css():
    global glines

    for line in glines:
        print("#s" + line + ":before{")
        print("\tcontent:\"" + line + "\";")
        print("\tbackground-color: #" + glines[line]["hexcolor"] + ";")
        print("\tcolor: #" + glines[line]["textcolor"] + ";")
        if glines[line]["lineType"] != "STRB":
            print("\tborder-radius: 50%;")  # cirle for buses
        print("\tpadding: 5px;")
        print("}")
        print()


def get_all_lines():
    try:
        global glines

        jdata = rnv.getalllines()

        # converting list to dict, to use lineID as key
        for line in jdata:
            # add default textcolor
            if "M " in line["lineID"]:
                line["textcolor"] = "000000"  # white for moonliner, because of yellow background
            else:
                line["textcolor"] = "ffffff"  # black for every other line
            glines[line["lineID"].replace(' ', '')] = line

    except:
        print("Couldn't download global lines list")
        raise


def get_all_stations():
    try:
        global gnext_call_stations
        global gstations
        global gstations_sorted

        jdata = rnv.getstationpackage(regionid="1")

        for station in jdata["stations"]:
            # patch shortName for Waldschloß because it collides with Waidalle
            if station["longName"] == "Waldschloß":
                station["shortName"] = "WHWS"

            try:
                gstations[station["longName"].lower(), station["shortName"].lower(), str(station["hafasID"])] = station
            except KeyError:
                # Some stationnames have several ids, if insertion fails, ignore them!
                # So we query both and take the one which returns more informations...
                stat1 = len(rnv.getstationmonitor(gstations[station["shortName"].lower()]["hafasID"]))
                stat2 = len(rnv.getstationmonitor(station["hafasID"]))
                if stat1 < stat2:
                    continue  # ignore new entry
                del gstations[station["shortName"].lower()]
                gstations[station["longName"].lower(), station["shortName"].lower(), str(station["hafasID"])] = station

            gstations_sorted[station["shortName"]] = station["longName"]

            if "platforms" in gstations[str(station["hafasID"])]:
                gstations[str(station["hafasID"])].pop('platforms', None)
    except:
        print("Couldn't download global stations list")
        raise

    print(str(datetime.datetime.now()) + " Updated stations list")
    next_call_stations = gnext_call_stations + 1800
    threading.Timer(next_call_stations - time.time(), get_all_stations).start()
    print(gstations)


def get_station_json(longname, stationid, date, poles=""):
    try:
        # todo pass date in proper format! needs to be time object (from package time)
        jdata = rnv.getstationmonitor(stationid, poles=poles)
        jdata["longName"] = longname

        return jdata

    except:
        print("Download of station failed: " + longname + " " + date)
        pass

    return []


def get_pole_info_json(stationid):
    try:
        jdata = rnv.getstationdetail(stationid)

        return jdata
    except:
        print("Download station platform information: " + stationid)

    return []


def add_poles_to_station(stationid):
    global gstations

    poles = get_pole_info_json(stationid)

    for pole in poles:
        if "platforms" not in gstations[stationid]:
            gstations[stationid]['platforms'] = {}
        if not pole["active"]:
            continue
        if pole['platform'].lower() in gstations[stationid]['platforms']:
            gstations[stationid]['platforms'][pole['platform'].lower()] += ';' + str(pole['pole'])
        else:
            gstations[stationid]['platforms'][pole['platform'].lower()] = str(pole['pole'])


def get_called_stations(path):
    global gcached_stations

    d = datetime.datetime.now()
    date = d.strftime("%Y-%m-%d+%R")
    cdate = d.strftime("%R")

    stats = []

    # we have to account stuff like:
    # /Im Eichwald/Bismarckplatz/A/B/H/F/
    # -> Show all poles from "Im Eichwald" and only poles A, B, H and F from Bismarckplatz

    laststation = ""
    stations = {}
    for item in path.split('/'):
        item = re.sub(r"\+\+", r"/", item)

        if item == "" or item.isdigit():
            continue

        if item.lower() in gstations:
            laststation = item.lower()
            stations[laststation] = ""

            if "platforms" not in gstations[laststation]:
                add_poles_to_station(gstations[laststation]['hafasID'])

        else:
            if laststation != "":
                if "platforms" not in gstations[laststation]:
                    add_poles_to_station(gstations[laststation]['hafasID'])

                if item.lower() not in gstations[laststation]["platforms"]:
                    continue

                if stations[laststation] != "":
                    stations[laststation] += ";" + gstations[laststation]["platforms"][item.lower()]
                else:
                    stations[laststation] = gstations[laststation]["platforms"][item.lower()]

    # stations is a global list containing all station classes
    for station in stations:
        if station.lower() not in gstations:
            continue

        stat = gstations[station.lower()]

        if stations[station] != "":
            if DEBUG:
                print("Station with specific poles: " + station.lower() + " " + stations[station])
            dstat = get_station_json(stat["longName"], stat["hafasID"], date, poles=stations[station])
            dstat["shortName"] = stat["shortName"]

            for s in dstat["listOfDepartures"]:
                s["color"] = get_lateness_color(s)
            stats.append(dstat)

            continue

        dstat = get_station_json(stat["longName"], stat["hafasID"], date)
        dstat["shortName"] = stat["shortName"]
        dstat["date"] = cdate

        if station.lower() in gcached_stations:
            if gcached_stations[station.lower()]["date"] == cdate:
                if DEBUG:
                    print("Station found and valid: " + station.lower() + " " + date)
                stats.append(gcached_stations[station.lower()])
            else:  # outdated
                if DEBUG:
                    print("Station found but not valid: " + station.lower() + " " + date)
                del gcached_stations[station.lower()]

                for s in dstat["listOfDepartures"]:
                    s["color"] = get_lateness_color(s)

                gcached_stations[stat["longName"].lower(), stat["shortName"].lower()] = dstat
                stats.append(dstat)
        else:
            if DEBUG:
                print("Station not in cache: " + station.lower() + " " + date)
            for s in dstat["listOfDepartures"]:
                s["color"] = get_lateness_color(s)

            gcached_stations[stat["longName"].lower(), stat["shortName"].lower()] = dstat

            stats.append(dstat)

    return stats


def get_lateness_color(station):
    color = ["#21ff11", "#88ff11", "#bfff11", "#e7ff11",
             "#ffc711", "#ff9f11", "#ff6411", "#ff4011",
             "#ff2811", "#ff1111"]

    if len(station["time"].split('+')) <= 1:
        return color[0]

    if int(station["time"].split('+')[1]) >= len(color):
        return color[-1]

    return color[int(station["time"].split('+')[1])]


@app.route('/')
def show_index():
    return render_template("index.html", stations=gstations_sorted)


@app.route("/favicon.ico")  # ignore favicons
def ignore_favicon():
    return ""


@app.route("/<path:path>")
def show_stations(path):
    d = datetime.datetime.now()

    stats = get_called_stations(path)

    tmplines = {}

    title = ""
    hdr = ""
    for stat in stats:
        title += stat["longName"] + " | "
        if DEBUG:
            print("Prepared station:")
            print(stat)
        # remove whitespaces from lines, eg. "M 1" -> "M1"
        for dep in stat["listOfDepartures"]:
            dep["lineLabel"] = dep["lineLabel"].replace(' ', '')
            lineid = dep["lineLabel"]

            # display the correct platform
            if "platform" in dep:
                # last position in string from (ex. "Steig A") is our desired platform name
                if len(dep["platform"]) < 10:  # some cheap method to detect if we haven't modified this before...
                    dep["platform"] = "<a href=/" + stat["shortName"] + "/" + dep["platform"][-1:] + ">" \
                                      + dep["platform"] + "</a>"

            # if we have a new line, not in the lines list, we still want to display with css the line number
            if (lineid not in glines) and (lineid not in tmplines):
                if hdr == "":
                    hdr += "<style>"
                hdr += "#s" + lineid + ":before{\n"
                hdr += "content:\"" + lineid + "\";\n"
                hdr += "color: black;\n"
                hdr += "padding: 5px;\n}\n"
                # and also add the new line to our temporary lines list
                tmplines[lineid] = lineid

    title = title[:-3]  # remove last 3 chars

    if hdr != "":
        hdr += "</style>"

    return render_template("station.html",
                           stations=stats,
                           time=d.strftime("%R"),
                           header=Markup(hdr),
                           title=title)


rnv = pyrnvapi.RNVStartInfoApi(get_env_variable("RNV_API_KEY"))  # rnv key

# global list of all available stations and all available lines
gstations = multi_key_dict()
gstations_sorted = OrderedDict()
glines = {}

# caching of requested stations
gnext_call_stations = time.time()
gcached_stations = multi_key_dict()

if __name__ == "__main__":
    get_all_stations()
    get_all_lines()
    # gen_css()

    app.run()
