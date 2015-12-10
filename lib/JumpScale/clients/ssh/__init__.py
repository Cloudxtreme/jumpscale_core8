from .SSHClient import SSHClient
cache = {}


def get(addr, port=22, login="root", passwd=None, stdout=True, forward_agent=True, allow_agent=True, look_for_keys=True):
    key = "%s_%s_%s" % (addr, port, login)
    if key not in cache:
        cache[key] = SSHClient(addr, port, login, passwd, stdout=stdout,
                               forward_agent=forward_agent, allow_agent=allow_agent, look_for_keys=look_for_keys)
    return cache[key]


def removeFromCache(client):
    key = "%s_%s_%s" % (client.addr, client.port, client.login)
    client.close()
    if key in cache:
        cache.pop(key)


def close():
    for key, client in cache.iteritems():
        client.close()
