
from JumpScale import j


class GCC():

    def __init__(self):
    
    def get(self,nodes):
        """
        define which nodes to init,
        format="localhost,ovh4,anode:2222,192.168.6.5:23"
        this will be remembered in local redis for further usage (uses the j.tools.develop... functionality)

        make sure nodes have your SSH key authorized before using there
        can do this with
        j.tools.gcc.authorizeNode(addr,passwd,keyname,login="root",port=22)

        """
        return GCC_Mgmt(nodes)

    def authorizeNode(self,addr,passwd,keyname,login="root",port=22):
        j.tools.executor.getSSHBased(addr=addr, port=port, login=login, passwd=passwd, debug=False, checkok=True, allow_agent=True, look_for_keys=True, pushkey=keyname)



class GCC_Mgmt():

    def __init__(self,nodes):
        self.nodes=j.tools.develop.init(nodes=nodes)

    def install(self):
        """
        """
        #@todo use cuisine which is on each node to do all required actions


    def healthcheck(self):
        """
        """
        #@todo implement some healthchecks done over agentcontrollers
        #- check diskpace
        #- check cpu
        #- check that 3 are there
        #- check that weave network is intact
        #- check sycnthing is up to date
        #- port checks ...

    def nameserver(self,login,passwd):
        """
        credentials to etcd to allow management of DNS records
        """
        return GCC_Nameserver(self,login,passwd)

    def aydostor(self,login,passwd):
        return 

class GCC_Nameserver():
    """
    define easy to use interface on top of nameserver management
    """
    def __init__(self,manager):
        self.manager=manager

    def ns_addHost(addr,dnsinfo....): #to be further defined

        #@todo use https over caddy to speak to etcd to configure skydns, maybe clients do already exist?

class GCC_aydostor():
    """
    define easy to use interface on top of aydostor (use aydostor client, needs to be separate client in js8)
    """
    def __init__(self,manager):
        self.manager=manager

    def ns_addHost(addr,dnsinfo....): #to be further defined

        #@todo use https over caddy to speak to etcd to configure skydns


