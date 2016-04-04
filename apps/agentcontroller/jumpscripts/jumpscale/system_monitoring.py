from JumpScale import j
import re
import sys

descr = """
gather statistics about system
"""

organization = "jumpscale"
author = "kristof@incubaid.com"
license = "bsd"
version = "1.0"
category = "monitoring.processes"
period = 60 #always in sec
timeout = period * 0.2
enable=True
async=True
queue='process'
log=False

roles = []
def action(redisconnection):
    import psutil
    import os
    hostname =j.sal.nettools.getHostname()

    if not redisconnection or not ':' in redisconnection:
        print("Please specifiy a redis connection in the form of ipaddr:port")
        return
    addr = redisconnection.split(':')[0]
    port = int(redisconnection.split(':')[1])
    redis = j.clients.redis.get(addr, port)

    aggregator = j.tools.aggregator.getClient(redis,  hostname)
    tags = j.data.tags.getTagString(tags={
        'gid': str(j.application.whoAmI.gid),
        'nid': str(j.application.whoAmI.nid),
        })


    results={}
    val=psutil.cpu_percent()
    results["cpu.percent"]=val
    cput= psutil.cpu_times()
    for key in cput._fields:
        val=cput.__getattribute__(key)
        results["cpu.time.%s"%(key)]=val

    counter=psutil.net_io_counters(False)
    bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout=counter
    results["network.kbytes.recv"]=round(bytes_recv/1024.0,0)
    results["network.kbytes.sent"]=round(bytes_sent/1024.0,0)
    results["network.packets.recv"]=packets_recv
    results["network.packets.send"]=packets_sent
    results["network.error.in"]=errin
    results["network.error.out"]=errout
    results["network.drop.in"]=dropin
    results["network.drop.out"]=dropout

    avg1min, avg5min, avg15min = os.getloadavg()
    results["process.load.avg1min"] = avg1min
    results["process.load.avg5min"] = avg5min
    results["processes.load.avg15min"] = avg15min

    memory = psutil.virtual_memory()
    results["memory.virtual.used"]=round((memory.used - memory.cached)/1024.0/1024.0,2)
    results["memory.virtual.cached"]=round(memory.cached/1024.0/1024.0,2)
    results["memory.virtual.free"]=round(memory.total/1024.0/1024.0,2) - results['memory.used'] - results['memory.cached']
    results["memory.virtual.percent"]=memory.percent

    vm= psutil.swap_memory()
    results["memory.swap.free"]=round(vm.__getattribute__("free")/1024.0/1024.0,2)
    results["memory.swap.used"]=round(vm.__getattribute__("used")/1024.0/1024.0,2)
    results["memory.swap.percent"]=vm.__getattribute__("percent")


    stat = j.sal.fs.fileGetContents('/proc/stat')
    stats = dict()
    for line in stat.splitlines():
        _, key, value = re.split("^(\w+)\s", line)
        stats[key] = value

    num_ctx_switches = int(stats['ctxt'])
    results["cpu.num_ctx_switches"]=num_ctx_switches


    for key, value in results.items():
        aggregator.measure(tags=tags, key=key, value=value, measurement="")

    return results

if __name__ == '__main__':
  if len(sys.argv) == 2:
    results = action(sys.argv[1])
    import yaml
    print (yaml.dump(results))
  else:
      print("Please specifiy a redis connection in the form of ipaddr:port")


