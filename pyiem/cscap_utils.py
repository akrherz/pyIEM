"""
Utility Functions that are common to our scripts, I hope
"""
from __future__ import print_function
import time
import json
import os
import sys
import random
import re

import gdata.gauth
import gdata.spreadsheets.client
import gdata.spreadsheets.data as spdata
from oauth2client.service_account import ServiceAccountCredentials
from httplib2 import Http
from apiclient.discovery import build
import smartsheet

CONFIG_FN = "/opt/datateam/config/mytokens.json"
NUMBER_RE = re.compile(r"^[-+]?\d*\.\d+$|^\d+$")
CLEANVALUE_COMPLAINED = []
CLEANVALUE_XREF = {'NA': 'n/a', 'dnc': 'did not collect'}


def save_config(config, filename=None):
    """ Save the configuration to disk """
    if filename is None:
        filename = CONFIG_FN
    json.dump(config, open(filename, 'w'), sort_keys=True,
              indent=4, separators=(',', ': '))


def get_config(filename=None):
    """ Load a JSON Configuration"""
    if filename is None:
        filename = CONFIG_FN
    if not os.path.isfile(filename):
        sys.stderr.write(("cscap_utils.get_config(%s) File Not Found.\n"
                          ) % (filename, ))
        return None
    return json.load(open(filename))


def cleanvalue(val):
    """cleanup the mess that is found in the Google Sheets for values

    Args:
      val (str): The value to clean up

    Returns:
      the cleaned value!
    """
    if val is None or val.strip() == '':
        return None
    if NUMBER_RE.match(val):
        return float(val)
    if CLEANVALUE_XREF.get(val):
        return CLEANVALUE_XREF[val]
    if val.lower() in ['did not collect', '.', 'n/a', 'clay', 'silty clay',
                       'silty clay loam', 'clay loam', 'sandy clay loam',
                       'silt loam', 'silty loam', 'sandy loam', 'sandy clay',
                       'sand', 'loam', 'silt', 'loamy sand']:
        return val.lower()
    if val.find("%") > -1:
        val = val.replace("%", "")
        if NUMBER_RE.match(val):
            return float(val)
    if val.find("<") > -1:
        return "< %s" % (val.replace("<", "").strip(), )
    if val not in CLEANVALUE_COMPLAINED:
        print(("cscap_utils.cleanvalue(%s) is unaccounted for, return None"
               ) % (repr(val), ))
        CLEANVALUE_COMPLAINED.append(val)
    return None


def translate_years(val):
    """ Convert X ('YY-'YY) into an array"""
    if val.find("-") > 0:
        tokens = re.findall('[0-9]+', val)
        one = int(tokens[0])
        two = int(tokens[1])
        one = (1900 + one) if one > 50 else (2000 + one)
        two = (1900 + two) if two > 50 else (2000 + two)
        return range(one, two+1)
    tokens = re.findall('[0-9]+', val)
    return [int("%s%s" % ("19" if int(t) > 50 else "20", t)) for t in tokens]


def exponential_backoff(func, *args, **kwargs):
    """Call Google's API with some grace to allow for errors"""
    for i in range(5):
        try:
            return func(*args, **kwargs)
        except Exception as exp:
            print("%s/5 %s traceback: %s" % (i+1, func.__name__, exp))
            time.sleep((2 ** i) + (random.randint(0, 1000) / 1000))
    return None


class Worksheet(object):
    """Our wrapper for a worksheet"""

    def __init__(self, spr_client, entry):
        """Constructor"""
        self.spr_client = spr_client
        self.entry = entry
        self.set_metadata()
        self.id = entry.id.text.split("/")[-1]
        self.spread_id = entry.id.text.split("/")[-2]

    def set_metadata(self):
        self.title = self.entry.title.text
        self.rows = int(self.entry.row_count.text)
        self.cols = int(self.entry.col_count.text)
        self.cell_feed = None
        self.list_feed = None
        self.data = {}
        self.numdata = {}

    def refetch_feed(self):
        self.entry = exponential_backoff(self.spr_client.get_worksheet,
                                         self.spread_id, self.id)
        self.set_metadata()

    def get_list_feed(self):
        """Get a ListFeed for this Worksheet

        Returns:
          list_feed
        """
        if self.list_feed is not None:
            return self.list_feed
        self.list_feed = exponential_backoff(self.spr_client.get_list_feed,
                                             self.spread_id, self.id)
        return self.list_feed

    def get_cell_feed(self):
        if self.cell_feed is not None:
            return
        self.cell_feed = exponential_backoff(self.spr_client.get_cells,
                                             self.spread_id, self.id)
        for entry in self.cell_feed.entry:
            row = entry.cell.row
            _rowstore = self.data.setdefault(row, dict())
            # https://developers.google.com/google-apps/spreadsheets/?hl=en#working_with_cell-based_feeds
            # The input_value could be a function, pick the numeric_value
            # first, which can be None for non-numeric types
            if entry.cell.numeric_value is not None:
                _numstore = self.numdata.setdefault(row, dict())
                _numstore[entry.cell.col] = entry.cell.numeric_value
            _rowstore[entry.cell.col] = entry.cell.input_value

    def get_cell_value(self, row, col, numeric=False):
        """Return the cell value

        Args:
          row (int): the raw desired
          col (int): the column desired
          numeric (bool): Attempt to use the numeric value before the text val

        Returns:
          object
        """
        if not numeric:
            return self.data.get(str(row), {}).get(str(col))
        txtval = self.data.get(str(row), {}).get(str(col))
        numval = self.numdata.get(str(row), {}).get(str(col))
        return (numval if numval is not None else txtval)

    def get_cell_entry(self, row, col):
        if self.cell_feed is None:
            self.get_cell_feed()
        for entry in self.cell_feed.entry:
            if entry.cell.row == str(row) and entry.cell.col == str(col):
                return entry
        return None

    def del_column(self, label, sloppy=False):
        """ Delete a column from the worksheet that has a given label
        this also zeros out any data in the column too

        Args:
          label (str): the column label based on the first row's value
          sloppy (bool): should we only find that the contents start the value
        """
        self.get_cell_feed()
        worked = False
        for col in range(1, int(self.cols)+1):
            if self.get_cell_value(1, col) != label and not sloppy:
                continue
            if sloppy and not self.get_cell_value(1, col).startswith(label):
                continue
            worked = True
            print('Found %s in column %s, deleting column' % (label, col))
            entry = self.get_cell_entry(1, col)
            entry.cell.input_value = ""
            exponential_backoff(self.spr_client.update, entry)

            updateFeed = spdata.build_batch_cells_update(self.spread_id,
                                                         self.id)
            for row in range(1, int(self.rows)+1):
                updateFeed.add_set_cell(str(row), str(col), "")
            self.cell_feed = exponential_backoff(self.spr_client.batch,
                                                 updateFeed, force=True)

        if not worked:
            print("Error, did not find column |%s| for deletion" % (label,))
            print("The columns were:")
            for col in range(1, int(self.cols)+1):
                print("  %2i |%s|" % (col, self.get_cell_value(1, col)))
            return
        self.refetch_feed()
        while self.trim_columns():
            print('Trimming Columns!')

    def expand_cols(self, amount=1):
        """ Expand this sheet by the number of columns desired"""
        self.cols = self.cols + amount
        self.entry.col_count.text = "%s" % (self.cols,)
        self.entry = exponential_backoff(self.spr_client.update, self.entry)
        self.cell_feed = None

    def expand_rows(self, amount=1):
        """ Expand this sheet by the number of rows desired

        Args:
          amount (int, optional): The number of rows to expand worksheet by
        """
        self.rows = self.rows + amount
        self.entry.row_count.text = "%s" % (self.rows,)
        self.entry = exponential_backoff(self.spr_client.update, self.entry)

    def add_column(self, label, row2=None, row3=None):
        """ Add a column, if it does not exist """
        self.get_cell_feed()
        for col in range(1, int(self.cols)+1):
            if self.get_cell_value("1", col) == label:
                print('Column %s with label already found: %s' % (col, label))
                return
        self.expand_cols(1)

        for i, lbl in enumerate([label, row2, row3]):
            if lbl is None:
                continue
            entry = exponential_backoff(self.spr_client.get_cell,
                                        self.spread_id, self.id,
                                        str(i+1),
                                        str(self.cols))
            entry.cell.input_value = lbl
            exponential_backoff(self.spr_client.update, entry)

        self.refetch_feed()
        self.cell_feed = None

    def drop_last_column(self):
        self.cols = self.cols - 1
        self.entry.col_count.text = "%s" % (self.cols,)
        self.entry = exponential_backoff(self.spr_client.update, self.entry)
        self.cell_feed = None

    def trim_columns(self):
        """ Attempt to trim off any extraneous columns """
        self.get_cell_feed()
        for col in range(1, int(self.cols)+1):
            if self.data["1"].get(str(col)) is not None:
                continue
            print('Column Delete Candidate %s' % (col,))
            found_data = False
            for row in range(1, int(self.rows)+1):
                _v = self.data.get(str(row), {}).get(str(col))
                if _v not in [None, 'n/a', 'did not collect']:
                    found_data = True
                    print(('ERROR row: %s has data: %s'
                           ) % (row, self.data[str(row)][str(col)]))
            if not found_data:
                print('Deleting column %s' % (col,))
                if col == int(self.cols):
                    self.drop_last_column()
                    return True
                # Move columns left
                updateFeed = spdata.build_batch_cells_update(self.spread_id,
                                                             self.id)
                for col2 in range(int(col), int(self.cols)):
                    for row in range(1, int(self.rows)+1):
                        updateFeed.add_set_cell(str(row), str(col2),
                                                self.get_cell_value(row,
                                                                    col2 + 1))
                self.cell_feed = exponential_backoff(self.spr_client.batch,
                                                     updateFeed, force=True)
                # Drop last column
                self.refetch_feed()
                self.drop_last_column()
                return True
        return False


class Spreadsheet(object):

    def __init__(self, spr_client, resource_id):
        self.spr_client = spr_client
        self.id = resource_id
        self.worksheets = {}
        self.get_worksheets()

    def get_worksheets(self):
        """ Get the worksheets associated with this spreadsheet """
        feed = exponential_backoff(self.spr_client.GetWorksheets, self.id)
        if feed is None:
            return
        for entry in feed.entry:
            self.worksheets[entry.title.text] = Worksheet(self.spr_client,
                                                          entry)


def get_xref_siteids_plotids(drive, spr_client, config):
    ''' Get a dict of site IDs with a list of plot IDs for each '''
    spreadkeys = get_xref_plotids(drive)
    data = {}
    for uniqueid in spreadkeys.keys():
        data[uniqueid.lower()] = []
        feed = exponential_backoff(spr_client.get_list_feed,
                                   spreadkeys[uniqueid], 'od6')
        for entry in feed.entry:
            row = entry.to_dict()
            if row['plotid'] is None:
                continue
            data[uniqueid.lower()].append(row['plotid'].lower())
    return data


def get_xref_plotids(drive):
    """Dictionary of Sites to PlotID keys

    Args:
      drive: authorized Google Drive API client

    Returns:
      dict
    """
    res = drive.files().list(q="title contains 'Plot Identifiers'").execute()
    data = {}
    for item in res['items']:
        if item['mimeType'] != 'application/vnd.google-apps.spreadsheet':
            continue
        siteid = item['title'].split()[0]
        data[siteid] = item['id']
    return data


def get_spreadsheet_client(config):
    """ Return an authorized spreadsheet client """
    token = gdata.gauth.OAuth2Token(
        client_id=config['appauth']['client_id'],
        client_secret=config['appauth']['app_secret'],
        user_agent='daryl.testing',
        scope=config['googleauth']['scopes'],
        refresh_token=config['googleauth']['refresh_token'])

    spr_client = gdata.spreadsheets.client.SpreadsheetsClient()
    token.authorize(spr_client)
    return spr_client


def get_sites_client(config, site='sustainablecorn'):
    """ Return an authorized sites client """
    import gdata.sites.client as sclient
    token = gdata.gauth.OAuth2Token(
        client_id=config['appauth']['client_id'],
        client_secret=config['appauth']['app_secret'],
        user_agent='daryl.testing',
        scope=config['googleauth']['scopes'],
        refresh_token=config['googleauth']['refresh_token'])

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
                if key in ['uniqueid', 'name', 'key'] or key[0] == '_':
                    continue
                print('Found Key: %s' % (key,))
                data[key] = {'TIL': [None, ], 'ROT': [None, ], 'DWM': [None, ],
                             'NIT': [None, ],
                             'LND': [None, ], 'REPS': 1}
        if 'code' not in row or row['code'] is None or row['code'] == '':
            continue
        treatment_key = row['code']
        treatment_names[treatment_key] = row['name'].strip()
        for colkey in row.keys():
            cell = row[colkey]
            if colkey in data.keys():  # Is sitekey
                sitekey = colkey
                if cell is not None and cell != '':
                    if treatment_key[:3] in data[sitekey].keys():
                        data[sitekey][treatment_key[:3]].append(treatment_key)
                if treatment_key == 'REPS' and cell not in ('?', 'TBD',
                                                            'REPS', None):
                    print(('Found REPS for site: %s as: %s'
                           ) % (sitekey, int(cell)))
                    data[sitekey]['REPS'] = int(cell)

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
            data = {'2011': {}, '2012': {}, '2013': {}, '2014': {}, '2015': {}}
            for key in row.keys():
                if key in ['uniqueid', 'name', 'key'] or key[0] == '_':
                    continue
                site_ids.append(key)
                for yr in ['2011', '2012', '2013', '2014', '2015']:
                    data[yr][key] = []
        # If the 'KEY' column is blank or has nothing in it, skip it...
        if row['key'] is None or row['key'] == '':
            continue
        # This is our Site Data Collected Key Identifier
        sdc_key = row['key']
        sdc_names[sdc_key] = {'name': row['name']}

        # Iterate over our site_ids
        for sitekey in site_ids:
            if row[sitekey] is None:
                continue
            for yr in ['2011', '2012', '2013', '2014', '2015']:
                if (row[sitekey].strip().lower() == 'x' or
                        row[sitekey].find('%s' % (yr[2:],)) > -1):
                    data[yr][sitekey].append(sdc_key)

    return data, sdc_names


def get_site_metadata(config, spr_client=None):
    '''
    Return a dict of research site metadata
    '''
    meta = {}
    if spr_client is None:
        spr_client = get_spreadsheet_client(config)

    lf = exponential_backoff(spr_client.get_list_feed,
                             config['cscap']['metamaster'], 'od6')
    for entry in lf.entry:
        d = entry.to_dict()
        meta[d['uniqueid']] = {'climate_site': d['iemclimatesite'].split()[0],
                               }
    return meta


def get_driveclient(config, project="cscap"):
    """ Return an authorized apiclient """
    return get_googleapiclient(config, project, 'drive', 'v2')


def get_sheetsclient(config, project="cscap"):
    """ Return an authorized apiclient """
    return get_googleapiclient(config, project, 'sheets', 'v4')


def get_googleapiclient(config, project, ns, v):
    """Helper to get an authorized googleapiclient

    Args:
      config (dict): provider of configuration
      project (str): the project used within config
      ns (str): google endpoint to use
      v (str): google endpoint version to use
    """
    cred = ServiceAccountCredentials.from_json_keyfile_dict(
            config[project]['service_account'],
            scopes=['https://www.googleapis.com/auth/drive'])
    http_auth = cred.authorize(Http())
    return build(ns, v, http=http_auth)


def get_folders(drive):
    """Return a dict of Google Drive Folders"""
    f = {}

    folders = drive.files().list(
        q="mimeType = 'application/vnd.google-apps.folder'",
        maxResults=999).execute()
    for _, item in enumerate(folders['items']):
        f[item['id']] = dict(title=item['title'], parents=[],
                             basefolder=None)
        for parent in item['parents']:
            f[item['id']]['parents'].append(parent['id'])

    for thisfolder in f:
        # title = f[thisfolder]['title']
        if len(f[thisfolder]['parents']) == 0:
            continue
        parentfolder = f[thisfolder]['parents'][0]
        if parentfolder not in f:
            print("ERROR: parentfolder: %s not in f" % (parentfolder,))
            continue
        while parentfolder in f and len(f[parentfolder]['parents']) > 0:
            parentfolder = f[parentfolder]['parents'][0]
        # print title, '->', f[parentfolder]['title']
        f[thisfolder]['basefolder'] = parentfolder
    return f


def get_ssclient(config):
    """Return a smartsheet enabled client"""
    return smartsheet.Smartsheet(config['ss_access_token'])
