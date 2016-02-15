from servers.serverbase.Exceptions import RemoteException
from JumpScale import j

descr = """
Check on average cpu
"""

organization = "jumpscale"
author = "deboeckj@codescalers.com"
category = "monitor.healthcheck"
license = "bsd"
version = "1.0"
period = 15*60  # always in sec
timeout = period * 0.2
startatboot = True
order = 1
enable = True
async = True
log = True
queue ='process'



def action():
    osis = j.core.osis.client
    gid = j.application.whoAmI.gid
    nid = j.application.whoAmI.nid

    try:
       oldest = osis.search('system', 'stats', 
            'select value from "%s_%s_cpu.num_ctx_switches.gauge" where time > now() - 1h limit 1' % 
            (gid, nid))

       newest = osis.search('system', 'stats', 
            'select value from "%s_%s_cpu.num_ctx_switches.gauge" where time > now() - 1h order by time desc limit 1' % 
            (gid, nid))
    except RemoteException as e:
        return [{'category':'CPU', 'state':'ERROR', 'message':'influxdb halted cannot access data'}]
         
    res=list()

    try:
        newvalue = newest['raw']['series'][0]['values'][0][1]
        oldestvalue = oldest['raw']['series'][0]['values'][0][1]
    except (KeyError,IndexError):
        return [{'category':'CPU', 'state':'WARNING', 'message':'Not enough data collected'}]

    avgctx = (newvalue - oldestvalue) / 3600.
    level = None
    result = dict()
    result['state'] = 'OK'
    result['message'] = 'CPU contextswitch value is: %.2f/s' % avgctx
    result['category'] = 'CPU'
    if avgctx > 100000:
        level = 1
        result ['state'] = 'ERROR'

    elif avgctx > 600000:
        level = 2
        result ['state'] = 'WARNING'

    if level:
        msg = 'CPU contextswitch is to high current value: %.2f/s' % avgctx
        eco = j.errorconditionhandler.getErrorConditionObject(msg=msg, category='monitoring', level=level, type='OPERATIONS')
        eco.nid = nid
        eco.gid = gid
        eco.process()
    
    res.append(result)
    return res


if __name__ == '__main__':
    j.core.osis.client = j.clients.osis.getByInstance('main')
    print(action())
