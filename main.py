from flask import Flask, render_template, Markup
from multi_key_dict import multi_key_dict

import datetime
import threading
import time
import sys
import os

import pyrnvapi


app = Flask(__name__)

if "DEBUG" in os.environ:
    DEBUG = True
    print("***Running in DEBUG mode!***")
else:
    DEBUG = False


# receives environment variables
def get_env_variable(varname, *, default=None, defaulttext=None, check_debug=True):
    try:
        value = os.environ[varname]
    except KeyError:
        if default == None or (check_debug and not DEBUG):
            print("ENV Variable '{}' not set. Exiting program.".format(varname))
            sys.exit(1)
        else:
            if defaulttext: print("   "+defaulttext)
            value = default
    if DEBUG:
        print("{:20} {}".format(varname+":", value))
    return value


def genCss():
    for line in lines:
        print("#s" + line + ":before{")
        print("\tcontent:\"" + line + "\";")
        print("\tbackground-color: #" + lines[line]["hexcolor"] + ";")
        print("\tcolor: #" + lines[line]["textcolor"] + ";")
        if lines[line]["lineType"] == "BUS":
            print("\tborder-radius: 50%;") #cirle for buses
        print("\tpadding: 5px;")
        print("}")
        print()


def getlines():
    try:
        global lines

        jdata = rnv.getalllines()

        # converting list to dict, to use lineID as key
        for line in jdata:
            # add default textcolor
            if "M " in line["lineID"]:
                line["textcolor"] = "000000" # white for moonliner, because of yellow background
            else:
                line["textcolor"] = "ffffff" # black for every other line
            lines[line["lineID"].replace(' ', '')] = line

    except:
        print("Couldn't download global lines list")
        raise


def getstations():
    try:
        global next_call_stations
        global stations

        jdata = rnv.getstationpackage(regionid="1")

        for station in jdata["stations"]:
            # patch shortName for Waldschloß because it collides with Waidalle
            if station["longName"] == "Waldschloß":
                station["shortName"] = "WHWS"

            stations[station["longName"].lower(), station["shortName"].lower(), str(station["hafasID"])] = station

    except:
        print("Couldn't download global stations list")
        raise

    print(str(datetime.datetime.now()) + " Updated stations list")
    next_call_stations = next_call_stations + 1800
    threading.Timer(next_call_stations - time.time(), getstations).start()
    print(stations)


def downloadstationjson(longname, stationid, date, poles=""):
    try:
        # todo pass date in proper format! needs to be time object (from package time)
        jdata = rnv.getstationmonitor(stationid, poles=poles)
        jdata["longName"] = longname

        return jdata

    except:
        print("Download of station failed: " + longname + " " + date)
        pass

    return []


@app.route('/')
def show_index():
    return render_template("index.html", stations=stations)


@app.route("/favicon.ico")  # ignore favicons
def ignore_favicon():
    return ""


def get_stations(path):
    global cached_stations

    d = datetime.datetime.now()
    date = d.strftime("%Y-%m-%d+%R")
    cdate = d.strftime("%R")

    stats = []

    tmp = {}
    t2 = []
    for item in path.split('/'):
        if item.isdigit():
            if tmp[t2[-1]] == "":
                tmp[t2[-1]] += str(item)
            else:
                tmp[t2[-1]] += ";" + str(item)
        else:
            t2.append(item)
            tmp[t2[-1]] = ""

    # stations is a global list containing all station classes
    for station in tmp:
        if station.lower() in stations:
            stat = stations[station.lower()]
            if tmp[station] != "":
                print("Station with specific poles: " + station.lower() + " " + tmp[station])
                dstat = downloadstationjson(stat["longName"], stat["hafasID"], date, poles=tmp[station])
                dstat["shortName"] = stat["shortName"]
                for s in dstat["listOfDepartures"]:
                    s["color"] = getColor(s)
                stats.append(dstat)
                continue

            if station.lower() in cached_stations:
                if cached_stations[station.lower()]["date"] == cdate:
                    print("Station found and valid: " + station.lower() + " " + date)
                    stats.append(cached_stations[station.lower()])
                else:  # outdated
                    print("Station found but not valid: " + station.lower() + " " + date)
                    del cached_stations[station.lower()]
                    dstat = downloadstationjson(stat["longName"], stat["hafasID"], date)
                    dstat["shortName"] = stat["shortName"]
                    dstat["date"] = cdate
                    for s in dstat["listOfDepartures"]:
                        s["color"] = getColor(s)

                    cached_stations[stat["longName"].lower(), stat["shortName"].lower()] = dstat
                    stats.append(dstat)
            else:
                print("Station not in cache: " + station.lower() + " " + date)
                dstat = downloadstationjson(stat["longName"], stat["hafasID"], date)
                dstat["shortName"] = stat["shortName"]

                dstat["date"] = cdate

                for s in dstat["listOfDepartures"]:
                    s["color"] = getColor(s)

                cached_stations[stat["longName"].lower(), stat["shortName"].lower()] = dstat

                stats.append(dstat)

    return stats


def getColor(station):
    color = ["#21ff11", "#88ff11", "#bfff11", "#e7ff11",
             "#ffc711", "#ff9f11", "#ff6411", "#ff4011",
             "#ff2811", "#ff1111"]

    if len(station["time"].split('+')) <= 1:
        return color[0]

    if int(station["time"].split('+')[1]) >= len(color):
        return color[-1]

    return color[int(station["time"].split('+')[1])]


@app.route("/<path:path>")
def show_stations(path):
    d = datetime.datetime.now()

    stats = get_stations(path)

    tmplines = {}

    title = ""
    hdr = ""
    for stat in stats:
        title += stat["longName"] + " | "
        if DEBUG:
            print("Prepared station:")
            print(stat)
        # remove whitespaces from lines, eg. M 1 -> M1
        for dep in stat["listOfDepartures"]:
            dep["lineLabel"] = dep["lineLabel"].replace(' ', '')
            lineid = dep["lineLabel"]

            if dep["platform"] in pole_translation:
                dep["platform"] = "<a href=/" + stat["shortName"] + "/" + pole_translation[dep["platform"]] + ">" \
                              + dep["platform"] + "</a>"

            # if we have a new line, not in the lines list, we still want to display with css the line number
            if (lineid not in lines) and (lineid not in tmplines):
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
stations = multi_key_dict()
lines = {}

pole_translation = {"Steig A" : "1", "Steig B": "2", "Steig C": "3", "Steig D": "4", "Steig E": "5", "Steig F": "6",
                    "Steig G": "7", "Steig H": "8", "Steig I": "9", "Steig J": "10", "Steig K": "11","Steig L": "12",
                    "Steig M": "13", "Steig N": "14", "Steig O": "15", "Steig P": "16", "Steig Q": "17",
                    "Steig R": "18",  "Steig S": "19", "Steig T": "20", "Steig U": "21", "Steig V": "22",
                    "Steig W": "23", "Steig X": "24", "Steig Y": "25", "Steig Z": "26"}

# caching of requested stations
next_call_stations = time.time()
cached_stations = multi_key_dict()


if __name__ == "__main__":
    getstations()
    getlines()

    app.run()
