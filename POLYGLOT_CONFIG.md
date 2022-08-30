# udi-powerwall

## Installation
To run node server user must first select data sources - from Local Power Wall (LOCAL),  Tesla Cloud(CLOUD) or both (BOTH).   Polyglot cloud requires CLOUD connection and will not allow LOCAL.  
Cloud account is needed if ISY is to make changes to Tesla Power Wall - e.g. only enable storm mode when not in peak hours, or control when to use the battery (vs using Tesla's predefined algorithms)

### Polisy/ local Polyglot
Configuration requires 4 steps first time (Polisy/Polyglot - non cloud):
1) First user needs to sepcifiy source of data (LOCAL/CLOUD/BOTH) 
2) Save and restart node


### Polyglot cloud
Cloud utilizes an automatic recaptcha solver from 2captcha.com.  A key is required.  Key can be acquired from https://2captcha.com?from=12244449 (referral to me). It is 3$ for 1000 solves.  One needed once pr node start.

1) Create 3 user defined parameters
    CLOUD_USER_EMAIL
    CLOUD_USER_PASSWORD
    CAPTCHA_APIKEY
    Enter email and password for cloud account using CLOUD_USER_EMAIL and CLOUD_USER_PASSWORD keywords as well as the above captcha key
2) save and stop - start
3) Start and wait 3-5min (needs to compile a few libraries) - solve takes about 30sec to complete 



## Notes 
LOGFILE can be used to generate a daily summary file (csv) in dailyData directory - File must be downloaded with separate tool for now.
