'''
 QC interface
'''
import psycopg2

def loadqc():
    ''' Load the current IEM Tracker QC'd variables '''
    qdict = {}
    portfolio = psycopg2.connect(database='portfolio', host='iemdb', 
                                 user='nobody')
    pcursor = portfolio.cursor()
    
    pcursor.execute("""
    select s_mid, sensor, status from tt_base WHERE sensor is not null 
    and status != 'CLOSED' and s_mid is not null
    """)
    for row in pcursor:
        sid = row[0]
        if not qdict.has_key(row[0]):
            qdict[sid] = {}
        for vname in row[1].split(","):
            qdict[sid][vname.strip()] = True
    pcursor.close()
    portfolio.close()
    return qdict