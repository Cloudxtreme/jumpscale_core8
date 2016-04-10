
from JumpScale import j
import colored_traceback
colored_traceback.add_hook(always=True)
import functools
import sys
import gevent

class ActionMethodDecorator(object):

    def __init__(self,action=True,force=True,actionshow=True,actionMethodName="", async=False):
        self.logger = j.logger.get('j.atyourservice.actionDecorator')
        self.action=action
        self.force=force
        self.actionshow=actionshow
        self.name=actionMethodName
        self.async = async

    def __call__(self, func):

        def wrapper(*args, **kwargs):
            cm=self.selfobjCode

            #this makes sure we show the action on terminal
            if "actionshow" in kwargs:
                actionshow=kwargs.pop("actionshow")
            else:
                actionshow=self.actionshow

            if "action" in kwargs:
                action=kwargs.pop("action")
            else:
                action=self.action

            if "force" in kwargs:
                force=kwargs.pop("force")
            else:
                force=self.force

            force=True

            if action:
                args=args[1:]
                action0=j.actions.add(action=func, actionRecover=None,args=args,kwargs=kwargs,die=False,stdOutput=True,\
                    errorOutput=True,retry=0,executeNow=False,selfGeneratorCode=cm,force=force,actionshow=actionshow, async=self.async)

                service = action0.selfobj.service
                stateitem = service.state.getSet(action0.name)

                method_hash = service.recipe.actionmethods[action0.name].hash
                hrd_hash = service.hrdhash

                if stateitem.hrd_hash!=hrd_hash or stateitem.actionmethod_hash!=method_hash:
                    stateitem.state="CHANGED"

                if stateitem.state=="OK":
                    print ("NOTHING TODO OK: %s"%stateitem)
                    action0.state="OK"
                    action0.save()
                    return action0.result

                if stateitem.state=="DISABLED":
                    print ("NOTHING TODO DISABLED: %s"%stateitem)
                    action0.state="DISABLED"
                    action0.save()
                    return

                print('service save')
                service.save()
                service.state.reload()

                if not self.async:
                    action0.execute()
                    stateitem.state = action0.state

                    stateitem.last=j.data.time.epoch

                    if action0.state=="OK":
                        stateitem.hrd_hash=hrd_hash
                        stateitem.actionmethod_hash=method_hash
                    else:
                        if "die" in kwargs:
                            if kwargs["die"]==False:
                                return action0
                        msg="**ERROR ACTION**:\n%s"%action0
                        # raise j.exceptions.RuntimeError()
                        print (msg)
                        service.save()
                        sys.exit(1)

                    service.save()

                    return action0.result
            else:
                return func(*args,**kwargs)

        functools.update_wrapper(wrapper, func)
        return wrapper
