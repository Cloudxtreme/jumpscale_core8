from JumpScale import j
import sys

descr = """
gather network statistics
"""

organization = "jumpscale"
author = "deboeckj@codescalers.com"
license = "bsd"
version = "1.0"
category = "info.gather.nic"
period = 60 #always in sec
timeout = period * 0.2
enable=True
async=True
queue='process'
roles = []
log=False

def action(redisconnection):
    import psutil
    import sys
    if not redisconnection or not ':' in redisconnection:
        print("Please specifiy a redis connection in the form of ipaddr:port")
        return
    addr = redisconnection.split(':')[0]
    port = int(redisconnection.split(':')[1])
    redis_client = j.clients.redis.get(addr, port)
    hostname =j.sal.nettools.getHostname()
    aggregator = j.tools.aggregator.getClient(redis_client,  hostname)
    tags = j.data.tags.getTagString(tags={
        'gid': str(j.application.whoAmI.gid),
        'nid': str(j.application.whoAmI.nid),
        })
    
    
    counters=psutil.net_io_counters(True)
    pattern = None
    if j.application.config.exists('gridmonitoring.nic.pattern'):
        pattern = j.application.config.getStr('gridmonitoring.nic.pattern')

    for nic, stat in counters.items():
        if pattern and j.codetools.regex.match(pattern,nic) == False:
            continue
        if j.sal.nettools.getNicType(nic) == 'VIRTUAL' and not 'pub' in nic:
            continue
        result = dict()
        bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout = stat
        result['kbytes.sent'] = int(round(bytes_sent/1024.0,0))
        result['kbytes.recv'] = int(round(bytes_recv/1024.0,0))
        result['packets.sent'] = packets_sent
        result['packets.recv'] = packets_recv
        result['error.in'] = errin
        result['error.out'] = errout
        result['drop.in'] = dropin
        result['drop.out'] = dropout

        for key, value in result.items():
            aggregator.measure(tags=tags, key="network.%s.%s" % (nic,key), value=value, measurement="")

    return result
if __name__ == '__main__':
  if len(sys.argv) == 2:
      results = action(sys.argv[1])
      print(results)

  else:
      print("Please specifiy a redis connection in the form of ipaddr:port")
