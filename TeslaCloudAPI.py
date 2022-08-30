import time
import json
import hashlib
from datetime import datetime
import requests

from requests_oauth2 import OAuth2BearerToken
import string
import random
#import captcha
from TPWauth import TPWauth

PG_CLOUD_ONLY = False

try:
    import polyinterface
except ImportError:
    import pgc_interface as polyinterface
    PG_CLOUD_ONLY = True

LOGGER = polyinterface.LOGGER

#import LOGGER
class TeslaCloudAPI():

    def __init__(self, email, password, captchaAPIkey):
        
        self.email = email
        self.password = password
        self.captchaAPIkey = ''
        self.captchaAPIkey = captchaAPIkey
        self.loginData = {}
        self.TESLA_URL = "https://owner-api.teslamotors.com"
        self.API = "/api/1"
        self.OPERATING_MODES = ["backup", "self_consumption", "autonomous"]
        self.TOU_MODES = ["economics", "balanced"]
        self.email = email
        self.password = password

        self.daysConsumption = {}
        self.site_info = {}
        self.tokeninfo = {}
        self.touScheduleList = []
        self.connectionEstablished = False
        LOGGER.debug( 'TeslaCloud init user email, password:' + str(self.email)+ ', password')
        self.products = {}
        self.site_id = ''
        #self.battery_id = ''
        self.teslaAuth = TPWauth(self.email, self.password, self.captchaAPIkey)

    def teslaCloudConnect(self ):
        LOGGER.debug('teslaCloudConnect')
        self.tokeninfo = self.teslaAuth.tesla_connect(self.captchaAPIkey)
        return(self.tokeninfo)

    def teslaRetrieveCloudData(self):
        if self.teslaCloudInfo(): 
            self.connectionEstablished = True
            self.site_status = self.teslaGetSiteInfo('site_status')
            self.teslaUpdateCloudData('all')
            
            self.daysMeterSummary = self.teslaCalculateDaysTotals()
            self.touSchedule = self.teslaExtractTouScheduleList()
        else:
            LOGGER.error('Error getting cloud data')
            return(None)
        #LOGGER.debug(self.site_info)    
        if 'tou_settings' in self.site_info:
            if 'optimization_strategy' in self.site_info['tou_settings']:
                self.touMode = self.site_info['tou_settings']['optimization_strategy']
            else:
                self.touMode = None
            if 'schedule' in self.site_info['tou_settings']:
                self.touScheduleList =self.site_info['tou_settings']['schedule']
            else:
                self.touScheduleList = []
        else:
            self.touMode = None
            self.touScheduleList = []
            LOGGER.debug('Tou mode not set')
        #self.battery_status = self.teslaGetBatteryInfo('bat_status') - not used any more 
        #self.battery_info = self.teslaGetBatteryInfo('bat_info') - not used anymore 

    def teslaUpdateCloudData(self, mode):
        if mode == 'critical':
            temp =self.teslaGetSiteInfo('site_live')
            if temp != None:
                self.site_live = temp
                return(True)
        elif mode == 'all':
            temp= self.teslaGetSiteInfo('site_live')
            if temp != None:
                self.site_live = temp
                
            temp = self.teslaGetSiteInfo('site_info')
            if temp != None:
                self.site_info = temp
            
            temp = self.teslaGetSiteInfo('site_history_day')            
            if temp != None:
                self.site_history = temp
                return(True)
            else:
                return(False)
        else:
            temp= self.teslaGetSiteInfo('site_live')
            if temp != None:
                self.site_live = temp
                
            temp = self.teslaGetSiteInfo('site_info')
            if temp != None:
                self.site_info = temp
            
            temp = self.teslaGetSiteInfo('site_history_day')            
            if temp != None:
                self.site_history = temp

            temp = self.teslaGetSiteInfo('site_status')
            if temp != None:
                self.site_status = temp
                return(True)
            else:
                return(False)


    def supportedOperatingModes(self):
        return( self.OPERATING_MODES )

    def supportedTouModes(self):
        return(self.TOU_MODES)

    def teslaCloudInfo(self):
        if self.site_id == '':
            try:
                products = self.teslaGetProduct()
                nbrProducts = products['count']
                for index in range(0,nbrProducts): #Can only handle one power wall setup - will use last one found
                    if 'resource_type' in products['response'][index]:
                        if products['response'][index]['resource_type'] == 'battery':
                            self.site_id ='/'+ str(products['response'][index]['energy_site_id'] )
                            self.products = products['response'][index]
                return(True)
            except Exception as e:
                LOGGER.error('Exception teslaCloudConnect: ' + str(e))
                return(False)
        else:
            return(True)


    def __teslaGetToken(self):
        if self.tokeninfo:
            dateNow = datetime.now()
            tokenExpires = datetime.fromtimestamp(self.tokeninfo['created_at'] + self.tokeninfo['expires_in']- 100)
            if dateNow > tokenExpires:
                LOGGER.info('Renewing token')
                self.tokeninfo = self.teslaAuth.__tesla_refresh_token()
        else:
            LOGGER.info('Getting New Token')
            self.tokeninfo = self.teslaAuth.tesla_connect(self.captchaAPIkey)
            #self.tokeninfo['created_at'] = datetime.now()
        return(self.tokeninfo)


    def __teslaConnect(self):
        return(self.__teslaGetToken())




    def teslaGetProduct(self):
        S = self.__teslaConnect()
        with requests.Session() as s:
            try:
                s.auth = OAuth2BearerToken(S['access_token'])
                r = s.get(self.TESLA_URL + self.API + "/products")
                products = r.json()
                return(products)        
            except Exception as e:
                LOGGER.error('Exception teslaGetProduct: '+ str(e))
                LOGGER.error('Error getting product info')
                return(None)



    def teslaSetOperationMode(self, mode):
        #if self.connectionEstablished:
        S = self.__teslaConnect()
        with requests.Session() as s:
            try:
                s.auth = OAuth2BearerToken(S['access_token'])          
                if mode  in self.OPERATING_MODES:
                    payload = {'default_real_mode': mode}
                    r = s.post(self.TESLA_URL +  self.API+ '/energy_sites'+self.site_id +'/operation', json=payload)        
                    site = r.json()
                    if site['response']['code'] <210:
                        self.site_info['default_real_mode'] = mode
                        return (True)
                    else:
                        return(False)
                else:
                    return(False)
                    #site="wrong mode supplied" + str(mode)
                #LOGGER.debug(site)        
            except Exception as e:
                LOGGER.error('Exception teslaSetOperationMode: ' + str(e))
                LOGGER.error('Error setting operation mode')
                return(False)

    def teslaExtractOperationMode(site_info):
        return(site_info['default_real_mode'])

    def teslaGetSiteInfo(self, mode):
        #if self.connectionEstablished:
        S = self.__teslaConnect()
        with requests.Session() as s:
            try:
                s.auth = OAuth2BearerToken(S['access_token'])            
                if mode == 'site_status':
                    r = s.get(self.TESLA_URL + self.API+ '/energy_sites'+self.site_id +'/site_status')          
                    site = r.json()
                elif mode == 'site_live':
                    r = s.get(self.TESLA_URL + self.API+ '/energy_sites'+self.site_id +'/live_status')          
                    site = r.json()
                elif mode == 'site_info':
                    r = s.get(self.TESLA_URL + self.API+ '/energy_sites'+self.site_id +'/site_info')          
                    site = r.json()            
                elif mode == 'site_history_day':
                    r = s.get(self.TESLA_URL + self.API+ '/energy_sites'+self.site_id +'/history', json={'kind':'power', 'period':'day'}) 
                    site = r.json()                        
                else:
                    #LOGGER.debug('Unknown mode: '+mode)
                    return(None)
                return(site['response'])
            except Exception as e:
                LOGGER.error('Exception teslaGetSiteInfo: ' + str(e))
                LOGGER.error('Error getting data' + str(mode))
                LOGGER.info('Trying to reconnect')
                self.tokeninfo = self.tesla_connect(self.captchaAPIkey)
                return(None)

        
    def teslaGetSolar(self):
        return(self.products['components']['solar'])


    def teslaSetStormMode(self, EnableBool):
        #if self.connectionEstablished:

        S = self.__teslaConnect()
        with requests.Session() as s:
            try:
                s.auth = OAuth2BearerToken(S['access_token'])
                payload = {'enabled': EnableBool}
                r = s.post(self.TESLA_URL +  self.API+ '/energy_sites'+self.site_id +'/storm_mode', json=payload)
                site = r.json()
                if site['response']['code'] <210:
                    self.site_info['user_settings']['storm_mode_enabled'] = EnableBool
                    return (True)
                else:
                    return(False)
            except Exception as e:
                LOGGER.error('Exception teslaSetStormMode: ' + str(e))
                LOGGER.error('Error setting storm mode')
                return(False)


    
    def teslaExtractStormMode(self):
        if self.site_info['user_settings']['storm_mode_enabled']:
            return(1)
        else:
            return(0)


    def teslaSetBackoffLevel(self, backupPercent):
        #if self.connectionEstablished:
        LOGGER.debug('teslaSetBackoffLevel ' + str(backupPercent))
        S = self.__teslaConnect()
        with requests.Session() as s:
            try:
                s.auth = OAuth2BearerToken(S['access_token'])
                if backupPercent >=0 and backupPercent <=100:
                    payload = {'backup_reserve_percent': backupPercent}
                    r = s.post(self.TESLA_URL +  self.API + '/energy_sites'+self.site_id +'/backup', json=payload)        
                    site = r.json()
                    if site['response']['code'] <210:
                        self.site_info['backup_reserve_percent'] = backupPercent
                        return (True)
                    else:
                        return(False)

                else:
                    return(False)
                    #site="Backup Percent out of range 0-100:" + str(backupPercent)
                    #LOGGER.debug(site)   
            except  Exception as e:
                LOGGER.error('Exception teslaSetBackoffLEvel: ' + str(e))
                LOGGER.error('Error setting bacup percent')
                return(False)



    def teslaExtractBackupPercent(self):
        return(self.site_info['backup_reserve_percent'])

    def teslaUpdateTouScheduleList(self, peakMode, weekdayWeekend, startEnd, time_s):
        indexFound = False
        try:
            if weekdayWeekend == 'weekend':
                days = set([6,0])
            else:
                days = set([1,2,3,4,5])

            if self.touScheduleList == None:
                self.touScheduleList = self.teslaExtractTouScheduleList()

            for index in range(0,len(self.touScheduleList)):
                if self.touScheduleList[index]['target']== peakMode and set(self.touScheduleList[index]['week_days']) == days:
                    indexFound = True
                    if startEnd == 'start':
                        self.touScheduleList[index]['start_seconds'] = time_s
                    else:
                        self.touScheduleList[index]['end_seconds'] = time_s
            if not(indexFound):
                temp = {}
                temp['target']= peakMode
                temp['week_days'] = days
                if startEnd == 'start':
                    temp['start_seconds'] = time_s
                else:
                    temp['end_seconds'] = time_s
                self.touScheduleList.append(temp)
                indexFound = True
            return(indexFound)
        except  Exception as e:
                LOGGER.error('Exception teslaUpdateTouScheduleLite: ' + str(e))
                LOGGER.error('Error updating schedule')
                return(False)

    def teslaSetTouSchedule(self, peakMode, weekdayWeekend, startEnd, time_s):
        if self.teslaUpdateTouScheduleList( peakMode, weekdayWeekend, startEnd, time_s):
            self.teslaSetTimeOfUse()

    def  teslaExtractTouTime(self, days, peakMode, startEnd ):
        indexFound = False
        try:
            if days == 'weekend':
                days =set([6,0])
            else:
                days = set([1,2,3,4,5])
            #data = set(self.touScheduleList[0]['week_days'])
            #LOGGER.debug(data == days)
            #LOGGER.debug(self.touScheduleList[0]['target']== peakMode)
            for index in range(0,len(self.touScheduleList)):
                if self.touScheduleList[index]['target']== peakMode and set(self.touScheduleList[index]['week_days']) == days:
                    if startEnd == 'start':
                        value = self.touScheduleList[index]['start_seconds']
                    else:
                        value = self.touScheduleList[index]['end_seconds']
                    indexFound = True
                    return(value)
            if not(indexFound):       
                self.site_info = self.teslaGetSiteInfo('site_info')
                self.touScheduleList = self.teslaExtractTouScheduleList()
                for index in range(0,len(self.touScheduleList)):
                    if self.touScheduleList[index]['target']== peakMode and set(self.touScheduleList[index]['week_days']) == days:
                        if startEnd == 'start':
                            value = self.touScheduleList[index]['start_seconds']
                        else:
                            value = self.touScheduleList[index]['end_seconds']
                        indexFound = True
                        return(value)
            if not(indexFound): 
                LOGGER.debug('No schedule appears to be set')            
                return(-1)
        except  Exception as e:
            LOGGER.error('Exception teslaExtractTouTime ' + str(e))
            LOGGER.error('No schedule idenfied')
            return(-1)


    def teslaSetTimeOfUseMode (self, touMode):
        self.touMode = touMode
        self.teslaSetTimeOfUse()



    def teslaSetTimeOfUse (self):
        #if self.connectionEstablished:
        temp = {}
        S = self.__teslaConnect()
        with requests.Session() as s:
            try:
                s.auth = OAuth2BearerToken(S['access_token'])
                temp['tou_settings'] = {}
                temp['tou_settings']['optimization_strategy'] = self.touMode
                temp['tou_settings']['schedule'] = self.touScheduleList
                payload = temp
                r = s.post(self.TESLA_URL +  self.API+ '/energy_sites'+self.site_id +'/time_of_use_settings', json=payload)
                site = r.json()
                if site['response']['code'] <210:
                    self.site_info['tou_settings']['optimization_strategy'] = self.touMode
                    self.site_info['tou_settings']['schedule']= self.touScheduleList
                    return (True)
                else:
                    return(False)
            except Exception as e:
                LOGGER.error('Exception teslaSetTimeOfUse: ' + str(e))
                LOGGER.error('Error setting time of use parameters')
                return(False)


    def teslaExtractTouMode(self):
        return(self.site_info['tou_settings']['optimization_strategy'])

    def teslaExtractTouScheduleList(self):
        self.touScheduleList = self.site_info['tou_settings']['schedule']
        return( self.touScheduleList )

    def teslaExtractChargeLevel(self):
        return(round(self.site_live['percentage_charged'],2))
        
    def teslaExtractBackoffLevel(self):
        return(round(self.site_info['backup_reserve_percent'],1))

    def teslaExtractGridStatus(self): 
        return(self.site_live['island_status'])


    def teslaExtractSolarSupply(self):
        return(self.site_live['solar_power'])

    def teslaExtractBatterySupply(self):     
        return(self.site_live['battery_power'])

    def teslaExtractGridSupply(self):     
        return(self.site_live['grid_power'])

    def teslaExtractLoad(self): 
        return(self.site_live['load_power'])

    def teslaExtractGeneratorSupply (self):
        return(self.site_live['generator_power'])



    def teslaCalculateDaysTotals(self):
        try:
            data = self.site_history['time_series']
            nbrRecords = len(data)
            index = nbrRecords-1
            dateStr = data[index]['timestamp']
            Obj = datetime.strptime(dateStr, "%Y-%m-%dT%H:%M:%S%z")

            solarPwr = 0
            batteryPwr = 0
            gridPwr = 0
            gridServicesPwr = 0
            generatorPwr = 0
            loadPwr = 0

            prevObj = Obj
            while ((prevObj.day == Obj.day) and  (prevObj.month == Obj.month) and (prevObj.year == Obj.year) and (index >= 1)):

                lastDuration =  prevObj - Obj
                timeFactor= lastDuration.total_seconds()/60/60
                solarPwr = solarPwr + data[index]['solar_power']*timeFactor
                batteryPwr = batteryPwr + data[index]['battery_power']*timeFactor
                gridPwr = gridPwr + data[index]['grid_power']*timeFactor
                gridServicesPwr = gridServicesPwr + data[index]['grid_services_power']*timeFactor
                generatorPwr = generatorPwr + data[index]['generator_power']*timeFactor

                index = index - 1
                prevObj = Obj
                dateStr = data[index]['timestamp']
                Obj = datetime.strptime(dateStr, "%Y-%m-%dT%H:%M:%S%z")
            loadPwr = gridPwr + solarPwr + batteryPwr + gridServicesPwr + generatorPwr

            ySolarPwr = data[index]['solar_power']*timeFactor
            yBatteryPwr = data[index]['battery_power']*timeFactor
            yGridPwr = data[index]['grid_power']*timeFactor
            yGridServicesPwr = data[index]['grid_services_power']*timeFactor
            YGeneratorPwr = data[index]['generator_power']*timeFactor

            prevObj = Obj
            while ((prevObj.day == Obj.day) and  (prevObj.month == Obj.month) and (prevObj.year == Obj.year) and (index >= 1)):
                lastDuration =  prevObj - Obj
                timeFactor= lastDuration.total_seconds()/60/60
                ySolarPwr = ySolarPwr + data[index]['solar_power']*timeFactor
                yBatteryPwr = yBatteryPwr + data[index]['battery_power']*timeFactor
                yGridPwr = yGridPwr + data[index]['grid_power']*timeFactor
                yGridServicesPwr = yGridServicesPwr + data[index]['grid_services_power']*timeFactor
                YGeneratorPwr = YGeneratorPwr + data[index]['generator_power']*timeFactor

                index = index - 1
                prevObj = Obj
                dateStr = data[index]['timestamp']
                Obj = datetime.strptime(dateStr, "%Y-%m-%dT%H:%M:%S%z")

            yLoadPwr = yGridPwr + ySolarPwr + yBatteryPwr + yGridServicesPwr + YGeneratorPwr

            self.daysConsumption = {'solar_power': solarPwr, 'consumed_power': loadPwr, 'net_power':-gridPwr
                                ,'battery_power': batteryPwr ,'grid_services_power': gridServicesPwr, 'generator_power' : generatorPwr
                                ,'yesterday_solar_power': ySolarPwr, 'yesterday_consumed_power': yLoadPwr, 'yesterday_net_power':-yGridPwr
                                ,'yesterday_battery_power': yBatteryPwr ,'yesterday_grid_services_power': yGridServicesPwr, 'yesterday_generator_power' : YGeneratorPwr, }
        
            return(True)
        except Exception as e:
            LOGGER.error('Exception teslaCalculateDaysTotal: ' + str(e))
            LOGGER.error(' Error obtaining time data')

        

    def teslaExtractDaysSolar(self):
        return(self.daysConsumption['solar_power'])
    
    def teslaExtractDaysConsumption(self):     
        return(self.daysConsumption['consumed_power'])

    def teslaExtractDaysGeneration(self):         
        return(self.daysConsumption['net_power'])

    def teslaExtractDaysBattery(self):         
        return(self.daysConsumption['battery_power'])

    def teslaExtractDaysGridServicesUse(self):         
        return(self.daysConsumption['grid_services_power'])

    def teslaExtractDaysGeneratorUse(self):         
        return(self.daysConsumption['generator_power'])  

    def teslaExtractYesteraySolar(self):
        return(self.daysConsumption['yesterday_solar_power'])
    
    def teslaExtractYesterdayConsumption(self):     
        return(self.daysConsumption['yesterday_consumed_power'])

    def teslaExtractYesterdayGeneraton(self):         
        return(self.daysConsumption['yesterday_net_power'])

    def teslaExtractYesterdayBattery(self):         
        return(self.daysConsumption['yesterday_battery_power'])

    def teslaExtractYesterdayGridServiceUse(self):         
        return(self.daysConsumption['yesterday_grid_services_power'])

    def teslaExtractYesterdayGeneratorUse(self):         
        return(self.daysConsumption['yesterday_generator_power'])  

    def teslaExtractOperationMode(self):         
        return(self.site_info['default_real_mode'])
    '''
    def teslaExtractConnectedTesla(self):       
        return(True)

    def teslaExtractRunning(self):  
        return(True)
    '''
    #???
    def teslaExtractPowerSupplyMode(self):  
        return(True)

    def teslaExtractGridServiceActive(self):
        if self.site_live['grid_services_active']: 
            return(1)
        else:
            return(0)