from JumpScale import j
import gevent


class GridHealthChecker(object):

    def __init__(self):
        with j.logger.nostdout():
            self._client = None
            installedagent = j.application.getAppHRDInstanceNames('agentcontroller_client')
            if installedagent:
                self._client = j.clients.ac.getByInstance(installedagent[0])

        self._heartbeatcl = j.data.models.system.Heartbeat
        self._nodecl = j.data.models.system.Node
        self._runningnids = list()
        self._nids = list()
        self._nodenames = dict()
        self._nodegids = dict()
        self._errors = dict()
        self._status = dict()
        self._tostdout = True
        with j.logger.nostdout():
            self.getNodes(activecheck=False)

    def _clean(self):
        self._errors = dict()
        self._status = dict()

    def _addError(self, nid, result, category=""):
        self._errors.setdefault(nid, {})
        self._errors[nid].setdefault(category, list())
        if isinstance(result, str):
            self._errors[nid][category].append({'message': result})
        else:
            self._errors[nid][category].append(result)

    def getName(self, id):
        id = int(id)
        if id in self._nodenames:
            return self._nodenames[id]
        else:
            self.getNodes(activecheck=False)
            return self._nodenames.get(id, 'UNKNOWN')

    def getGID(self, id):
        id = int(id)
        if id in self._nodegids:
            return self._nodegids[id]
        else:
            self.getNodes(activecheck=False)
            return self._nodegids.get(id, 'UNKNOWN')

    def _addResult(self, nid, result, category):
        self._status.setdefault(nid, {})
        self._status[nid].setdefault(category, list())
        self._status[nid][category].append(result)

    def _parallelize(self, functionname, clean=False, category=""):
        if functionname.__name__ in ['ping']:
            nodes = self._nids
        else:
            nodes = self._runningnids
        greens = list()
        for nid in nodes:
            greenlet = gevent.Greenlet(functionname, nid, clean)
            greenlet.nid = nid
            greenlet.start()
            greens.append(greenlet)
        gevent.joinall(greens)
        for green in greens:
            result = green.value
            if not result:
                results = list()
                errors = [(green.nid, {'message': str(green.exception), 'state': 'UNKNOWN'}, category)]
                self._returnResults(results, errors)

    def _returnResults(self, results, errors):
        for nid, result, category in results:
            self._addResult(nid, result, category)
        for nid, result, category in errors:
            self._addError(nid, result, category)
        return self._status, self._errors

    def _checkRunningNIDs(self):
        print('CHECKING HEARTBEATS...')
        self._runningnids = list()
        print("\tget all heartbeats (just query from OSIS):")
        heartbeats = self._heartbeatcl.find({})
        print("OK")
        for heartbeat in heartbeats:
            if heartbeat['nid'] not in self._nids and  heartbeat['nid']  not in self._nidsNonActive:
                self._addError(heartbeat['nid'],"found heartbeat node '%s' which is not in grid nodes."%(heartbeat['nid']),"heartbeat")

        nid2hb = dict([(x['nid'], x['lastcheck']) for x in heartbeats])
        for nid in self._nids:
            if nid not in self._nidsNonActive:
                if nid in nid2hb:
                    lastchecked = nid2hb[nid]
                    if j.data.time.getEpochAgo('-2m') < lastchecked:
                        # print "%s"%nid,
                        self._runningnids.append(nid)
                    else:                        
                        hago = round(float(j.data.time.getTimeEpoch()-lastchecked)/3600,1)
                        name = self._nodenames[nid]
                        gid = self._nodegids[nid]
                        self._addError(nid, "On node:'%s' (%s) on grid %s. Processmanager is not responding, last heartbeat %s hours ago" % (name, nid, gid, hago), "heartbeat")    
                else:
                    self._addError(nid,"found heartbeat node '%s' which is not in grid nodes." % (nid),"heartbeat")

    def _checkRunningNIDsFromPing(self):
        self._runningnids = self._nids[:]
        for nid, error in list(self._errors.items()):
            for category in error:
                if category == 'processmanagerping':
                    self._runningnids.remove(nid)

    def toStdout(self):
        self._tostdout = True

    def getNodes(self, activecheck=True):
        """
        cache in mem
        list nodes from grid
        list nodes from heartbeat
        if gridnodes found not in heartbeat -> error
        if heartbeat nodes found not in gridnodes -> error
        all the ones found in self._nids (return if populated)
        """
        nodes = self._nodecl.find({})
        self._nids = []
        self._nidsNonActive=[]
        for node in nodes:
            self._nodenames[node['nid']] = node['name']
            self._nodegids[node['nid']] = node['gid']
            if node["active"]==True:
                self._nids.append(node['nid'])
            else:
                self._nidsNonActive.append(node['nid'])
        if activecheck and nodes:
            self.pingAllNodesSync(clean=True)
            self._checkRunningNIDsFromPing()

    def getErrorsAndCheckTime(self, data):
        errors = dict()
        oldestdate = None
        for nid, result in data.items():
            for category, categorydata in result.items():
                for dataitem in categorydata:
                    if dataitem.get('state') != 'OK':
                        errors.setdefault(nid, set())
                        errors[nid].add(category)
                    checktime = dataitem.get('lastchecked')
                    if oldestdate is None or (checktime is not None and checktime < oldestdate):
                        oldestdate = checktime
        return errors, oldestdate
    def runAll(self):
        self._clean()
        self.getNodes()
        self._clean()
        self.checkHeartbeatsAllNodes(clean=False)
        self.checkProcessManagerAllNodes(clean=False)
        print(('\n**Running tests on %s node(s). %s node(s) have not responded to ping**\n' % (len(self._runningnids), len(self._nids)-len(self._runningnids))))
        self.checkDBs(clean=False)
        if self._runningnids:
            self.pingAllNodesAsync(clean=False)
            self.checkElasticSearch(clean=False)
            self.checkRedisAllNodes(clean=False)
            self.checkWorkersAllNodes(clean=False)
            self.checkDisksAllNodes(clean=False)
        if self._tostdout:
            self._printResults()
        return self._status, self._errors

    def fetchMonitoringOnAllNodes(self):
        self._clean()
        self.getNodes()
        return self._status
        for nid in self._nids:
            self.runAllOnNode(nid)
        return self._status, self._errors


    def runAllOnNode(self, nid):
        self._clean()
        self._nids = [nid]
        self.checkHeartbeatsAllNodes(clean=False, nid=nid)
        self.ping(nid=nid, clean=False)
        self.checkRedis(nid, clean=False)
        self.pingasync(nid=nid, clean=False)
        self.checkWorkers(nid, clean=False)
        self.checkDisks(nid, clean=False)
        if self._tostdout:
            self._printResults()
        return self._status, self._errors

    def _printResults(self):
        form = '%(gid)-8s %(nid)-8s %(name)-10s %(status)-8s %(issues)s'
        print((form % {'gid': 'Grid ID', 'nid': 'NODE ID', 'name': 'NAME', 'status': 'STATUS', 'issues':'ISSUES'}))
        print(('=' * 80))
        print('')
        for nid, checks in list(self._status.items()):
            if nid not in self._errors:
                nodedata={'gid': self.getGID(nid), 'nid': nid, 'name': self.getName(nid), 'status': 'OK', 'issues': ''}
                print((form % nodedata))

        for nid, checks in list(self._errors.items()):
            nodedata={'gid': self.getGID(nid), 'nid': nid, 'name': self.getName(nid), 'status': 'ERROR', 'issues': ''}
            print((form % nodedata))
            for category, errors in list(checks.items()):
                for error in errors:
                    defaultvalue = 'processmanager is unreachable by ping' if category == 'processmanager' else None
                    errormessage = error.get('message', defaultvalue)
                    if errormessage is None:
                        continue
                    for message in errormessage.split(','):
                        nodedata={'gid': '', 'nid': '', 'name': '', 'status': '', 'issues': '- %s' % message}
                        print((form % nodedata))


    def getHealthCheckJumpScripts(self):
        return [j.data.models.system.Jumpscript.get(js.guid) for js in j.data.models.system.Jumpscript.find({'category':'monitor.healthcheck'})]


    def checkElasticSearch(self, clean=True):
        return True
        if self._nids==[]:
            self.getNodes()
        if clean:
            self._clean()

        errormessage = ''
        if self.masternid not in self._runningnids:
            self._addError(self.masternid, {'state': 'UNKNOWN'}, 'elasticsearch')
            errormessage = 'ElasticSearch status UNKNOWN'
        else:
            eshealth = None

            if self._client:
                eshealth = self._client.executeJumpscript('info_gather_elasticsearch', nid=self.masternid, timeout=5)
            if eshealth['state'] == 'TIMEOUT':
                self._addError(self.masternid, {'state': 'TIMEOUT'}, 'elasticsearch')
                errormessage = 'ElasticSearch status TIMEOUT'
            elif eshealth['state'] != 'OK':
                self._addError(self.masternid, {'state': 'UNKNOWN'}, 'elasticsearch')
                errormessage = 'ElasticSearch status UNKNOWN'
            else:
                eshealth = eshealth['result']
                if eshealth==None:
                    self._addError(self.masternid,"elasticsearch did not return info for healthcheck","elasticsearch")
                    return self._status, self._errors
                size, unit = j.data.units.bytes.converToBestUnit(eshealth['size'])
                eshealth['size'] = '%.2f %sB' % (size, unit)
                size, unit = j.data.units.bytes.converToBestUnit(eshealth['memory_usage'])
                eshealth['memory_usage'] = '%.2f %sB' % (size, unit)

                if eshealth['health']['status'] in ['red']:
                    self._addError(self.masternid, eshealth, 'elasticsearch')
                    errormessage = 'ElasticSearch status is RED'
                else:
                    self._addResult(self.masternid, eshealth, 'elasticsearch')
        if errormessage:
            self._addError(self.masternid, errormessage, 'elasticsearch')
        if clean:
            return self._status, self._errors

    def checkDBs(self, clean=True):
        if self._nids==[]:
            self.getNodes()
        if clean:
            self._clean()
        errormessage = ''
        nid = j.application.whoAmI.nid
        dbhealth = None
        if self._client:
            dbhealth = self._client.executeJumpscript('healthcheck_db', nid=nid, gid=self._nodegids[nid], timeout=5)
            dbhealth = dbhealth['result']
        if dbhealth == None:
            self._addError(nid, {'state': 'UNKNOWN'}, 'databases')
            errormessage = 'Database status UNKNOWN'
        else:
            for dbname, status in list(dbhealth.items()):
                if status:
                    self._addResult(nid, status, dbname)
                else:
                    self._addError(nid, {'state': 'UNKNOWN'}, dbname)
                    errormessage = '%s status UNKNOWN' % dbname.capitalize()
        if errormessage:
            self._addError(nid, errormessage, 'databases')
        if clean:
            return self._status, self._errors


    def checkRedisAllNodes(self, clean=True):
        if clean:
            self._clean()
        if self._nids==[]:
            self.getNodes()
        print(("CHECKING REDIS ON %s NODE(S)..." % len(self._runningnids)))
        if clean:
            self._clean()
        self._parallelize(self.checkRedis, False, 'redis')
        if clean:
            return self._status, self._errors
    def runOnAllNodes(self, sync=True):
        self._clean()
        self.getNodes()
        self._clean()
        self.checkHeartbeat(clean=False)
        self.checkProcessManagerAllNodes(clean=False)
        results = list()
        greens = list()


    def getWikiStatus(self, status):
        colormap = {'RUNNING': 'green', 'HALTED': 'red', 'UNKNOWN': 'orange',
                'BROKEN': 'red', 'OK': 'green', 'NOT OK': 'red', 'WARNING': 'orange'}
        return '{color:%s}*%s*{color}' % (colormap.get(status, 'orange'), status)

    def checkRedis(self, nid, clean=True):
        if clean:
            self._clean()
        results = list()
        errors = list()
        errormessage = list()
        result = None

        if self._client:
            result = self._client.executeJumpscript('healthcheck_redis', nid=nid, gid=self._nodegids[nid], timeout=5)
            redis = result['result']
        if result['state'] != 'OK' or not redis:
            errors.append((nid, {'state': 'UNKNOWN'}, 'redis'))
            errormessage.append('Redis state UNKNOWN')
            redis = dict()

        for port, result in list(redis.items()):
            size, unit = j.data.units.bytes.converToBestUnit(result['memory_usage'])
            msize, munit = j.data.units.bytes.converToBestUnit(result['memory_max'])
            result['memory_usage'] = '%.2f %sB' % (size, unit)
            result['memory_max'] = '%.2f %sB' % (msize, munit)
            result['port'] = port
            if result['state'] == 'RUNNING':
                results.append((nid, result, 'redis'))
            else:
                errormessage.append('Redis port "%(port)s" is %(state)s. Memory usage = %(memory_usage)s/ %(memory_max)s' % result)
                errors.append((nid, result, 'redis'))
        if errormessage:
            errors.append((nid, ','.join(errormessage), 'redis'))
        self._returnResults(results, errors)
        return results, errors

    def checkWorkersAllNodes(self,clean=True):
        if self._nids==[]:
            self.getNodes()
        if clean:
            self._clean()
        print(("CHECKING WORKERS ON %s NODE(S)..." % len(self._runningnids)))
        self._parallelize(self.checkWorkers, False, 'workers')
        if clean:
            return self._status, self._errors

    def checkWorkers(self, nid, clean=True):
        if clean:
            self._clean()
        results = list()
        errors = list()
        errormessage = list()
        workers = None
        result = None

        if self._client:
            result = self._client.executeJumpscript('workerstatus', nid=nid, gid=self._nodegids[nid], timeout=30)
            workers = result['result']
        if result['state'] != 'OK' or not workers:
            errors.append((nid, {'state':'UNKNOWN', 'mem': '0 B'}, 'workers'))
            errormessage.append('Workers status UNKNOWN')
            workers = dict()

        for worker, stats in list(workers.items()):
            stats['name'] = worker
            if stats['state'] == 'RUNNING':
                results.append((nid, stats, 'workers'))
            else:
                statsmod = stats.copy()
                statsmod['lastactive'] = j.data.time.epoch2HRDateTime(stats['lastactive']) if stats['lastactive'] else 'never'
                errormessage.append('%(name)s is %(state)s. Last active: %(lastactive)s.' % statsmod)
                errors.append((nid, stats, 'workers'))
        if errormessage:
            errors.append((nid, ','.join(errormessage), 'workers'))
        self._returnResults(results, errors)
        return results, errors


    def checkProcessManagerAllNodes(self, clean=True):
        if clean:
            self._clean()
        if self._nids==[]:
            self.getNodes()
        print("CHECKING PROCESSMANAGERS...")
        haltednodes = set(self._nids)-set(self._runningnids)
        for nid in haltednodes:
            self._addError(nid, {'state': 'HALTED'}, 'processmanager')
        for nid in self._runningnids:
            self._addResult(nid, {'state': 'RUNNING'}, 'processmanager')
        if clean:
            return self._status, self._errors
    def checkHeartbeat(self, clean=True, nid=None):
        if clean:
            self._clean()
        if self._nids==[]:
            self.getNodes()
        print('CHECKING HEARTBEATS...')
        print("\tget all heartbeats (just query from OSIS):")
        print("OK")
        heartbeats = self._heartbeatcl.find({'nid':nid})
        for heartbeat in heartbeats:
            if heartbeat['nid'] not in self._nids and heartbeat['nid'] not in self._nidsNonActive:
                self._addResult(heartbeat['nid'], {'message': "Found heartbeat node '%s' when not in grid nodes." % heartbeat['nid'],
                                'state': 'ERROR'}, "JSAgent")

        nid2hb = dict([(x['nid'], x['lastcheck']) for x in heartbeats])
        nids = [nid] if nid else self._nids
        for nid in nids:
            if nid not in self._nidsNonActive:
                if nid in nid2hb:
                    lastchecked = nid2hb[nid]
                    if not j.data.time.getEpochAgo('-2m') < lastchecked:
                        state = 'ERROR'
                    else:
                        state = 'OK'
                    self._addResult(nid, {'message': "Heartbeat", 'state': state, 'lastchecked': lastchecked}, "JSAgent")
                else:
                    self._addResult(nid, {'message': "Found heartbeat node when not in grid nodes.", 'state':'ERROR'}, "JSAgent")
        if clean:
            return self._status

    def checkHeartbeatsAllNodes(self, clean=True, nid=None):
        if clean:
            self._clean()
        if self._nids==[]:
            self.getNodes()
        print('CHECKING HEARTBEATS...')
        print("\tget all heartbeats (just query from OSIS):")
        print("OK")
        query = {}
        if nid:
            query['nid'] = nid
        heartbeats = self._heartbeatcl.find(query)
        for heartbeat in heartbeats:
            if heartbeat['nid'] not in self._nids and  heartbeat['nid']  not in self._nidsNonActive:
                self._addError(heartbeat['nid'], "found heartbeat node '%s' when not in grid nodes." % heartbeat['nid'],"heartbeat")

        nid2hb = dict([(x['nid'], x['lastcheck']) for x in heartbeats])
        for nid in self._nids:
            if nid not in self._nidsNonActive:
                if nid in nid2hb:
                    lastchecked = nid2hb[nid]
                    hago = j.data.time.getSecondsInHR(j.data.time.getTimeEpoch()-lastchecked)
                    if not j.data.time.getEpochAgo('-2m') < lastchecked:
                        self._addError(nid, "Last heartbeat %s ago" % hago,"heartbeat")
                    else:
                        self._addResult(nid, "Last heartbeat %s ago" % hago,"heartbeat")
                else:
                    self._addError(nid, "found heartbeat node when not in grid nodes.","heartbeat")
        if clean:
            return self._status, self._errors

    def checkProcessManager(self, nid, clean=True):
        """
        Check heartbeat on specified node, see if result came in osis
        """
        if clean:
            self._clean()
        gid = self.getGID(nid)
        if self._heartbeatcl.find({'gid':gid,'nid':nid}):
            heartbeat = self._heartbeatcl.find({'gid':gid,'nid':nid})[0]
            lastchecked = heartbeat.lastcheck
            if  j.data.time.getEpochAgo('-2m') < lastchecked:
                self._addResult(nid, {'state': 'RUNNING'}, 'processmanager')
            else:
                self._addError(nid, {'state': 'HALTED'}, 'processmanager')
        else:
            self._addError(nid, {'state': 'UNKNOWN'}, 'processmanager')
        return self._status, self._errors

    def checkDisksAllNodes(self, clean=True):
        if clean:
            self._clean()
        if self._nids==[]:
            self.getNodes()
        print(("CHECKING DISKS ON %s NODE(S)..." % len(self._runningnids)))
        self._parallelize(self.checkDisks, False, 'disks')
        if clean:
            return self._status, self._errors

    def pingAllNodesSync(self, clean=True):
        if clean:
            self._clean()
        if self._nids==[]:
            self.getNodes(activecheck=False)
        print(("PROCESS MANAGER PING TO ALL (%s) NODES..." % len(self._nids)))
        self._parallelize(self.ping, False, 'processmanagerping')
        return self._status, self._errors

    def pingAllNodesAsync(self, clean=True):
        if self._nids==[]:
            self.getNodes()
        if clean:
            self._clean()
        print(("WORKER PING TO %s NODE(S)..." % len(self._runningnids)))
        self._parallelize(self.pingasync, False, 'workerping')
        return self._status, self._errors        

    def ping(self,nid,clean=True):
        if clean:
            self._clean()
        results = list()
        errors = list()
        result = None

        if self._client:
            result = self._client.executeJumpscript('system_echo_sync', args={"msg":"ping"}, nid=nid, gid=self._nodegids[nid], timeout=5)
        if not result["result"]=="ping":
            errors.append((nid, {'ping': 'down'}, 'processmanagerping'))
            errors.append((nid, 'cannot ping processmanager', 'processmanagerping'))
        self._returnResults(results, errors)
        return results, errors

    def pingasync(self,nid,clean=True):
        if clean:
            self._clean()
        results = list()
        errors = list()
        result = None

        if self._client:
            result = self._client.executeJumpscript('system_echo_async', args={"msg":"ping"}, nid=nid, gid=self._nodegids[nid], timeout=5)
        if not result["result"]=="ping":
            errors.append((nid, {'ping': 'down'}, 'workerping'))
            errors.append((nid, 'cannot ping workers', 'workerping'))
        self._returnResults(results, errors)
        return results, errors

    def checkDisks(self, nid, clean=True):
        if clean:
            self._clean()
        results = list()
        errors = list()
        errormessage = list()
        result = None

        if self._client:
            result = self._client.executeJumpscript('healthcheck_disks', nid=nid, gid=self._nodegids[nid], timeout=30)
            disks = result['result']
        if result['state'] != 'OK':
            errors.append((nid, {'state': 'UNKNOWN'}, 'disks'))
            errormessage.append('Disks status UNKNOWN.')
            disks = dict()
        else:
            if not disks:
                disks = dict()
        for path, disk in list(disks.items()):
            disk['path'] = path
            if (disk['free'] and disk['size']) and (disk['free'] / float(disk['size'])) * 100 < 10:
                disk['message'] = 'FREE SPACE LESS THAN 10%% on disk %s' % path
                disk['state'] = 'NOT OK'
                errors.append((nid, {path: disk}, 'disks'))
                errormessage.append('Disk %(path)s is %(state)s. %(message)s.' % disk)
            else:
                if disk['free']:
                    size, unit = j.data.units.bytes.converToBestUnit(disk['free'], 'M')
                    disk['message'] = '%.2f %siB free space available' % (size, unit)

                else:
                    disk['message'] = 'Disk is not mounted, Info is not available'
                disk['state'] = 'OK'
                results.append((nid, disk, 'disks'))
        if errormessage:
            errors.append((nid, ','.join(errormessage), 'disks'))
        self._returnResults(results, errors)
        return results, errors
