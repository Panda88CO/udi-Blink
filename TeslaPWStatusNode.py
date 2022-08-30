#!/usr/bin/env python3
PG_CLOUD_ONLY = False

try:
    import polyinterface
except ImportError:
    import pgc_interface as polyinterface
    PG_CLOUD_ONLY = True

#from os import truncate
import sys
import TeslaInfo
import ISYprofile

LOGGER = polyinterface.LOGGER
               
class teslaPWStatusNode(polyinterface.Node):

    def __init__(self, controller, primary, address, name, TPW):
        super().__init__(controller, primary, address, name)

        LOGGER.info('_init_ Tesla Power Wall Status Node')
        self.ISYforced = False
        self.TPW = TPW
        self.address = address 
        self.id = address
        self.name = name
        self.hb = 0

        if not(PG_CLOUD_ONLY):
             self.drivers = []

        self.nodeDefineDone = False
        LOGGER.debug('Start Tesla Power Wall Status Node')  

        self.ISYparams = self.TPW.supportedParamters(self.id)
        #LOGGER.debug ('Node = ISYparams :' + str(self.ISYparams))

        self.ISYcriticalParams = self.TPW.criticalParamters(self.id)
        #LOGGER.debug ('Node = ISYcriticalParams :' + str(self.ISYcriticalParams))
    
        if not(PG_CLOUD_ONLY):
            for key in self.ISYparams:
                info = self.ISYparams[key]
                #LOGGER.debug(key )
                if info != {}:
                    value = self.TPW.getISYvalue(key, self.id)
                    LOGGER.debug('StatusNode: driver' + str(key)+ ' value:' + str(value) + ' uom:' + str(info['uom']) )
                    self.drivers.append({'driver':key, 'value':value, 'uom':info['uom'] })
            LOGGER.debug( 'Status node init - DONE')


    def start(self):                
        self.updateISYdrivers('all')
        #self.reportDrivers()
        self.nodeDefineDone = True


    def stop(self):
        LOGGER.debug('stop - Cleaning up')
    
    def shortPoll(self):
        #No need to poll data - done by Controller
        LOGGER.debug('Tesla Power Wall Status Node shortPoll')
        if self.nodeDefineDone:
            self.updateISYdrivers('critical')
        else:
           LOGGER.info('Status Node: waiting for system/nodes to get created')

            
    def longPoll(self):
        #No need to poll data - done by Controller
        LOGGER.debug('Tesla Power Wall  status Node longPoll')
        if self.nodeDefineDone:
           self.updateISYdrivers('all')
           #self.reportDrivers() 
        else:
           LOGGER.info('Status Node: waiting for system/nodes to get created')

    def updateISYdrivers(self, level):
        LOGGER.debug('StatusNode updateISYdrivers')
        params = []
        if level == 'all':
            params = self.ISYparams
            if params:
                for key in params:
                    info = params[key]
                    if info != {}:
                        value = self.TPW.getISYvalue(key, self.id)
                        #LOGGER.debug('Update all ISY drivers :' + str(key)+ ' ' + info['systemVar']+ ' value:' + str(value) )
                        self.setDriver(key, value, report = True, force = True)      
        elif level == 'critical':
            params = self.ISYcriticalParams
            if params:
                for key in params:
                    value = self.TPW.getISYvalue(key, self.id)
                    #LOGGER.debug('Update critical ISY drivers :' + str(key)+ ' value: ' + str(value) )
                    self.setDriver(key, value, report = True, force = True)        

        else:
           LOGGER.error('Wrong parameter passed: ' + str(level))
  
        #LOGGER.debug('updateISYdrivers - Status node DONE')


    def ISYupdate (self, command):
        LOGGER.debug('ISY-update called')
        if self.TPW.pollSystemData('all'):
            self.updateISYdrivers('all')
            #self.reportDrivers()
 

    commands = { 'UPDATE': ISYupdate, 
                }

    if PG_CLOUD_ONLY:
            drivers= [
                     {'driver': 'GV1', 'value':0, 'uom':51}
                    ,{'driver': 'GV2', 'value':0, 'uom':25}
                    ,{'driver': 'GV3', 'value':0, 'uom':25}
                    ,{'driver': 'GV4', 'value':0, 'uom':25}
                    ,{'driver': 'GV5', 'value':0, 'uom':58}
                    ,{'driver': 'GV6', 'value':0, 'uom':33}
                    ,{'driver': 'GV7', 'value':0, 'uom':33}
                    ,{'driver': 'GV8', 'value':0, 'uom':33}
                    ,{'driver': 'GV9', 'value':0, 'uom':33}
                    ,{'driver': 'GV10', 'value':0, 'uom':33}
                    ,{'driver': 'GV11', 'value':0, 'uom':33}
                    ,{'driver': 'GV12', 'value':0, 'uom':33}
                    ,{'driver': 'GV13', 'value':0, 'uom':33}
                    ,{'driver': 'GV14', 'value':0, 'uom':33}
                    ,{'driver': 'GV15', 'value':0, 'uom':33}
                    ,{'driver': 'GV16', 'value':0, 'uom':33}
                    ,{'driver': 'GV17', 'value':0, 'uom':33}
                    ,{'driver': 'GV18', 'value':0, 'uom':33}
                    ,{'driver': 'GV19', 'value':0, 'uom':33}
            ]


