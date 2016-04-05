from JumpScale import j
import gevent
from gevent.pool import Pool
from gevent.queue import Queue


class AYSExecutor:
    def __init__(self, size=4):
        self.logger = j.logger.get('j.atyourservice.geventPool')
        self.consumer_pool = Pool(size)

    def start(self):
        reader = gevent.spawn(self._action_reader)
        reader.join()

    def _action_reader(self):
        self.logger.debug("start actions reader routine")
        while True:
            gevent.sleep(1)

            try:
                runid = j.actions.runid
            except:
                self.logger.debug("runid not set")
                continue

            self.logger.debug('get actions for runid: %s' % runid)
            if runid and runid.startswith('ays_'):

                hash_key = "actions.%s" % runid
                # self.logger.debug("get action for %s" % hash_key)

                for key in j.core.db.hkeys(hash_key):
                    action = j.actions.load_action(runid=runid, key=key)
                    if action.readyForExecute:
                        self.logger.debug('schedule action %s %s' % (runid, key))
                        self.consumer_pool.spawn(self._worker, action)


    def _worker(self, action):
        self.logger.debug("worker start action %s" % (action.name))

        action.execute()
        # if action.state == "ERROR":
        #     raise j.exceptions.RuntimeError("cannot execute run:%s, failed action." % (action.runid))
        #
        # service = action.selfobj.service
        # method_hash = service.recipe.actionmethods[action.name].hash
        # hrd_hash = service.hrdhash
        #
        # stateitem = service.state.getSet(action.name)
        # stateitem.state = action.state
        # stateitem.last = j.data.time.epoch
        #
        # if action.state == "OK":
        #     stateitem.hrd_hash = hrd_hash
        #     stateitem.actionmethod_hash = method_hash
        # else:
        #     # TODO handler async error
        #     # # raise j.exceptions.RuntimeError()
        #     self.logger.error("Error during execution of %s" % action.name)
        #     # print (msg)
        #     service.save()
        #     sys.exit(1)
        #
        # service.save()

if __name__ == '__main__':
    ays_exec = AYSExecutor(size=1)
    ays_exec.start()
