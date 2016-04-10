from JumpScale import j
import click

class CockpitArgs:
    """Argument required to deploy a G8Cockpit"""
    def __init__(self, asker):
        super(CockpitArgs, self).__init__()

        # Asker is the interface used to ask data to user
        self.asker = asker

        # used by some properties
        self.ovc_client = None

        # Next properties are the actual arguments required by the cockpit
        self._repo_url = None
        self._ovc_url = None
        self._ovc_login = None
        self._ovc_password = None
        self._ovc_account = None
        self._ovc_vdc = None
        self._ovc_location = None
        self._dns_login = None
        self._dns_password = None
        self._domain = None
        self._sshkey = None
        self._portal_password = None
        self._expose_ssh = None
        self._bot_token = None
        self._gid = None

    @property
    def repo_url(self):
        if self._repo_url is None:
            self._repo_url = self.asker.ask_repo_url()
        return self._repo_url

    @property
    def ovc_url(self):
        if self._ovc_url is None:
            self._ovc_url = self.asker.ask_ovc_url()
        return self._ovc_url

    @property
    def ovc_login(self):
        if self._ovc_login is None:
            self._ovc_login = self.asker.ask_ovc_login()
        return self._ovc_login

    @property
    def ovc_password(self):
        if self._ovc_password is None:
            self._ovc_password = self.asker.ask_ovc_password()
        return self._ovc_password

    @property
    def ovc_account(self):
        if self._ovc_account is None:
            self._ovc_account = self.asker.ask_ovc_account(self.ovc_client)
        return self._ovc_account

    @property
    def ovc_vdc(self):
        if self._ovc_vdc is None:
            self._ovc_vdc = self.asker.ask_ovc_vdc()
        return self._ovc_vdc

    @property
    def ovc_location(self):
        if self._ovc_location is None:
            self._ovc_location = self.asker.ask_ovc_location(ovc_client=self.ovc_client, account_name=self.ovc_account, vdc_name=self.ovc_vdc)
        return self._ovc_location

    @property
    def dns_login(self):
        if self._dns_login is None:
            self._dns_login = self.asker.ask_dns_login()
        return self._dns_login

    @property
    def dns_password(self):
        if self._dns_password is None:
            self._dns_password = self.asker.ask_dns_password()
        return self._dns_password

    @property
    def domain(self):
        if self._domain is None:
            self._domain = self.asker.ask_domain()
        return self._domain

    @property
    def sshkey(self):
        if self._sshkey is None:
            self._sshkey = self.asker.ask_ssh_key()
        return self._sshkey

    @property
    def portal_password(self):
        if self._portal_password is None:
            self._portal_password = self.asker.ask_portal_password()
        return self._portal_password

    @property
    def expose_ssh(self):
        if self._expose_ssh is None:
            self._expose_ssh = self.asker.ask_expose_ssh()
        return self._expose_ssh

    @property
    def bot_token(self):
        if self._bot_token is None:
            self._bot_token =self.asker.ask_bot_token()
        return self._bot_token

    @property
    def gid(self):
        if self._gid is None:
            self._gid = self.asker.ask_gid()
        return self._gid


class CockpitDeployer:
    def __init__(self, asker):
        self.logger = j.logger.get('j.clients.cockpit.installer')
        self.args = CockpitArgs(asker)
        self.TEMPLATE_REPO = "https://github.com/0-complexity/g8cockpit.git"
        self.type = None



    def printInfo(self, msg):
        self.logger.info(msg)

    def exit(err, code=1):
        if isinstance(err, BaseException):
            raise err
        else:
            raise RuntimeError(err)

    def _get_vdc(self):
        try:
            ovc_client = j.clients.openvcloud.get(self.args.ovc_url, self.args.ovc_login, self.args.ovc_password)
        except Exception as e:
            self.logger.error("Error while trying to connect to G8 (%s). Login: %s" % (self.args.ovc_url, self.args.ovc_login))
            self.exit(e)

        self.args.ovc_client = ovc_client
        account = ovc_client.account_get(self.args.ovc_account)
        self.logger.info("Virtual Data Center Selection")
        try:
            vdc = account.space_get(self.args.ovc_vdc, self.args.ovc_location, create=True)
        except Exception as e:
            self.logger.error("Error while trying to have access to VDC %s with account: %s" % (self.args.ovc_vdc, self.args.ovc_account))
            self.exit(e)
        return vdc

    def _get_dns_client(self):
        client = None
        url = 'https://dns%d.aydo.com/etcd'
        for i in range(1, 4):
            try:
                baseurl = url % i
                client = j.clients.skydns.get(baseurl, username=self.args.dns_login, password=self.args.dns_password)
                cfg = client.getConfig()
                if 'error' in cfg:
                    self.logger.info("Can't connect to DNS: %s" % cfg['error'])
                    client = None
                    break
                return client
            except Exception as e:
                client = None
                continue
        if not client:
            self.logger.info("Can't connect to DNS")
            self.exit("Can't connect to DNS")

    def _register_domain(self, vdc_adress):
        dns_client = self._get_dns_client()

        def validateDNS(dns_name):
            self.logger.info("Test if domain name is available (%s)" % dns_name)
            exists, host = dns_client.exists(dns_name)
            if exists and host != vdc_adress:
                self.logger.info("%s is not available, please choose another name" % dns_name)
                return False
            else:
                self.logger.info("Domain name is available (%s)" % dns_name)
                return True

        while (validateDNS(self.args.domain) is False):
            self.args._domain = None

        if not self.args.domain.endswith('.barcelona.aydo.com'): # TODO chagne DNS
            self.args._domain = '%s.barcelona.aydo.com' % self.args.domain
        dns_client.setRecordA(self.args._domain, vdc_adress, ttl=120) # TODO, set real TTL
        return self.args._domain

    def _caddy_cfg(self, cuisine, hostname):
        caddy_main_cfg = """
        #$hostname
        :80
        gzip

        log /optvar/cfg/caddy/log/portal.access.log
        errors {
        log /optvar//cfg/caddy/log/portal.errors.log
        }

        import $varDir/cfg/caddy/proxies/*
        """
        caddy_proxy_cfg = """
        proxy /0/0/hubble 127.0.0.1:8966 {
          without /0/0/hubble
          websocket
        }

        proxy /controller 127.0.0.1:8966 {
           without /controller
           websocket
        }

        proxy /$url 127.0.0.1:4200 {
           without /$url
        }

        proxy /grafana 127.0.0.1:3000 {
            without /grafana
        }
        """

        caddy_portal_cfg = "proxy / 127.0.0.1:82"
        url = j.data.idgenerator.generateXCharID(15)
        caddy_main_cfg = caddy_main_cfg.replace("$hostname", hostname)
        caddy_main_cfg = cuisine.core.args_replace(caddy_main_cfg)
        caddy_proxy_cfg = caddy_proxy_cfg.replace("$url", url)
        cuisine.core.dir_ensure('$varDir/cfg/caddy/log')
        cuisine.core.dir_ensure('$varDir/cfg/caddy/proxies/')
        cuisine.core.file_write('$varDir/cfg/caddy/caddyfile', caddy_main_cfg)
        cuisine.core.file_write('$varDir/cfg/caddy/proxies/01_proxies', caddy_proxy_cfg)
        cuisine.core.file_write('$varDir/cfg/caddy/proxies/99_portal', caddy_portal_cfg)
        return url

    def deploy(self):
        j.actions.resetAll() #@todo needs to be improved, is too harsh
        
        j.do.loadSSHAgent(createkeys=True)
        local_pubkey = j.do.listSSHKeyFromAgent()[0]
        cuisine = j.tools.cuisine.local

        # connection to Gener8 + get vdc client
        self.logger.info('Test connectivity to G8')
        vdc_cockpit = self._get_vdc()
        self.logger.info('Connection to G8 valid.')

        # self.logger.info('Register domain for new cockpit on dns server')
        dns_name = self._register_domain(vdc_cockpit.model['publicipaddress'])

        key_pub = j.do.getSSHKeyFromAgentPub(self.args.sshkey, die=False)
        if key_pub is None:
            key_pub = self.args.sshkey

        #self.logger.info('cloning template repo (%s)' % self.TEMPLATE_REPO)
        _, _, _, _, template_repo_path, _ = j.do.getGitRepoArgs(self.TEMPLATE_REPO)
        #template_repo_path = j.do.pullGitRepo(url=self.TEMPLATE_REPO, branch='master', executor=cuisine.executor)
        #self.logger.info('cloned in %s' % template_repo_path)

        self.logger.info("creation of cockpit repo")
        _, _, _, _, cockpit_repo_path, cockpit_repo_remote = j.do.getGitRepoArgs(self.args.repo_url, ssh=True)
        if j.sal.fs.exists(cockpit_repo_path):
            j.sal.fs.removeDirTree(cockpit_repo_path)
        j.sal.fs.createDir(cockpit_repo_path)
        cuisine.core.run('git init %s' % cockpit_repo_path)
        cuisine.core.run('cd %s; git remote add origin %s' % (cockpit_repo_path, cockpit_repo_remote))

        src = j.sal.fs.joinPaths(template_repo_path, 'ays_repo')
        dest = j.sal.fs.joinPaths(cockpit_repo_path, 'ays_repo')
        if not j.sal.fs.exists(src):
            self.exit("%s doesn't exist. template repo is propably not valid")
        j.sal.fs.copyDirTree(src, dest)

        git_cl = j.clients.git.get(cockpit_repo_path)
        git_cl.commit('init commit')
        self.logger.info('created at %s' % cockpit_repo_path)

        self.logger.info("Start creation of the cockpit VM\nIt can take some time, please be patient.")
        if 'cockpit' in vdc_cockpit.machines:
            machine = vdc_cockpit.machines['cockpit']
        else:
            machine = vdc_cockpit.machine_create('cockpit', memsize=2, disksize=50, image='Ubuntu 15.10')
        ssh_exec = machine.get_ssh_connection()

        exists_pf = [pf['publicPort']for pf in machine.portforwardings]
        if '80' not in exists_pf:
            machine.create_portforwarding(80, 80)
        if '443' not in exists_pf:
            machine.create_portforwarding(443, 443)
        if '18384' not in exists_pf:
            machine.create_portforwarding(18384, 18384)  # temporary create portforwardings for syncthing

        self.logger.info('Authorize ssh key into VM')
        # authorize ssh key into VM
        ssh_exec.cuisine.ssh.authorize('root', local_pubkey)
        # reconnect as root
        ssh_exec = j.tools.executor.getSSHBased(ssh_exec.addr, ssh_exec.port, 'root')

        self.logger.info("Start installation of cockpit")
        ssh_exec.cuisine.docker.install()
        self.logger.info("installation of Jumpscale")
        ssh_exec.cuisine.installer.jumpscale8()
        self.logger.info("Configure environment")
        ssh_exec.cuisine.bash.environSet('GOPATH', '/optvar/go')
        ssh_exec.cuisine.bash.addPath('/optvar/go/bin')
        ssh_exec.cuisine.bash.addPath('/usr/local/go/bin')
        self.logger.info("Creation of docker container")
        ssh_exec.cuisine.core.run('$binDir/jsdocker pull -i jumpscale/g8cockpit', profile=True)
        container_conn_str = ssh_exec.cuisine.docker.ubuntu(name='g8cockpit', image='jumpscale/g8cockpit', 
           ports="80:80 443:443 18384:18384", volumes="/optvar/data:/optvar/data", 
           pubkey=local_pubkey, aydofs=False)
        
        # erase our own key and put the key from the client instead
        ssh_exec.cuisine.core.file_write('/root/.ssh/authorized_keys', key_pub)
        
        addr, port = container_conn_str.split(":")
        if port not in exists_pf:
            machine.create_portforwarding(port, port) # expose ssh of docker
        container_cuisine = j.tools.cuisine.get("%s:%s" % (ssh_exec.addr, port))
        self.logger.info("Update jumpscale repos in cockpit container")
        repos = [
            'https://github.com/Jumpscale/ays_jumpscale8.git',
            'https://github.com/Jumpscale/jumpscale_core8.git',
            'https://github.com/Jumpscale/jumpscale_portal8.git',
        ]
        for url in repos:
            j.do.pullGitRepo(url=url, executor=container_cuisine.executor)


        self.logger.info("Start configuration of your cockpit")
        self.logger.info("Configuration of influxdb")
        container_cuisine.apps.influxdb.start()

        self.logger.info("Configuration of grafana")
        container_cuisine.apps.grafana.start()
        cfg = container_cuisine.core.file_read('$cfgDir/grafana/grafana.ini')
        cfg = cfg.replace('domain = localhost', 'domain = %s' % dns_name)
        cfg = cfg.replace('root_url = %(protocol)s://%(domain)s:%(http_port)s/', 'root_url = %(protocol)s://%(domain)s:%(http_port)s/grafana')
        container_cuisine.core.file_write('$cfgDir/grafana/grafana.ini', cfg)

        self.logger.info("Configuration of mongodb")
        container_cuisine.apps.mongodb.start()

        self.logger.info("Configuration of g8os controller")
        container_cuisine.apps.controller.start()

        self.logger.info("Configuration of cockpit portal")
        # start, do the linking of minimum portal and set admin passwd
        container_cuisine.portal.start(force=True, passwd=self.args.portal_password)
        # link required cockpit spaces
        container_cuisine.core.dir_ensure('$cfgDir/portals/main/base/')
        container_cuisine.core.file_link("/opt/code/github/jumpscale/jumpscale_portal8/apps/gridportal/base/Cockpit", "$cfgDir/portals/main/base/Cockpit")
        container_cuisine.core.file_link("/opt/code/github/jumpscale/jumpscale_portal8/apps/gridportal/base/AYS", "$cfgDir/portals/main/base/AYS")
        container_cuisine.core.file_link("/opt/code/github/jumpscale/jumpscale_portal8/apps/gridportal/base/system__atyourservice", "$cfgDir/portals/main/base/system__atyourservice")
        # restart portal to load new spaces
        container_cuisine.processmanager.stop('portal')
        container_cuisine.processmanager.start('portal')

        self.logger.info("Configuration of shellinabox")
        if self.args.expose_ssh:
            # TODO authorize local sshkey to auto login
            config = "-s '/:root:root:/:ssh root@localhost'"
            cmd = 'shellinaboxd --disable-ssl --port 4200 %s ' % config
            container_cuisine.processmanager.ensure('shellinabox_cockpit', cmd=cmd)

        self.logger.info("Configuration of caddy proxy")
        shellinbox_url = self._caddy_cfg(container_cuisine, dns_name)
        cmd = '$binDir/caddy -conf $varDir/cfg/caddy/caddyfile -email mail@fake.com -http2=false'
        # if self.args.dev:  # enable stating environment
            # cmd += ' -ca https://acme-staging.api.letsencrypt.org/directory'
        container_cuisine.processmanager.ensure('caddy', cmd)

        self.logger.info("Configuration of AYS robot")
        cmd = "ays bot --token %s" % self.args.bot_token
        container_cuisine.tmux.executeInScreen('aysrobot', 'aysrobot', cmd, wait=0)

        self.logger.info("Generate cockpit config service")
        pwd = j.sal.fs.getcwd()
        j.sal.fs.changeDir(j.sal.fs.joinPaths(cockpit_repo_path, 'ays_repo'))
        j.atyourservice.basepath = j.sal.fs.joinPaths(cockpit_repo_path, 'ays_repo')
        args = {
            'dns': dns_name,
            'node.addr': container_cuisine.executor.addr,
            'ssh.port': int(container_cuisine.executor.port),
            'bot.token': self.args.bot_token,
            'gid': int(self.args.gid),
        }
        r = j.atyourservice.getRecipe('cockpitconfig')
        r.newInstance(args=args)
        # cuisine.core.run('cd %s; git push -f origin master' % cockpit_repo_path, force=True)

        content = "grid.id = %d\nnode.id = 0" % int(self.args.gid)
        container_cuisine.core.file_append(location="$hrdDir/system/system.hrd", content=content)
        
        # j.sal.fs.copyFile("portforwards.py", cockpit_repo_path, createDirIfNeeded=False, overwriteFile=True)
        dest = 'root@%s:%s' % (container_cuisine.executor.addr, cockpit_repo_path)
        container_cuisine.core.dir_ensure(cockpit_repo_path)
        j.do.copyTree(cockpit_repo_path, dest, sshport=container_cuisine.executor.port, ssh=True)

        self.logger.info("\nCockpit deployed")
        self.logger.info("SSH: ssh root@%s -p %s" % (dns_name, container_cuisine.executor.port))
        if self.args.expose_ssh:
            self.logger.info("Shell In A Box: https://%s/%s" % (dns_name, shellinbox_url))
        self.logger.info("Portal: http://%s" % (dns_name))
        
        # erase our own key and write client key instead
        container_cuisine.core.file_write('/root/.ssh/authorized_keys', key_pub)

        return cockpit_repo_path
