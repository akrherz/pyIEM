"""
Utility Functions that are common to our scripts, I hope
"""
import json
import os
import sys
import re

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import smartsheet
from pyiem.util import LOG

CONFIG_FN = "/opt/datateam/config/mytokens.json"
NUMBER_RE = re.compile(r"^[-+]?\d*\.\d+$|^\d+$")
CLEANVALUE_COMPLAINED = []
CLEANVALUE_XREF = {"NA": "n/a", "dnc": "did not collect"}


def save_config(config, filename=None):
    """Save the configuration to disk"""
    if filename is None:
        filename = CONFIG_FN
    json.dump(
        config,
        open(filename, "w"),
        sort_keys=True,
        indent=4,
        separators=(",", ": "),
    )


def get_config(filename=None):
    """Load a JSON Configuration"""
    if filename is None:
        filename = CONFIG_FN
    if not os.path.isfile(filename):
        sys.stderr.write(
            f"cscap_utils.get_config({filename}) File Not Found.\n"
        )
        return None
    return json.load(open(filename))


def cleanvalue(val):
    """cleanup the mess that is found in the Google Sheets for values

    Args:
      val (str): The value to clean up

    Returns:
      the cleaned value!
    """
    if val is None or val.strip() == "":
        return None
    if NUMBER_RE.match(val):
        return float(val)
    if CLEANVALUE_XREF.get(val):
        return CLEANVALUE_XREF[val]
    if val.lower() in [
        "did not collect",
        ".",
        "n/a",
        "clay",
        "silty clay",
        "silty clay loam",
        "clay loam",
        "sandy clay loam",
        "silt loam",
        "silty loam",
        "sandy loam",
        "sandy clay",
        "sand",
        "loam",
        "silt",
        "loamy sand",
    ]:
        return val.lower()
    if val.find("%") > -1:
        val = val.replace("%", "")
        if NUMBER_RE.match(val):
            return float(val)
    if val.find("<") > -1:
        return "< %s" % (val.replace("<", "").strip(),)
    if val not in CLEANVALUE_COMPLAINED:
        LOG.warning(
            "cscap_utils.cleanvalue(%s) is unaccounted for, return None",
            repr(val),
        )
        CLEANVALUE_COMPLAINED.append(val)
    return None


def translate_years(val):
    """Convert X ('YY-'YY) into an array"""
    if val.find("-") > 0:
        tokens = re.findall("[0-9]+", val)
        one = int(tokens[0])
        two = int(tokens[1])
        one = (1900 + one) if one > 50 else (2000 + one)
        two = (1900 + two) if two > 50 else (2000 + two)
        return range(one, two + 1)
    tokens = re.findall("[0-9]+", val)
    return [int("%s%s" % ("19" if int(t) > 50 else "20", t)) for t in tokens]


def get_xref_plotids(drive):
    """Dictionary of Sites to PlotID keys

    Args:
      drive: authorized Google Drive API client

    Returns:
      dict
    """
    res = drive.files().list(q="title contains 'Plot Identifiers'").execute()
    data = {}
    for item in res["items"]:
        if item["mimeType"] != "application/vnd.google-apps.spreadsheet":
            continue
        siteid = item["title"].split()[0]
        data[siteid] = item["id"]
    return data


def get_driveclient(config, project="cscap"):
    """Return an authorized apiclient"""
    return get_googleapiclient(config, project, "drive", "v2")


def get_sheetsclient(config, project="cscap"):
    """Return an authorized apiclient"""
    return get_googleapiclient(config, project, "sheets", "v4")


def get_googleapiclient(config, project, ns, v):
    """Helper to get an authorized googleapiclient

    Args:
      config (dict): provider of configuration
      project (str): the project used within config
      ns (str): google endpoint to use
      v (str): google endpoint version to use
    """
    cred = Credentials.from_service_account_info(
        config[project]["service_account"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build(ns, v, credentials=cred)


def get_folders(drive):
    """Return a dict of Google Drive Folders"""
    f = {}

    # Whoa, just because maxResults=999 and the returned items is less
    # than 999, it does not mean the list was complete
    folders = (
        drive.files()
        .list(
            q="mimeType = 'application/vnd.google-apps.folder'", maxResults=999
        )
        .execute()
    )
    folder_list = folders["items"]
    i = 0
    while "nextPageToken" in folders:
        folders = (
            drive.files()
            .list(
                pageToken=folders["nextPageToken"],
                q="mimeType = 'application/vnd.google-apps.folder'",
                maxResults=999,
            )
            .execute()
        )
        folder_list = folder_list + folders["items"]
        i += 1
        if i > 10:
            LOG.warning("get_folders iterator reached 10, aborting")
            break

    for _, item in enumerate(folder_list):
        f[item["id"]] = dict(title=item["title"], parents=[], basefolder=None)
        for parent in item["parents"]:
            f[item["id"]]["parents"].append(parent["id"])

    for thisfolder in f:
        # title = f[thisfolder]['title']
        if not f[thisfolder]["parents"]:
            continue
        parentfolder = f[thisfolder]["parents"][0]
        if parentfolder not in f:
            LOG.warning("ERROR: parentfolder: %s not in f", parentfolder)
            continue
        while parentfolder in f and len(f[parentfolder]["parents"]) > 0:
            parentfolder = f[parentfolder]["parents"][0]
        f[thisfolder]["basefolder"] = parentfolder
    return f


def get_ssclient(config):
    """Return a smartsheet enabled client"""
    return smartsheet.Smartsheet(config["ss_access_token"])
