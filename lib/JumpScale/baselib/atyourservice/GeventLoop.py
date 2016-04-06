from JumpScale import j
import gevent
from gevent.pool import Pool
from gevent.queue import Queue


class AYSExecutor:
    def __init__(self, size=4):
        self.logger = j.logger.get('j.atyourservice.geventPool')
        self.consumer_pool = Pool(size)
        self.started = False

    def start(self, wait=True):
        self.logger.info("Starting AYS.")
        self.started = True
        self._reader = gevent.spawn(self._action_reader)
        if wait:
            self._reader.join()

    def stop(self):
        self.logger.info("Stopping AYS. waiting for the running actions tot finish.")
        self.started = False
        self.consumer_pool.join(timeout=10)

    def wait(self):
        self._reader.join()

    def _action_reader(self):
        self.logger.debug("start actions reader routine")

        while self.started:
            gevent.sleep(1)

            try:
                runid = j.actions.runid
            except:
                self.logger.debug("runid not set")
                continue

            if runid and runid.startswith('ays_'):
                # self.logger.debug('get actions for runid: %s' % runid)

                hash_key = "actions.%s" % runid
                # self.logger.debug("get action for %s" % hash_key)

                for key in j.core.db.hkeys(hash_key):
                    action = j.actions.load_action(runid=runid, key=key)
                # for action in j.actions.actions.values():
                    if action.readyForExecute and action.async:
                        if len(action.selfobj.service.getProducersWaiting(action, set())) > 0:
                            continue
                        self.logger.debug('schedule action %s %s' % (runid, action.key))
                        self.consumer_pool.spawn(self._worker, action)


    def _worker(self, action):
        service = action.selfobj.service
        self.logger.debug("worker start action %s for service %s" % (action.name, service.key))

        action.execute()
        if action.state == "ERROR":
            raise j.exceptions.RuntimeError("cannot execute run:%s, failed action." % (action.runid))

        method_hash = service.recipe.actionmethods[action.name].hash
        hrd_hash = service.hrdhash

        stateitem = service.state.getSet(action.name)
        stateitem.state = action.state
        stateitem.last = j.data.time.epoch

        if action.state == "OK":
            stateitem.hrd_hash = hrd_hash
            stateitem.actionmethod_hash = method_hash
        else:
            # TODO handler async error
            # # raise j.exceptions.RuntimeError()
            self.logger.error("Error during execution of %s" % action.name)
            # print (msg)
            service.save()
            sys.exit(1)

        service.save()

if __name__ == '__main__':
    ays_exec = AYSExecutor(size=1)
    ays_exec.start(wait=False)
    gevent.sleep(30)
    ays_exec.stop()
