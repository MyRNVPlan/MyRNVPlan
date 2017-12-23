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
        stations = jdata["stations"]

    except:
        print("Couldn't download global stations list")
        raise

    print(str(datetime.datetime.now()) + " Updated stations list")
    next_call_stations = next_call_stations + 1800
    threading.Timer(next_call_stations - time.time(), getstations).start()
    print(stations)


def downloadstationjson(longname, stationid, date):
    try:
        # todo pass date in proper format! needs to be time object (from package time)
        jdata = rnv.getstationmonitor(stationid)
        jdata["longName"] = longname

        return jdata
    except:
        print("Download of station failed: " + longname + " " + date)
        pass

    return []


@app.route('/')
def show_index():
    return render_template("index.html", stations=stations)


@app.route("/favicon.ico") # ignore favicons
def ignore_favicon():
    return ""


def get_stations(path):
    global cached_stations

    d = datetime.datetime.now()
    date = d.strftime("%Y-%m-%d+%R")
    cdate = d.strftime("%R")

    stats = []

    tmp = list(set(path.split('/')))

    # stations is a global list containing all station classes
    for station in tmp:
        for stat in stations:
            if str(stat["shortName"]).lower() == station.lower() or str(stat["longName"]).lower() == station.lower():
                if station.lower() in cached_stations:
                    if cached_stations[station.lower()]["date"] == cdate:
                        print("Station found and valid: " + station.lower() + " " + date)
                        stats.append(cached_stations[station.lower()])
                    else:  # outdated
                        print("Station found but not valid: " + station.lower() + " " + date)
                        del cached_stations[station.lower()]
                        tmp = downloadstationjson(stat["longName"], stat["hafasID"], date)
                        tmp["date"] = cdate
                        cached_stations[stat["longName"].lower(), stat["shortName"].lower()] = tmp
                        stats.append(tmp)
                else:
                    print("Station not in cache: " + station.lower() + " " + date)
                    tmp = downloadstationjson(stat["longName"], stat["hafasID"], date)
                    tmp["date"] = cdate
                    cached_stations[stat["longName"].lower(), stat["shortName"].lower()] = tmp

                    stats.append(tmp)

    return stats

@app.route("/<path:path>")
def show_stations(path):
    d = datetime.datetime.now()

    stats = get_stations(path)

    tmplines = {}

    hdr = ""
    for stat in stats:
        print(stat)
        # remove whitespaces from lines, eg. M 1 -> M1
        for dep in stat["listOfDepartures"]:
            dep["lineLabel"] = dep["lineLabel"].replace(' ', '')
            lineid = dep["lineLabel"]

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
    if hdr != "":
        hdr += "</style>"

    return render_template("station.html", stations=stats, time=d.strftime("%R"), header=Markup(hdr))


rnv = pyrnvapi.RNVStartInfoApi(get_env_variable("RNV_API_KEY"))  # rnv key

# global list of all available stations and all available lines
stations = []
lines = {}

# caching of requested stations
next_call_stations = time.time()
cached_stations = multi_key_dict()


if __name__ == "__main__":
    getstations()
    getlines()

    app.run()
