from JumpScale import j
import sys

descr = """
gather statistics about disks
"""

organization = "jumpscale"
author = "kristof@incubaid.com"
license = "bsd"
version = "1.0"
category = "disk.monitoring"
period = 300 #always in sec
timeout = period * 0.2
order = 1
enable=True
async=True
queue='process'
log=False

roles = []

def action(redisconnection):
    import psutil

    dcl = j.data.models.system.Disk
    if not redisconnection or not ':' in redisconnection:
        print("Please specifiy a redis connection in the form of ipaddr:port")
        return
    addr = redisconnection.split(':')[0]
    port = int(redisconnection.split(':')[1])
    redis_client = j.clients.redis.get(addr, port)
    hostname =j.sal.nettools.getHostname()
    try:
        aggregator = j.tools.aggregator.getClient(redis_client,  hostname)
    except:
        print("No redis instance was found on this connection")
        return
    tags = j.data.tags.getTagString(tags={
        'gid': str(j.application.whoAmI.gid),
        'nid': str(j.application.whoAmI.nid),
        })

    disks = j.sal.disklayout.getDisks(detailed=True)


    #disk counters
    counters=psutil.disk_io_counters(True)

    
    for disk in disks:

        results = {'time.read': 0, 'time.write': 0, 'count.read': 0, 'count.write': 0,
                   'kbytes.read': 0, 'kbytes.write': 0,
                   'space.free_mb': 0, 'space.used.mb': 0, 'space.percent': 0}
        path = disk['NAME'].replace("/dev/","")
        print (path)

        odisk = dcl()
        old = dcl.find({'path': disk['NAME']})
        odisk.nid = j.application.whoAmI.nid
        odisk.gid = j.application.whoAmI.gid

        if path in counters.keys():
            counter=counters[path]
            read_count, write_count, read_bytes, write_bytes, read_time, write_time, read_merged_count, write_merged_count, busy_time=counter
            results['time.read'] = read_time
            results['time.write'] = write_time
            results['count.read'] = read_count
            results['count.write'] = write_count

            read_bytes=int(round(read_bytes/1024,0))
            write_bytes=int(round(write_bytes/1024,0))
            results['kbytes.read'] = read_bytes
            results['kbytes.write'] = write_bytes

            if old:
                old_disk = old[0].to_dict()
            for key,value in disk.items():
                key = key.lower()
                if key == "name":
                    key = "path"
                elif key == "fstype":
                    key = "fs"
                elif key == "uuid":
                    continue
                elif key == "type":
                    value = [value]
                elif key == "size":
                    value = int(value)
                odisk[key] = value
                if old:
                    same = old_disk[key] == value

                    if not same:
                        print("Disk %s's %s changed from %s to %s" % (path,key,old_disk[key],value))
                        old[0].delete()
            if not old:
                odisk.save()

        for key, value in results.items():
            aggregator.measure(tags=tags, key="disk.%s.%s" % (path,key), value=value, measurement="")

    return results

if __name__ == '__main__':
    if len(sys.argv) == 2:
        results = action(sys.argv[1])
        print(results)
    else:
        print("Please specifiy a redis connection in the form of ipaddr:port")
