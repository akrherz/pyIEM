"""A client to Box.com using Python Box SDK"""
from boxsdk import OAuth2, Client
import psycopg2
import os
import sys
from tqdm import tqdm


class Session(object):
    """Represents a ongoing / running session with Box API"""
    IEM_PROPERTIES_ACCESS_TOKEN = 'boxclient.access_token'
    IEM_PROPERTIES_REFRESH_TOKEN = 'boxclient.refresh_token'
    IEM_PROPERTIES_CLIENT_ID = 'boxclient.client_id'
    IEM_PROPERTIES_CLIENT_SECRET = 'boxclient.client_secret'

    def __init__(self, client_id=None, client_secret=None,
                 access_token=None, refresh_token=None, store_tokens=None):
        """constructor

        Args:
          client_id (str): The application box client_id
          client_secret (str): The application box client_secret
          access_token (str): The Oauth2 access_token
          refresh_token (str): The Oauth2 refresh_token
          store_tokens (function): The Oauth2 callback on new tokens
        """
        st = self.iem_token_callback if store_tokens is None else store_tokens
        if client_id is None:
            self.dbbootstrap(st)
        else:
            self.client_id = client_id
            self.client_secret = client_secret
            oauth = OAuth2(client_id=self.client_id,
                           client_secret=self.client_secret,
                           access_token=access_token,
                           refresh_token=refresh_token, store_tokens=st)
            self.client = Client(oauth)

    def dbbootstrap(self, store_tokens):
        """Get configuration from IEM Database"""
        pgconn = psycopg2.connect(database='mesosite', host='iemdb')
        cursor = pgconn.cursor()
        cursor.execute("""SELECT propvalue from properties where
        propname = %s""", (self.IEM_PROPERTIES_CLIENT_ID,))
        self.client_id = cursor.fetchone()[0]
        cursor.execute("""SELECT propvalue from properties where
        propname = %s""", (self.IEM_PROPERTIES_CLIENT_SECRET,))
        self.client_secret = cursor.fetchone()[0]
        cursor.execute("""SELECT propvalue from properties where
        propname = %s""", (self.IEM_PROPERTIES_ACCESS_TOKEN,))
        access_token = cursor.fetchone()[0]
        cursor.execute("""SELECT propvalue from properties where
        propname = %s""", (self.IEM_PROPERTIES_REFRESH_TOKEN,))
        refresh_token = cursor.fetchone()[0]
        oauth = OAuth2(client_id=self.client_id,
                       client_secret=self.client_secret,
                       access_token=access_token,
                       refresh_token=refresh_token, store_tokens=store_tokens)
        self.client = Client(oauth)

    def iem_token_callback(self, access_token, refresh_token):
        oauth = OAuth2(client_id=self.client_id,
                       client_secret=self.client_secret,
                       access_token=access_token,
                       refresh_token=refresh_token,
                       store_tokens=self.iem_token_callback)
        self.client = Client(oauth)
        pgconn = psycopg2.connect(database='mesosite', host='iemdb')
        cursor = pgconn.cursor()
        for propname, propvalue in zip([self.IEM_PROPERTIES_ACCESS_TOKEN,
                                        self.IEM_PROPERTIES_REFRESH_TOKEN],
                                       [access_token, refresh_token]):
            cursor.execute("""
                UPDATE properties SET propvalue = %s WHERE propname = %s
            """, (propvalue, propname))
        cursor.close()
        pgconn.commit()

    def get_folder(self, remote_folder):
        """Get or Create a remote folder on Box

        Args:
          remote_folder (str): the full remote path of the folder
        """
        # print("get_folder(%s)" % (repr(remote_folder),))
        dirs = remote_folder.split("/")
        root = self.client.folder(folder_id=0)
        for dirname in dirs:
            if dirname == '':
                continue
            # BUG folders over 1000 items :/
            found = False
            for item in root.get_items(1000):
                if item.name == dirname:
                    root = self.client.folder(item.object_id)
                    found = True
                    break
            if not found:
                root = root.create_subfolder(dirname)
        return root

    def rmirror(self, local_folder, remote_folder):
        """Recursively send local_folder to remote_folder"""
        for root, _, filenames in os.walk(local_folder):
            boxpath = os.path.join(remote_folder, root.lstrip(local_folder))
            localfns = ["%s/%s" % (root, f) for f in filenames]
            self.uploads(localfns, boxpath, filenames)

    def upload(self, localfn, remote_folder, remotefn=None):
        """Upload a single file to remote path"""
        remotefn = localfn if remotefn is None else remotefn
        self.uploads([localfn, ], remote_folder, [remotefn, ])

    def uploads(self, localfns, remote_folder, remotefns=[]):
        """Upload multiple files to remote path"""
        root = self.get_folder(remote_folder)
        currentitems = {}
        for item in root.get_items(1000):
            currentitems[item.name] = item
        remotefns = localfns if len(remotefns) == 0 else remotefns
        for localfn, remotefn in tqdm(zip(localfns, remotefns),
                                      desc=remote_folder,
                                      disable=(not sys.stdout.isatty())):
            if remotefn in currentitems:
                continue
            root.upload(localfn, remotefn if remotefn is not None else localfn)
