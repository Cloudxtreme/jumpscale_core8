import uuid

from JumpScale import j


GENERIC_TIMEOUT = 5
GET_INFO_TIMEOUT = 5

CMD_EXECUTE = 'execute'
CMD_EXECUTE_JUMPSCRIPT = 'jumpscript'
CMD_EXECUTE_JUMPSCRIPT_CONTENT = 'jumpscript_content'
CMD_GET_CPU_INFO = 'get_cpu_info'
CMD_GET_NIC_INFO = 'get_nic_info'
CMD_GET_OS_INFO = 'get_os_info'
CMD_GET_AGGREGATED_STATS = 'get_aggregated_stats'
CMD_GET_DISK_INFO = 'get_disk_info'
CMD_GET_MEM_INFO = 'get_mem_info'
CMD_GET_PROCESSES_STATS = 'get_processes_stats'
CMD_TUNNEL_OPEN = 'hubble_open_tunnel'
CMD_TUNNEL_CLOSE = 'hubble_close_tunnel'
CMD_TUNNEL_LIST = 'hubble_list_tunnels'
CMD_GET_MSGS = 'get_msgs'

QUEUE_CMDS_MAIN = 'cmds.queue'
LEVELS = list(range(1, 10)) + list(range(20, 24)) + [30]

LEVEL_JSON = 20


def jsonLoads(x):
    if isinstance(x, bytes):
        x = x.decode('utf-8')
    return j.data.serializer.json.loads(x)


class AgentException(Exception):
    pass


class ResultTimeout(AgentException):
    pass


class RunArgs(object):
    """
    Creates a new instance of RunArgs

    :param domain: Domain name
    :param name: script or executable name
    :param max_time: Max run time, 0 (forever), -1 forever but remember during reboots (long running),
                   other values is timeout
    :param max_restart: Max number of restarts if process died in under 5 min.
    :param recurring_period: Scheduling time
    :param stats_interval: How frequent the stats aggregation is done/flushed to AC
    :param args: Command line arguments (in case of execute)
    :param loglevels: Which log levels to capture and pass to logger
    :param loglevels_db: Which log levels to store in DB (overrides logger defaults)
    :param loglevels_ac: Which log levels to send to AC (overrides logger defaults)
    :param queue: Name of the command queue to wait on.

    This job will not get executed until no other commands running on the same queue.
    """
    def __init__(self, domain=None, name=None, max_time=0, max_restart=0, working_dir=None,
                 recurring_period=0, stats_interval=0, args=None, loglevels='*',
                 loglevels_db=None, loglevels_ac=None, queue=None):
        self._domain = domain
        self._name = name
        self._max_time = max_time
        self._max_restart = max_restart
        self._working_dir = working_dir
        self._recurring_period = recurring_period
        self._stats_interval = stats_interval
        self._args = args
        self._loglevels = loglevels
        self._loglevels_db = loglevels_db
        self._loglevels_ac = loglevels_ac
        self._queue = queue

    @property
    def domain(self):
        """
        Command domain name
        """
        return self._domain

    @property
    def name(self):
        """
        Script or executable name. It's totally up to the ``cmd`` to interpret this
        """
        return self._name

    @property
    def max_time(self):
        """
        Max exection time.
        """
        return self._max_time

    @property
    def max_restart(self):
        """
        Max number of restarts before agent gives up
        """
        return self._max_restart

    @property
    def working_dir(self):
        return self._working_dir

    @property
    def recurring_period(self):
        """
        How often to run this job (in seconds)
        """
        return self._recurring_period

    @property
    def stats_interval(self):
        """
        How frequent the stats aggregation is done/flushed to AC
        """
        return self._stats_interval

    @property
    def args(self):
        """
        List of command line arguments (if applicable)
        """
        return self._args or []

    @property
    def loglevels(self):
        """
        Log levels to process
        """
        return self._loglevels or ''

    @property
    def loglevels_ac(self):
        """
        Which log levels to report back to AC
        """
        return self._loglevels_ac or ''

    @property
    def loglevels_db(self):
        """
        Which log levels to store in agent DB
        """
        return self._loglevels_db or ''

    @property
    def queue(self):
        """
        Which command queue to wait in (in case of serial exection)
        """
        return self._queue

    def dump(self):
        """
        Return run arguments dict

        :rtype: dict
        """
        dump = {}
        for key in ('domain', 'name', 'max_time', 'max_restart', 'recurring_period', 'working_dir',
                    'stats_interval', 'args', 'loglevels', 'loglevels_db', 'loglevels_ac', 'queue'):
            value = getattr(self, key)
            if value:
                dump[key] = value
        return dump

    def update(self, args):
        """
        Return a new instance of run arguments with updated arguments

        :param args: overrides the current arguments with this set
        :type args: :class:`acclient.RunArgs` or :class:`dict`

        :rtype: :class:`acclient.RunArgs`
        """
        base = self.dump()
        if isinstance(args, RunArgs):
            data = args.dump()
        elif isinstance(args, dict):
            data = args
        elif args is None:
            data = {}
        else:
            raise ValueError('Expecting RunArgs or dict')

        base.update(data)
        return RunArgs(**base)


class Base(object):
    def __init__(self, client, id, gid, nid):
        self._client = client
        self._id = id
        self._gid = 0 if gid is None else int(gid)
        self._nid = 0 if nid is None else int(nid)

    @property
    def id(self):
        """
        Command ID
        """
        return self._id

    @property
    def gid(self):
        """
        Grid ID
        """
        return self._gid

    @property
    def nid(self):
        """
        Node ID
        """
        return self._nid


class Job(Base):
    """
    Job Information
    """
    def __init__(self, client, jobdata):
        super(Job, self).__init__(client, jobdata['id'], jobdata['gid'], jobdata['nid'])
        self._redis = client._redis
        self._set_job(jobdata)

    def _set_job(self, jobdata):
        self._jobdata = jobdata
        args = jobdata.get('args')
        self._args = RunArgs(**args) if args else None

    @property
    def starttime(self):
        """
        Job starttime
        """
        return self._jobdata['starttime']

    @property
    def state(self):
        """
        Job state
        """
        self._update()
        return self._jobdata['state']

    def _update(self):
        state = self._jobdata['state']
        if state is None or state in ('RUNNING', 'QUEUED'):
            job = self._client.get_cmd_jobs(self.id)[(self.gid, self.nid)]
            self._jobdata = job._jobdata

    @property
    def args(self):
        """
        Job args
        """
        if self._args is None:
            self._update()
            if 'args' in self._jobdata:
                self._args = RunArgs(**self._jobdata['args'])
        return self._args

    @property
    def level(self):
        """
        Job level
        """
        self._update()
        return self._jobdata['level']

    @property
    def cmd(self):
        """
        Job cmd
        """
        return self._jobdata['cmd']

    @property
    def time(self):
        """
        Job runtime in miliseconds
        """
        self._update()
        return self._jobdata['time']

    @property
    def streams(self):
        self._update()
        default = ['', '']
        streams = self._jobdata.get('streams', default)
        return streams or default

    @property
    def critical(self):
        return self._jobdata.get('critical', '')

    @property
    def data(self):
        """
        Job data
        """
        self._update()
        return self._jobdata['data']

    @property
    def tags(self):
        return self._jobdata.get('tags')

    def _get_result_queue(self):
        return 'cmd.%s.%d.%d' % (self.id, self.gid, self.nid)

    def wait(self, timeout=GENERIC_TIMEOUT):
        """
        Waits for the job until it finishes or timeout
        :param timeout: (default=5 sec) 0 for never.
        """

        try:
            rqueue = self._get_result_queue()
            result = self._redis.brpoplpush(rqueue, rqueue, timeout)
        except TypeError:
            raise ResultTimeout('Timedout while waiting for job %s' % self)

        if result is None:
            raise ResultTimeout('Timedout while waiting for job %s' % self)

        return self._set_job(jsonLoads(result))

    def kill(self):
        """
        Kills this command on agent (if it's running)
        """
        return self._client.cmd(self._gid, self._nid, 'kill', RunArgs(), data=j.data.serializer.json.dumps({'id': self._id}))

    def get_stats(self):
        """
        Gets the job cpu and memory stats on agent. Only valid if job is still running on
        agent. otherwise will give an error.
        """
        if self.state != 'RUNNING':
            raise AgentException('Can only get stats on running jobs')
        stats = self._client.cmd(self._gid, self._nid, 'get_process_stats',
                                 RunArgs(), data=j.data.serializer.json.dumps({'id': self._id})).get_next_result(GET_INFO_TIMEOUT)
        if stats.state != 'SUCCESS':
            raise AgentException(stats.data)

        # TODO: parsing data should be always based on the level
        result = jsonLoads(stats.data)
        return result

    def get_msgs(self, levels='*', limit=20):
        """
        Gets job log messages from agent

        :param levels: Log levels to retrieve, default to '*' (all)
        :param limit: Max number of log lines to retrieve (max to 1000)

        :rtype: list of dict
        """
        return self._client.get_msgs(self._gid, self._nid, jobid=self._id, levels=levels, limit=limit)

    def __repr__(self):
        return '<Job at {this.gid}:{this.nid} id={this.id}>'.format(this=self)


class BaseCmd(Base):
    """
    Base command. You never need to create an instance of this class, always use :func:`acclient.Client.cmd` or any of
    the other shortcuts.
    """
    def __init__(self, client, id, gid, nid):
        super(BaseCmd, self).__init__(client, id, gid, nid)

    def get_jobs(self):
        """
        Returns a list with all available job results

        :rtype: dict of :class:`acclient.Job`
        """
        return self._client.get_cmd_jobs(self._id)


class Cmd(BaseCmd):
    """
    Child of :class:`acclient.BaseCmd`

    You probably don't need to make an instance of this class manually. Alway use :func:`acclient.Client.cmd` or
    ony of the client shortcuts.
    """
    def __init__(self, client, id, gid, nid, cmd, args, data, roles, fanout, tags):
        if not isinstance(args, RunArgs):
            raise ValueError('Invalid arguments')

        if not (bool(roles) ^ bool(nid)):
            raise ValueError('Nid and Roles are mutual exclusive')

        if not bool(gid) and not bool(roles):
            raise ValueError('Gid or Roles are required')

        if fanout and roles is None:
            raise ValueError('Fanout only effective if roles is set')

        super(Cmd, self).__init__(client, id, gid, nid)
        self._cmd = cmd
        self._args = args
        self._data = data
        self._roles = roles
        self._fanout = fanout
        self._tags = tags
        self._result_iter = None

    def iter_results(self, timeout=GENERIC_TIMEOUT):
        """
        Iterate over the jobs. It blocks until the job is finished

        :param timeout: Waits for this amount of seconds before giving up on results. 0 means wait forever.

        :rtype: dict
        """

        for key, job in self.get_jobs().items():
            job.wait(timeout)
            yield job

    def get_next_result(self, timeout=GENERIC_TIMEOUT):
        """
        Pops and returns the first available result for that job. It blocks until the result is givent

        The result is POPed out of the result queue, so a second call to the same method will block until a new
            result object is available for that job. In case you don't want to wait use noblock_get_next_result()

        :param timeout: Waits for this amount of seconds before giving up on results. 0 means wait forever.

        :rtype: dict
        """
        if self._result_iter is None:
            self._result_iter = self.iter_results(timeout)

        return next(self._result_iter)

    @property
    def cmd(self):
        """
        Command name
        """
        return self._cmd

    @property
    def args(self):
        """
        Command run arguments
        """
        return self._args

    @property
    def data(self):
        """
        Command data
        """
        return self._data

    @property
    def roles(self):
        """
        Command roles
        """
        return self._roles

    @property
    def fanout(self):
        """
        Either to fanout command
        """
        return self._fanout

    @property
    def tags(self):
        return self._tags

    def dump(self):
        """
        Gets the command as a dict

        :rtype: dict
        """
        return {
            'id': self.id,
            'gid': self.gid,
            'nid': self.nid,
            'tags': self.tags,
            'roles': self.roles,
            'fanout': self.fanout,
            'cmd': self.cmd,
            'args': self.args.dump(),
            'data': self.data if self.data is not None else ''
        }

    def __repr__(self):
        return repr(self.dump())


class Client(object):
    """
    Creates a new client instance. You need a client to send jobs to the agent-controller
    and to retrieve results

    :param address: Redis host address
    :param port: Redis port
    :param password: (optional) redis password
    """
    def __init__(self, address='localhost', port=6379, password=None):
        # Initializing redis client
        self._redis = j.clients.redis.get(ipaddr=address, port=port, password=password, fromcache=True)
        # Check the connectivity
        self._redis.ping()

    getRunArgs = RunArgs

    def _build_cmd(self, gid, nid, cmd, args, data=None, id=None, roles=None, fanout=False, tags=None):
        cmd_id = id or str(uuid.uuid4())
        return Cmd(self, id=cmd_id, gid=gid, nid=nid, cmd=cmd, args=args,
                   data=data, roles=roles, fanout=fanout, tags=tags)

    def cmd(self, gid, nid, cmd, args, data=None, id=None, roles=None, fanout=False, tags=None):
        """
        Executes a command, return a cmd descriptor

        :param gid: grid id (can be None)
        :param nid: node id (can be None)
        :param cmd: one of the supported commands (execute, execute_js_py, get_x_info, etc...)
        :param args: instance of RunArgs
        :param data: Raw data to send to the command standard input. Passed as objecte and will be dumped as json on
                   wire
        :param id: id of command for retrieve later, if None a random GUID will be generated.
        :param roles: Optional rolse, only agents that satisfy this role can process this job. This is mutual exclusive
                    with gid/nid compo in that case, the gid/nid values must be None or a ValueError will be raised.
                    There is a special role '*' which means ANY.
        :type roles: list
        :param fanout: Send job to ALL agents that satisfy the given role. Only effective is role is set.
        :param tags: Tags string that will be attached to the command and return with the results as is. Usefule to
                   attach meta data to the command for analysis
        Allowed compinations:

        +-----+-----+------+---------------------------------------+
        | GID | NID | ROLE | Meaning                               |
        +=====+=====+======+=======================================+
        |  X  |  X  |  O   | To specific agent Gid/Nid             |
        +-----+-----+------+---------------------------------------+
        |  X  |  O  |  X   | Any agent with that role on this grid |
        +-----+-----+------+---------------------------------------+
        |  O  |  O  |  X   | Any agent with that role globaly      |
        +-----+-----+------+---------------------------------------+

        :rtype: :class:`acclient.Cmd`
        """
        cmd = self._build_cmd(gid=gid, nid=nid, cmd=cmd, args=args, data=data,
                              id=id, roles=roles, fanout=fanout, tags=tags)

        payload = j.data.serializer.json.dumps(cmd.dump())
        self._redis.rpush(QUEUE_CMDS_MAIN, payload)
        return cmd

    def schedule_add(self, id, cron, gid, nid, cmd, args, data=None, roles=None, fanout=False, tags=None,
                     validate_queued=False):
        """
        Schedule a command to run on the given cron expression.

        Cron expression represents a set of times, using 6 space-separated fields.

        +--------------+------------+-----------------+----------------------------+
        | Field name   | Mandatory? | Allowed values  | Allowed special characters |
        +==============+============+=================+============================+
        | Seconds      | Yes        | 0-59            | * / , -                    |
        +--------------+------------+-----------------+----------------------------+
        | Minutes      | Yes        | 0-59            | * / , -                    |
        +--------------+------------+-----------------+----------------------------+
        | Hours        | Yes        | 0-23            | * / , -                    |
        +--------------+------------+-----------------+----------------------------+
        | Day of month | Yes        | 1-31            | * / , - ?                  |
        +--------------+------------+-----------------+----------------------------+
        | Month        | Yes        | 1-12 or JAN-DEC | * / , -                    |
        +--------------+------------+-----------------+----------------------------+
        | Day of week  | Yes        | 0-6 or SUN-SAT  | * / , - ?                  |
        +--------------+------------+-----------------+----------------------------+

        Note: Month and Day-of-week field values are case insensitive. "SUN", "Sun", and "sun" are equally accepted.

        :param id: Cron job id, must be unique globally and can be used later to stop the schedule
        :param cron: Cron string to run the task
        :param validate_queued: If False (default), the schedule_add will not validated that the schedule_add command
                              has been picked up by the controller. This is usefule when you want to schedule tasks
                              while the agent controller is not up yet. So client will just push this command to queue
                              and will not care about it.

        Note: Other params are exeactly as :func:`acclient.Client.cmd`
        """
        cmd = self._build_cmd(gid=gid, nid=nid, cmd=cmd, args=args,
                              data=data, id='', roles=roles, fanout=fanout, tags=tags).dump()

        data = {
            'cron': cron,
            'cmd': cmd,
            'id': str(id),
        }

        cmd = self.cmd(0, 0, 'controller', RunArgs(name='scheduler_add'),
                       data=j.data.serializer.json.dumps(data), roles=['*'])
        if validate_queued:
            result = cmd.get_next_result(GET_INFO_TIMEOUT)
            return self._load_json_or_die(result)

    def schedule_list(self):
        """
        List all scheduled jobs
        """
        cmd = self.cmd(0, 0, 'controller', RunArgs(name='scheduler_list'), roles=['*'])
        result = cmd.get_next_result(GET_INFO_TIMEOUT)

        return self._load_json_or_die(result)

    def schedule_remove(self, id, validate_queued=False):
        """
        Remove a scheduled job by ID
        """
        cmd = self.cmd(0, 0, 'controller', RunArgs(name='scheduler_remove'), data=j.data.serializer.json.dumps(str(id)), roles=['*'])
        if validate_queued:
            result = cmd.get_next_result(GET_INFO_TIMEOUT)
            return self._load_json_or_die(result)

    def schedule_remove_prefix(self, prefix, validate_queued=False):
        """
        Remove a scheduled job by ID
        """
        cmd = self.cmd(0, 0, 'controller', RunArgs(name='scheduler_remove_prefix'), data=j.data.serializer.json.dumps(str(prefix)), roles=['*'])
        if validate_queued:
            result = cmd.get_next_result(GET_INFO_TIMEOUT)
            return self._load_json_or_die(result)

    def execute(self, gid, nid, executable, cmdargs=None, args=None, data=None, id=None, roles=None,
                fanout=False, tags=None):
        """
        Short cut for cmd.execute

        :param gid: grid id
        :param nid: node id
        :param executable: the executable to run_args
        :param cmdargs: An optional array with command line arguments
        :param args: Optional RunArgs
        :param data: Raw data to the command stdin. (see cmd)
        :param id: Optional command id (see cmd)
        :param roles: Optional role, only agents that satisfy this role can process this job. This is mutual exclusive
                    with gid/nid compo in that case, the gid/nid values must be None or a ValueError will be raised.
                    There is a special role '*' which means ANY.
        :type roles: list
        :param fanout: Fanout job to all agents with given role (only effective if role is set)
        :param tags: Tags string that will be attached to the command and return with the results as is. Usefule to
                   attach meta data to the command for analysis
        """
        if cmdargs is not None and not isinstance(cmdargs, list):
            raise ValueError('cmdargs must be a list')

        args = RunArgs().update(args).update({'name': executable, 'args': cmdargs})

        return self.cmd(gid=gid, nid=nid, cmd=CMD_EXECUTE, args=args, data=data, id=id, roles=roles,
                        fanout=fanout, tags=tags)

    def execute_jumpscript(self, gid, nid, domain, name, args={}, runargs=None, roles=None, fanout=False, tags=None):
        """
        Executes jumpscale script (py) on agent. The execute_js_py extension must be
        enabled and configured correctly on the agent.

        :param gid: Grid id
        :param nid: Node id
        :param domain: Domain of script
        :param name: Name of script
        :param args: dict object (any json serializabl struct) that will be used as jumpscript kwargs
        :param runargs: Optional run arguments
        :type args: :class:`acclient.RunArgs`
        :param roles: Optional role, only agents that satisfy this role can process this job. This is mutual exclusive
                    with gid/nid compo in that case, the gid/nid values must be None or a ValueError will be raised.
                    There is a special role '*' which means ANY.
        :type roles: list
        :param fanout: Fanout job to all agents with given role (only effective if role is set)
        """
        runargs = RunArgs().update(runargs).update({'domain': domain, 'name': name})
        return self.cmd(gid, nid, CMD_EXECUTE_JUMPSCRIPT, runargs,j.data.serializer.json.dumps(args), roles=roles,
                        fanout=fanout, tags=tags)

    def execute_jumpscript_content(self, gid, nid, content, args={}, runargs=None, roles=None, fanout=False, tags=None):
        data = {
            'content': content,
            'args': args
        }
        runargs = RunArgs().update(runargs)
        return self.cmd(gid=gid, nid=nid, cmd=CMD_EXECUTE_JUMPSCRIPT_CONTENT, args=runargs,
                        data=j.data.serializer.json.dumps(data), roles=roles, fanout=fanout, tags=tags)

    def get_by_id(self, gid, nid, id):
        """
        Get a command descriptor by an ID. So you can read command result later if the ID is known.

        :rtype: :class:`acclient.BaseCmd`
        """
        return BaseCmd(self, id, gid, nid)

    def _load_json_or_die(self, result):
        if result.state == 'SUCCESS':
            if result.level != LEVEL_JSON:
                raise AgentException("Expected json data got response level '%d'" % result.level)
            return jsonLoads(result.data)
        else:
            error = result.data or result.streams[1]
            raise AgentException(
                'Job {job} failed with state: {job.state} and message: "{error}"'.format(job=result, error=error)
            )

    def get_cpu_info(self, gid, nid):
        """
        Get CPU info of the agent node
        """
        result = self.cmd(gid, nid, CMD_GET_CPU_INFO, RunArgs()).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def get_disk_info(self, gid, nid):
        """
        Get disk info of the agent node
        """
        result = self.cmd(gid, nid, CMD_GET_DISK_INFO, RunArgs()).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def get_mem_info(self, gid, nid):
        """
        Get MEM info of the agent node
        """
        result = self.cmd(gid, nid, CMD_GET_MEM_INFO, RunArgs()).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def get_nic_info(self, gid, nid):
        """
        Get NIC info of the agent node
        """
        result = self.cmd(gid, nid, CMD_GET_NIC_INFO, RunArgs()).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def get_os_info(self, gid, nid):
        """
        Get OS info of the agent node
        """
        result = self.cmd(gid, nid, CMD_GET_OS_INFO, RunArgs()).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def get_aggregated_stats(self, gid, nid):
        """
        Get OS info of the agent node
        """
        result = self.cmd(gid, nid, CMD_GET_AGGREGATED_STATS, RunArgs()).get_next_result(GET_INFO_TIMEOUT)
        stats = self._load_json_or_die(result)
        stats.pop('cmd', None)
        return stats

    def get_cmd_jobs(self, id, timeout=5):
        """
        Returns a dict with all available job results

        :rtype: dict of :class:`acclient.Job`
        """
        def wrap_jobs(jobresult):
            result = jsonLoads(jobresult)
            return (result['gid'], result['nid']), Job(self, result)

        # wait until we make sure all jobs were queued
        jqueue = 'cmd.%s.queued' % id
        event = self._redis.brpoplpush(jqueue, jqueue, timeout)
        if event == '' or event is None:
            raise ResultTimeout('Timedout while waiting for jobs to get queued, is agent controller working?')

        results = self._redis.hgetall('jobresult:%s' % id)
        return dict(list(map(wrap_jobs, list(results.values()))))

    def get_processes(self, gid, nid, domain=None, name=None):
        """
        Get stats for all running process at the moment of the call, optionally filter with domain and/or name
        """
        data = {
            'domain': domain,
            'name': name
        }

        result = self.cmd(gid,
                          nid,
                          CMD_GET_PROCESSES_STATS,
                          RunArgs(),
                          j.data.serializer.json.dumps(data)).get_next_result(GET_INFO_TIMEOUT)

        return self._load_json_or_die(result)

    def get_all_processes(self, domain=None, name=None):
        """
        Get stats for all running process at the moment of the call, optionally filter with domain and/or name
        """
        data = {
            'domain': domain,
            'name': name
        }
        all_jobs = list()

        cmd = self.cmd(None,
                       None,
                       CMD_GET_PROCESSES_STATS,
                       RunArgs(),
                       j.data.serializer.json.dumps(data),
                       fanout=True,
                       roles=['*'])

        for job in cmd.iter_results():
            data = self._load_json_or_die(job)
            all_jobs += data

        return all_jobs



    def get_msgs(self, gid, nid, jobid, levels='*', limit=20):
        """
        Query and return log messages stored on agent side.

        :param gid: Grid id
        :param nid: Node id
        :param jobid: Job id
        :param limit: Max number of log messages to return. Note that the agent in anyways will not return
         more than 1000 record
        """

        query = {
            'jobid': jobid,
            'limit': limit,
            'levels': levels,
        }

        result = self.cmd(gid, nid, CMD_GET_MSGS, RunArgs(), j.data.serializer.json.dumps(query)).get_next_result()
        return self._load_json_or_die(result)

    def reverse_tunnel_open(self, local, gid, nid, ip, remote):
        """
        Opens a tunnel from the controller (local) port to the given agent "ip:remote"

        :param local: Port number on controller side
        :param gid: Grid id of target agent
        :param nid: Node id of target agent
        :param ip: Ip to reach from agent side
        :param remote: Remote Ip to reach from agent side
        :return:
        """
        request = {
            'local': int(local),
            'gateway': '%s.%s' % (gid, nid),
            'ip': ip,
            'remote': int(remote)
        }

        args = RunArgs(name='tunnel_open')
        result = self.cmd(None, None, 'controller', args, j.data.serializer.json.dumps(request), roles=['*']).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def reverse_tunnel_close(self, local, gid, nid, ip, remote):
        """
        Close a tunnel from the controller (local) port to the given agent "ip:remote"

        :param local: Port number on controller side
        :param gid: Grid id of target agent
        :param nid: Node id of target agent
        :param ip: Ip to reach from agent side
        :param remote: Remote Ip to reach from agent side
        :return:
        """
        request = {
            'local': int(local),
            'gateway': '%s.%s' % (gid, nid),
            'ip': ip,
            'remote': int(remote)
        }

        args = RunArgs(name='tunnel_close')
        result = self.cmd(None, None, 'controller', args, j.data.serializer.json.dumps(request), roles=['*']).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def reverse_tunnel_list(self):
        """
        List all tunnels opened from the controller to agents
        """

        args = RunArgs(name='tunnel_list')
        result = self.cmd(None, None, 'controller', args, roles=['*']).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def tunnel_open(self, gid, nid, local, gateway, ip, remote):
        """
        Opens a secure tunnel that accepts connection at the agent's local port `local`
        and forwards the received connections to remote agent `gateway` which will
        forward the tunnel connection to `ip:remote`

        Note: The agent will proxy the connection over the agent-controller it recieved this open command from.

        :param gid: Grid id
        :param nid: Node id
        :param local: Agent's local listening port for the tunnel. 0 for dynamic allocation
        :param gateway: The other endpoint `agent` which the connection will be redirected to.
                      This should be the name of the hubble agent.
                      NOTE: if the endpoint is another superangent, it automatically names itself as '<gid>.<nid>'
                      NOTE: there is a special gateway named 'controller' that points to the agent controller
        :param ip: The endpoint ip address on the remote agent network. Note that IP must be a real ip not a host name
                 dns names lookup is not supported.
        :param remote: The endpoint port on the remote agent network
        """

        request = {
            'local': int(local),
            'gateway': gateway,
            'ip': ip,
            'remote': int(remote)
        }

        result = self.cmd(gid, nid, CMD_TUNNEL_OPEN, RunArgs(), j.data.serializer.json.dumps(request)).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def tunnel_close(self, gid, nid, local, gateway, ip, remote):
        """
        Closes a tunnel previously opened by tunnel_open. The `local` port MUST match the
        real open port returned by the tunnel_open function. Otherwise the agent will not match the tunnel and return
        ignore your call.

        Closing a non-existing tunnel is not an error.
        """
        request = {
            'local': int(local),
            'gateway': gateway,
            'ip': ip,
            'remote': int(remote)
        }

        result = self.cmd(gid, nid, CMD_TUNNEL_CLOSE, RunArgs(), j.data.serializer.json.dumps(request)).get_next_result(GET_INFO_TIMEOUT)
        if result.state != 'SUCCESS':
            raise AgentException(result.data)

    def tunnel_list(self, gid, nid):
        """
        Return all opened connection that are open from the agent over the agent-controller it
        received this command from
        """
        result = self.cmd(gid, nid, CMD_TUNNEL_LIST, RunArgs()).get_next_result(GET_INFO_TIMEOUT)
        return self._load_json_or_die(result)

    def get_cmds(self, start=0, count=100):
        """
        Retrieves cmds history. This by default returns the latest 100 cmds. You can
        change the `start` and `count` argument to thinking of the jobs history as a list where
        the most recent job is at index 0

        :param start: Start index to retrieve, default 0
        :param count: Number of jobs to retrieve
        """
        assert count > 0, "Invalid count, must be greater than 0"

        def _rmap(r):
            r = jsonLoads(r)
            return Job(self, r)

        def _map(s):
            j = jsonLoads(s)
            result = self._redis.hgetall('jobresult:%s' % j['id'])

            j['jobs'] = list(map(_rmap, list(result.values())))
            return j

        return list(map(_map, self._redis.lrange('joblog', start, start + count - 1)))
