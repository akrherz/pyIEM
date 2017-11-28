"""IEM Tracker Related Stuff

"""
import smtplib
from email.mime.text import MIMEText

import pytz
from pyiem.util import get_dbconn


class TrackerEngine(object):
    """A processing engine of tracking offline/online events"""

    def __init__(self, icursor, pcursor, maxactions=0):
        """Constructor of TrackerEngine object

        We need to be provided with psycopg2 cursors to both the `iem` database
        and the `portfolio` database as we have business logic in both places

        Args:
          icursor (cursor): psycopg2 cursor to the iem database
          pcursor (cursor): psycopg2 cursor to the portfolio database
          maxactions (int, optional): threshold for now many email actions we
            allow before we don't wish to spam our users.  0 implies no limit

        """
        self.icursor = icursor
        self.pcursor = pcursor
        self.maxactions = maxactions
        self.action_count = 0
        self.emails = {}

    def send_emails(self, really_send=True):
        """Send out those SPAM emails!"""
        # Don't do anything if we have exceeded maxoffline
        if self.action_count >= self.maxactions and self.maxactions > 0:
            return
        if not really_send:
            return
        s = smtplib.SMTP()
        s.connect()
        for email in self.emails:
            msg = MIMEText(self.emails[email]['body'])
            msg['From'] = "akrherz@iastate.edu"
            msg['Subject'] = self.emails[email]['subject']
            s.sendmail(msg['From'], email, msg.as_string())
        s.close()

    def offline_logic(self, sid, ob, pnetwork, nt):
        """offline logic

        Args:
          sid (str): site identifier
          ob (dict): observation dictionary
          pnetwork (str): Portfolio name of this network
          nt (dict): provider of station metadata

        """
        # Get a listing of OPEN tickets
        open_tickets = ""
        self.pcursor.execute("""SELECT id, entered, subject from
        tt_base WHERE portfolio = %s and s_mid = %s and status != 'CLOSED'
        ORDER by id DESC""", (pnetwork, sid))
        for row in self.pcursor:
            open_tickets += (" %-6s %16s     %s\n"
                             "") % (row[0], row[1].strftime("%Y-%m-%d %I %p"),
                                    row[2])
        # Get a listing of past 4 closed tickets
        closed_tickets = ""
        self.pcursor.execute("""SELECT id, entered, subject from
        tt_base WHERE portfolio = %s and s_mid = %s and status = 'CLOSED'
        ORDER by id DESC LIMIT 5""", (pnetwork, sid))
        for row in self.pcursor:
            closed_tickets += (" %-6s %16s     %s\n"
                               "") % (row[0],
                                      row[1].strftime("%Y-%m-%d %I %p"),
                                      row[2])
        if closed_tickets == "":
            closed_tickets = " --None-- "
        if open_tickets == "":
            open_tickets = " --None-- "
        # Create an entry in tt_base
        self.pcursor.execute("""INSERT into tt_base (portfolio, s_mid, subject,
        status, author) VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                             (pnetwork, sid, 'Site Offline', 'OPEN',
                              'mesonet'))
        trackerid = self.pcursor.fetchone()[0]
        # Create a tt_log entry
        lts = ob['valid'].astimezone(pytz.timezone(nt.sts[sid]['tzname']))
        msg = "Site Offline since %s" % (lts.strftime("%d %b %Y %H:%M %Z"), )
        self.pcursor.execute("""INSERT into tt_log (portfolio, s_mid, author,
        status_c, comments, tt_id) VALUES (%s, %s, %s, %s, %s, %s)
        """, (pnetwork, sid, 'mesonet', 'OKAY', msg, trackerid))

        # Update iemaccess
        self.icursor.execute("""INSERT into offline(station, network,
        valid, trackerid) VALUES (%s, %s, %s, %s)
        """, (sid, nt.sts[sid]['network'], ob['valid'], trackerid))

        mformat = """
----------------------
| IEM TRACKER REPORT |  New Ticket Generated: # %s
================================================================
 ID                :  %s [IEM Network: %s]
 Station Name      :  %s
 Status Change     :  [OFFLINE] Site is NOT reporting to the IEM
 Last Observation  :  %s

 Other Currently 'Open' Tickets for this Site:
 #      OPENED_ON            TICKET TITLE
%s

 Most Recently 'Closed' Trouble Tickets for this Site:
 #      CLOSED_ON            TICKET TITLE
%s
================================================================
"""
        mailstr = mformat % (trackerid, sid, nt.sts[sid]['network'],
                             nt.sts[sid]['name'],
                             lts.strftime("%d %b %Y %I:%M %p %Z"),
                             open_tickets, closed_tickets)
        # Get contacts for site
        self.pcursor.execute("""SELECT distinct email from
        iem_site_contacts WHERE s_mid = %s and email is not NULL
        """, (sid, ))
        for row in self.pcursor:
            email = row[0].lower()
            if email not in self.emails:
                subject = ('[IEM] %s Offline'
                           '') % (nt.sts[sid]['name'], )
                self.emails[email] = {'subject': subject,
                                      'body': mailstr}
            else:
                subject = '[IEM] Multiple Sites'
                self.emails[email]['subject'] = subject
                self.emails[email]['body'] += "\n=========\n"
                self.emails[email]['body'] += mailstr

    def online_logic(self, sid, offline, ob, pnetwork, nt):
        """online logic

        Args:
          sid (str): site identifier
          offline (dict): dictionary of offline metadata
          ob (dict): observation dictionary
          pnetwork (str): Portfolio name of this network
          nt (dict): provider of station metadata

        """
        trackerid = offline[sid]['trackerid']
        # Create Log Entry
        cmt = ("Site Back Online at: %s"
               "") % (ob['valid'].strftime("%Y-%m-%d %H:%M:%S"), )
        self.pcursor.execute("""INSERT into tt_log
            (portfolio, s_mid, author, status_c, comments, tt_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (pnetwork, sid, 'mesonet', 'CLOSED', cmt,
              trackerid))
        # Update tt_base
        self.pcursor.execute("""UPDATE tt_base SET
        last = now(), status = 'CLOSED' WHERE id = %s
        """, (trackerid, ))
        # Update iemaccess
        self.icursor.execute("""DELETE from offline where
        station = %s and network = %s""", (sid,
                                           nt.sts[sid]['network']))
        mformat = """
   ---------------------------------
   |  *** IEM TRACKER REPORT ***   |
------------------------------------------------------------
ID                :  %s [IEM Network: %s]
Station Name      :  %s
Status Change     :  [ONLINE] Site is reporting to the IEM
Trouble Ticket#   :  %s

Last Observation  :  %s
Outage Duration   :  %s

IEM Tracker Action:  This trouble ticket has been marked
                     CLOSED pending any further information.
------------------------------------------------------------

  * If you have any information pertaining to this outage,
    please directly respond to this email.
  * Questions about this alert?  Email:  akrherz@iastate.edu
  * Thanks!!!
"""
        ltz = pytz.timezone(nt.sts[sid]['tzname'])
        lts = ob['valid'].astimezone(ltz)
        delta = (ob['valid'] - offline[sid]['valid'])
        days = delta.days
        hours = delta.seconds / 3600.
        minutes = (delta.seconds % 3600) / 60.
        duration = "%.0f days %.0f hours %.0f minutes" % (days,
                                                          hours,
                                                          minutes)
        mailstr = mformat % (sid, nt.sts[sid]['network'],
                             nt.sts[sid]['name'], trackerid,
                             lts.strftime("%d %b %Y %I:%M %p %Z"),
                             duration)
        # Get contacts for site
        self.pcursor.execute("""SELECT distinct email from
        iem_site_contacts WHERE s_mid = %s and email is not NULL
        """, (sid, ))
        for row in self.pcursor:
            email = row[0].lower()
            if email not in self.emails:
                subject = ('[IEM] %s Online'
                           '') % (nt.sts[sid]['name'], )
                self.emails[email] = {'subject': subject,
                                      'body': mailstr}
            else:
                subject = '[IEM] Multiple Sites'
                self.emails[email]['subject'] = subject
                self.emails[email]['body'] += "\n=========\n"
                self.emails[email]['body'] += mailstr

    def process_network(self, obs, pnetwork, nt, threshold):
        """Process a list of dicts representing the network's observations

        Args:
          obs (list): list of dicts representing the network obs
          pnetwork (str): the identifier of this network used in Portfolio DB
          nt (NetworkTable): dictionary provider of station metadata
          threshold (datetime): datetime instance with tzinfo set represeting
            the minimum time a site is considered to be 'online' within

        """
        network = nt.sts[list(nt.sts.keys())[0]]['network']
        self.icursor.execute("""SELECT station, trackerid, valid from offline
            WHERE network = %s""", (network,))
        offline = {}
        for row in self.icursor:
            offline[row[0]] = {'trackerid': row[1], 'valid': row[2]}

        for sid in obs:
            ob = obs[sid]
            if ob['valid'] > threshold:
                # print '%s is online, offlinekeys: %s' % (sid,
                #                                         str(offline.keys()))
                if sid in offline:
                    self.action_count += 1
                    self.online_logic(sid, offline, ob, pnetwork, nt)
                continue
            elif sid in offline:
                # NOOP
                # print '%s is offline and known offline' % (sid, )
                continue
            # We must act!
            # print '%s is offline' % (sid, )
            self.action_count += 1
            self.offline_logic(sid, ob, pnetwork, nt)


def loadqc(cursor=None):
    """ Load the current IEM Tracker QC'd variables

    Args:
      cursor (cursor,optional): Optionally provided database cursor
    """
    qdict = {}
    if cursor is None:
        portfolio = get_dbconn('portfolio', user='nobody')
        cursor = portfolio.cursor()

    cursor.execute("""
    select s_mid, sensor, status from tt_base WHERE sensor is not null
    and status != 'CLOSED' and s_mid is not null
    """)
    for row in cursor:
        sid = row[0]
        if row[0] not in qdict:
            qdict[sid] = {}
        for vname in row[1].split(","):
            qdict[sid][vname.strip()] = True
    return qdict
