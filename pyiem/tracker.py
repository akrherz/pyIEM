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
    and status != 'CLOSED' 
    and portfolio in ('kccisnet','kelosnet','kimtsnet', 'iaawos', 'iarwis')
    """)
    for row in pcursor:
        if not qdict.has_key(row[0]):
            qdict[row[0]] = {}
        if row[1].find("precip") > -1:
            qdict[row[0]]['precip'] = True
        if row[1].find("tmpf") > -1:
            qdict[row[0]]['tmpf'] = True
        if row[1].find("drct") > -1 or row[1].find("sknt") > -1 or row[1].find("wind") > -1:
            qdict[row[0]]['wind'] = True    
    pcursor.close()
    portfolio.close()
    return qdict