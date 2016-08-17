import os
import json

from pandaharvester.harvesterconfig import harvester_config
from WorkSpec import WorkSpec


# class for queue config
class QueueConfig:
    def __init__(self,queueName):
        self.queueName = queueName
        # default parameters
        self.mapType = WorkSpec.MT_OneToOne
        self.useJobLateBinding = False



# mapper
class QueueConfigMapper:
    
    # constructor
    def __init__(self):
        self.queueConfig = {}
        # define config file path
        if os.path.isabs(harvester_config.qconf.configFile):
            confFilePath = harvester_config.qconf.configFile
        else:
            # check if in PANDA_HOME
            confFilePath = None
            if 'PANDA_HOME' in os.environ:
                confFilePath = os.path.join(os.environ['PANDA_HOME'],
                                            'etc/panda',
                                            harvester_config.qconf.configFile)
                if not os.path.exists(confFilePath):
                    confFilePath = None
            # look into /etc/panda
            if confFilePath == None:
                confFilePath = os.path.join('/etc/panda',
                                            harvester_config.qconf.configFile)
        # load config from json
        f = open(confFilePath)
        queueConfigJson = json.load(f)
        f.close()
        # set attributes
        for queueName,queueDict in queueConfigJson.iteritems():
            queueConfig = QueueConfig(queueName)
            for key,val in queueDict.iteritems():
                setattr(queueConfig,key,val)
            self.queueConfig[queueName] = queueConfig



    # check if valid queue
    def hasQueue(self,queueName):
        return queueName in self.queueConfig


    
    # get queue config
    def getQueue(self,queueName):
        if not self.hasQueue(queueName):
            return None
        return self.queueConfig[queueName]