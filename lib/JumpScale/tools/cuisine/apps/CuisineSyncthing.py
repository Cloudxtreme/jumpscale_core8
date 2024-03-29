from JumpScale import j


from ActionDecorator import ActionDecorator


"""
please ensure that the start and build methods are separate and
the build doesnt place anyfile outside opt as it will be used in aysfs mounted system
"""

class actionrun(ActionDecorator):
    def __init__(self, *args, **kwargs):
        ActionDecorator.__init__(self, *args, **kwargs)
        self.selfobjCode = "cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.apps.syncthing"


class Syncthing():
    
    def __init__(self, executor, cuisine):
        self.executor = executor
        self.cuisine = cuisine

    @actionrun(action=True)
    def build(self, start=True):
        """
        build and setup syncthing to run on :8384 , this can be changed from the config file in /optvar/cfg/syncthing
        """
        self.cuisine.apps.installdeps()

        config="""
        <configuration version="11">
            <folder id="default" path="$homeDir/Sync" ro="false" rescanIntervalS="60" ignorePerms="false" autoNormalize="false">
                <device id="H7MBKSF-XNFETHA-2ERDXTB-JQCAXTA-BBTTLJN-23TN5BZ-4CL7KLS-FYCISAR"></device>
                <minDiskFreePct>1</minDiskFreePct>
                <versioning></versioning>
                <copiers>0</copiers>
                <pullers>0</pullers>
                <hashers>0</hashers>
                <order>random</order>
                <ignoreDelete>false</ignoreDelete>
            </folder>
            <device id="H7MBKSF-XNFETHA-2ERDXTB-JQCAXTA-BBTTLJN-23TN5BZ-4CL7KLS-FYCISAR" name="$hostname" compression="metadata" introducer="false">
                <address>dynamic</address>
            </device>
            <gui enabled="true" tls="false">
                <address>$lclAddrs:$port</address>
                <apikey>wbgjQX6uSgjI1RfS7BT1XQgvGX26DHMf</apikey>
            </gui>
            <options>
                <listenAddress>0.0.0.0:22000</listenAddress>
                <globalAnnounceServer>udp4://announce.syncthing.net:22026</globalAnnounceServer>
                <globalAnnounceServer>udp6://announce-v6.syncthing.net:22026</globalAnnounceServer>
                <globalAnnounceEnabled>true</globalAnnounceEnabled>
                <localAnnounceEnabled>true</localAnnounceEnabled>
                <localAnnouncePort>21025</localAnnouncePort>
                <localAnnounceMCAddr>[ff32::5222]:21026</localAnnounceMCAddr>
                <maxSendKbps>0</maxSendKbps>
                <maxRecvKbps>0</maxRecvKbps>
                <reconnectionIntervalS>60</reconnectionIntervalS>
                <startBrowser>true</startBrowser>
                <upnpEnabled>true</upnpEnabled>
                <upnpLeaseMinutes>60</upnpLeaseMinutes>
                <upnpRenewalMinutes>30</upnpRenewalMinutes>
                <upnpTimeoutSeconds>10</upnpTimeoutSeconds>
                <urAccepted>0</urAccepted>
                <urUniqueID></urUniqueID>
                <restartOnWakeup>true</restartOnWakeup>
                <autoUpgradeIntervalH>12</autoUpgradeIntervalH>
                <keepTemporariesH>24</keepTemporariesH>
                <cacheIgnoredFiles>true</cacheIgnoredFiles>
                <progressUpdateIntervalS>5</progressUpdateIntervalS>
                <symlinksEnabled>true</symlinksEnabled>
                <limitBandwidthInLan>false</limitBandwidthInLan>
                <databaseBlockCacheMiB>0</databaseBlockCacheMiB>
                <pingTimeoutS>30</pingTimeoutS>
                <pingIdleTimeS>60</pingIdleTimeS>
                <minHomeDiskFreePct>1</minHomeDiskFreePct>
            </options>
        </configuration>
        """
        #create config file
        content = self.cuisine.core.args_replace(config)
        content = content.replace("$lclAddrs",  "0.0.0.0", 1)
        content = content.replace ("$port", "8384", 1)

        self.cuisine.core.dir_ensure("$tmplsDir/cfg/syncthing/")
        self.cuisine.core.file_write("$tmplsDir/cfg/syncthing/config.xml", content)

        #build
        url = "https://github.com/syncthing/syncthing.git"
        self.cuisine.core.dir_remove('$goDir/src/github.com/syncthing/syncthing')
        dest = self.cuisine.git.pullRepo(url, branch="v0.11.25",  dest='$goDir/src/github.com/syncthing/syncthing', ssh=False, depth=None)
        self.cuisine.core.run('cd %s && godep restore' % dest, profile=True)
        self.cuisine.core.run("cd %s && ./build.sh noupgrade" % dest, profile=True)

        #copy bin
        self.cuisine.core.file_copy(self.cuisine.core.joinpaths(dest, 'syncthing'), "$goDir/bin/", recursive=True)
        self.cuisine.core.file_copy("$goDir/bin/syncthing", "$binDir", recursive=True)

        if start:
            self.start()

    def start(self):
        self.cuisine.core.dir_ensure("$cfgDir")
        self.cuisine.core.file_copy("$tmplsDir/cfg/syncthing/", "$cfgDir", recursive=True)

        GOPATH = self.cuisine.bash.environGet('GOPATH')
        env={}
        env["TMPDIR"]=self.cuisine.core.dir_paths["tmpDir"]
        pm = self.cuisine.processmanager.get("tmux")
        pm.ensure(name="syncthing", cmd="./syncthing -home  $cfgDir/syncthing", path=self.cuisine.core.joinpaths(GOPATH, "bin"))