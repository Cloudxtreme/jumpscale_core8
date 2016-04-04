from JumpScale import j

from InfluxDumper import InfluxDumper
from MongoDumper import MongoDumper
from ECODumper import ECODumper


class RealitProcess(object):
    """
    """

    def __init__(self):
        self.__jslocation__ = "j.tools.realityprocess"

    def influxpump(self, influxdb, cidr='127.0.0.1', ports=[7777]):
        """
        will dump redis stats into influxdb(s)
        get connections from j.jumpscale.clients...
        """

        InfluxDumper(influxdb, cidr=cidr, ports=ports).start()

    def monogopump(self, cidr='127.0.0.1', ports=[7777]):
        """
        will dump redis stats into influxdb(s)
        get connections from j.jumpscale.clients...
        """

        MongoDumper(cidr=cidr, ports=ports).start()

    def ecodump(self, cidr='127.0.0.1', ports=[7777]):
        """
        Will dump redis ecos into mongodb

        :param cidr:
        :param port:
        :return:
        """
        ECODumper(cidr, ports).start()

    def logsdump(self, cidr='127.0.0.1', ports=[7777]):
        """
        Will dump redis logs into tar files.

        :param cidr:
        :param port:
        :return:
        """
        raise NotImplementedError