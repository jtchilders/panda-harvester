import os
import shutil

from pandaharvester.harvestercore import core_utils
from pandaharvester.harvestercore.plugin_base import PluginBase

from act.common.aCTConfig import aCTConfigARC
from act.atlas.aCTDBPanda import aCTDBPanda

# logger
baseLogger = core_utils.setup_logger('act_sweeper')


# plugin for aCT sweeper
class ACTSweeper(PluginBase):
    # constructor
    def __init__(self, **kwarg):
        PluginBase.__init__(self, **kwarg)

        self.log = core_utils.make_logger(baseLogger, 'aCT sweeper', method_name='__init__')
        self.conf = aCTConfigARC()
        self.actDB = aCTDBPanda(self.log, self.conf.get(["db", "file"]))


    # kill a worker
    def kill_worker(self, workspec):
        """ Mark aCT job as tobekilled.

        :param workspec: worker specification
        :type workspec: WorkSpec
        :return: A tuple of return code (True for success, False otherwise) and error dialog
        :rtype: (bool, string)
        """
        # make logger
        tmpLog = core_utils.make_logger(baseLogger, 'workerID={0}'.format(workspec.workerID),
                                        method_name='kill_worker')

        jobSpecs = workspec.get_jobspec_list()
        if not jobSpecs:
            # return true since there is nothing to kill
            return True, ''

        for jobSpec in jobSpecs:
            try:
                self.actDB.updateJob(jobSpec.PandaID, {'actpandastatus': 'tobekilled'})
            except Exception as e:
                tmpLog.error('Failed to cancel job {0} in aCT: {1}'.format(jobSpec.PandaID, str(e)))
            else:
                tmplog.info('Job {0} cancelled in aCT'.format(jobSpec.PandaID))

        return True, ''


    # cleanup for a worker
    def sweep_worker(self, workspec):
        """Clean up access point. aCT takes care of archiving its own jobs.

        :param workspec: worker specification
        :type workspec: WorkSpec
        :return: A tuple of return code (True for success, False otherwise) and error dialog
        :rtype: (bool, string)
        """
        # make logger
        tmpLog = core_utils.make_logger(baseLogger, 'workerID={0}'.format(workspec.workerID),
                                        method_name='sweep_worker')
        # clean up worker directory
        if os.path.exists(workspec.accessPoint):
            shutil.rmtree(workspec.accessPoint)
            tmpLog.info('removed {0}'.format(workspec.accessPoint))
        else:
            tmpLog.info('access point {0} already removed.'.format(workspec.accessPoint))
        # return
        return True, ''
