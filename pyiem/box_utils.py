"""A helper to work with Box API"""
import os
import logging

from six import string_types
from boxsdk import Client, OAuth2

from pyiem.util import get_properties, set_property
LOG = logging.getLogger()


def _store_tokens(access_token, refresh_token):
    """Callback if we needed to have our tokens refreshed"""
    set_property('boxclient.access_token', access_token)
    set_property('boxclient.refresh_token', refresh_token)


def sendfiles2box(remotepath, filenames, remotefilenames=None,
                  overwrite=False):
    """Send a file(s) to Box.

    Args:
      remotepath (str): remote directory to send file(s) to
      filenames (str or list): local files to send to box
      remotefilenames (str or list, optional): same size as filenames and
        optional as to if they should have different names or not
      overwrite (bool): should this overwrite existing files, default `False`

    Returns:
      list of ids of the uploaded content
    """
    if isinstance(filenames, string_types):
        filenames = [filenames, ]
    if isinstance(remotefilenames, string_types):
        remotefilenames = [remotefilenames, ]
    if remotefilenames is None:
        remotefilenames = [os.path.basename(f) for f in filenames]
    iemprops = get_properties()
    oauth = OAuth2(
        client_id=iemprops['boxclient.client_id'],
        client_secret=iemprops['boxclient.client_secret'],
        access_token=iemprops['boxclient.access_token'],
        refresh_token=iemprops['boxclient.refresh_token'],
        store_tokens=_store_tokens
    )
    client = Client(oauth)
    folder_id = 0
    for token in remotepath.split("/"):
        if token.strip() == '':
            continue
        offset = 0
        found = False
        while not found:
            LOG.debug("folder(%s).get_items(offset=%s)", folder_id, offset)
            items = client.folder(
                folder_id=folder_id).get_items(limit=100, offset=offset)
            for item in items:
                if (item.type == 'folder' and
                        item.name.lower() == token.lower()):
                    folder_id = item.id
                    found = True
                    break
            if len(items) != 100:
                break
            offset += 100
        if not found:
            LOG.debug("Creating folder %s inside of %s", token, folder_id)
            item = client.folder(folder_id=folder_id).create_subfolder(token)
            folder_id = item.id
    LOG.debug("Now we upload to folder_id: %s", folder_id)
    res = []
    for localfn, remotefn in zip(filenames, remotefilenames):
        LOG.debug("uploading %s", localfn)
        try:
            item = client.folder(folder_id=folder_id).upload(localfn, remotefn)
            res.append(item.id)
        except Exception as exp:
            if overwrite and hasattr(exp, 'context_info'):
                _fileid = exp.context_info['conflicts']['id']
                LOG.info("overwriting %s fid: %s", remotefn, _fileid)
                try:
                    item = client.file(_fileid).update_contents(localfn)
                    res.append(_fileid)
                    continue
                except Exception as exp2:
                    LOG.debug(
                        "Upload_Contents of %s resulted in exception: %s",
                        localfn, exp2
                    )
                    continue
            LOG.debug(
                "Upload of %s resulted in exception: %s", localfn, exp
            )
            res.append(None)

    return res


if __name__ == '__main__':
    LOG.setLevel(logging.DEBUG)
    LOG.addHandler(logging.StreamHandler())
    sendfiles2box("/bah/bah/bah", "/tmp/z_01my18.dbf", overwrite=True)
