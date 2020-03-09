"""
Utility Functions that are common to our scripts, I hope
"""
import json
import os
import sys
import re

import gdata.gauth
import gdata.sites.client as sclient
from oauth2client.service_account import ServiceAccountCredentials
from httplib2 import Http
from googleapiclient.discovery import build
import smartsheet
from pyiem.util import logger

LOG = logger()
CONFIG_FN = "/opt/datateam/config/mytokens.json"
NUMBER_RE = re.compile(r"^[-+]?\d*\.\d+$|^\d+$")
CLEANVALUE_COMPLAINED = []
CLEANVALUE_XREF = {"NA": "n/a", "dnc": "did not collect"}


def save_config(config, filename=None):
    """ Save the configuration to disk """
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
    """ Load a JSON Configuration"""
    if filename is None:
        filename = CONFIG_FN
    if not os.path.isfile(filename):
        sys.stderr.write(
            ("cscap_utils.get_config(%s) File Not Found.\n") % (filename,)
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
        LOG.info(
            "cscap_utils.cleanvalue(%s) is unaccounted for, return None",
            repr(val),
        )
        CLEANVALUE_COMPLAINED.append(val)
    return None


def translate_years(val):
    """ Convert X ('YY-'YY) into an array"""
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


def get_sites_client(config, site="sustainablecorn"):
    """ Return an authorized sites client """

    token = gdata.gauth.OAuth2Token(
        client_id=config["appauth"]["client_id"],
        client_secret=config["appauth"]["app_secret"],
        user_agent="daryl.testing",
        scope=config["googleauth"]["scopes"],
        refresh_token=config["googleauth"]["refresh_token"],
    )

    sites_client = sclient.SitesClient(site=site)
    token.authorize(sites_client)
    return sites_client


def build_treatments(feed):
    """
    Process the Treatments spreadsheet and generate a dictionary of
    field metadata
    @param feed the processed spreadsheet feed
    """
    data = None
    treatment_names = {}
    for entry in feed.entry:
        row = entry.to_dict()
        if data is None:
            data = {}
            for key in row.keys():
                if key in ["uniqueid", "name", "key"] or key[0] == "_":
                    continue
                LOG.info("Found Key: %s", key)
                data[key] = {
                    "TIL": [None],
                    "ROT": [None],
                    "DWM": [None],
                    "NIT": [None],
                    "LND": [None],
                    "REPS": 1,
                }
        if "code" not in row or row["code"] is None or row["code"] == "":
            continue
        treatment_key = row["code"]
        treatment_names[treatment_key] = row["name"].strip()
        for colkey in row.keys():
            cell = row[colkey]
            if colkey in data.keys():  # Is sitekey
                sitekey = colkey
                if cell is not None and cell != "":
                    if treatment_key[:3] in data[sitekey].keys():
                        data[sitekey][treatment_key[:3]].append(treatment_key)
                if treatment_key == "REPS" and cell not in (
                    "?",
                    "TBD",
                    "REPS",
                    None,
                ):
                    LOG.info(
                        "Found REPS for site: %s as: %s", sitekey, int(cell)
                    )
                    data[sitekey]["REPS"] = int(cell)

    return data, treatment_names


def build_sdc(feed):
    """
    Process the Site Data Collected spreadsheet
    @param feed the processed spreadsheet feed
    @return data is a two tier dictionary of years x siteids
    """
    data = None
    sdc_names = {}
    site_ids = []
    for entry in feed.entry:
        # Turn the entry into a dictionary with the first row being the keys
        row = entry.to_dict()
        if data is None:
            data = {"2011": {}, "2012": {}, "2013": {}, "2014": {}, "2015": {}}
            for key in row.keys():
                if key in ["uniqueid", "name", "key"] or key[0] == "_":
                    continue
                site_ids.append(key)
                for yr in ["2011", "2012", "2013", "2014", "2015"]:
                    data[yr][key] = []
        # If the 'KEY' column is blank or has nothing in it, skip it...
        if row["key"] is None or row["key"] == "":
            continue
        # This is our Site Data Collected Key Identifier
        sdc_key = row["key"]
        sdc_names[sdc_key] = {"name": row["name"]}

        # Iterate over our site_ids
        for sitekey in site_ids:
            if row[sitekey] is None:
                continue
            for yr in ["2011", "2012", "2013", "2014", "2015"]:
                if (
                    row[sitekey].strip().lower() == "x"
                    or row[sitekey].find("%s" % (yr[2:],)) > -1
                ):
                    data[yr][sitekey].append(sdc_key)

    return data, sdc_names


def get_driveclient(config, project="cscap"):
    """ Return an authorized apiclient """
    return get_googleapiclient(config, project, "drive", "v2")


def get_sheetsclient(config, project="cscap"):
    """ Return an authorized apiclient """
    return get_googleapiclient(config, project, "sheets", "v4")


def get_googleapiclient(config, project, ns, v):
    """Helper to get an authorized googleapiclient

    Args:
      config (dict): provider of configuration
      project (str): the project used within config
      ns (str): google endpoint to use
      v (str): google endpoint version to use
    """
    cred = ServiceAccountCredentials.from_json_keyfile_dict(
        config[project]["service_account"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    http_auth = cred.authorize(Http())
    return build(ns, v, http=http_auth)


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
            LOG.info("get_folders iterator reached 10, aborting")
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
            LOG.info("ERROR: parentfolder: %s not in f", parentfolder)
            continue
        while parentfolder in f and len(f[parentfolder]["parents"]) > 0:
            parentfolder = f[parentfolder]["parents"][0]
        f[thisfolder]["basefolder"] = parentfolder
    return f


def get_ssclient(config):
    """Return a smartsheet enabled client"""
    return smartsheet.Smartsheet(config["ss_access_token"])
