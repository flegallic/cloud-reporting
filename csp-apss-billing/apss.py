# -*- coding: utf-8 -*-
import os,sys
from pyzabbix import ZabbixMetric, ZabbixSender
import requests,json,logging,mysql.connector
from mysql.connector import Error
from datetime import date
from dateutil.relativedelta import relativedelta
import urllib.parse

#env variable
today         = date.today()
endDate       = date(today.year, today.month, 1)
startDate     = endDate + relativedelta(months=-1)
apss_month    = startDate.strftime("%Y-%m-27T00:00:00Z")
BillingPeriod = startDate.strftime("%Y-%m-28")
#zabbix monitoring
zabbix_url            = os.getenv('zabbix_url')
zabbix_monitored_host = os.getenv('zabbix_monitored_host')
zabbix_item_key       = ''
zabbix_value          = 0
#logging
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log = '/var/log/apss_billing.log'
fileHandler = logging.FileHandler("{0}".format(log))
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)
#get mySQL database credentials
db_host              = os.getenv('db_host')
db_port              = 3306
db_database          = os.getenv('db_database')
db_user              = os.getenv('db_user')
db_password          = os.getenv('db_password')
db_customers_table   = 'csp_accounts'
db_consumption_table = 'csp_consumptions'
db_date              = date(today.year, today.month, today.day).strftime("%Y-%m-%d")
#get vault credentials
apss_tenantId          = os.getenv('apss_tenantId')
apss_appId             = os.getenv('apss_appId')
apss_appSecret         = urllib.parse.quote(os.getenv('apss_appSecret'), safe='')
apss_sharedTenantId    = os.getenv('apss_sharedTenantId')
apss_token_url         = f'https://login.microsoftonline.com/{apss_tenantId}/oauth2/token'
apss_data              = f'grant_type=client_credentials&client_id={apss_appId}&client_secret={apss_appSecret}&resource=https://graph.windows.net'
apss_subscriptions_url = f'https://api.partnercenter.microsoft.com/v1/customers/{apss_sharedTenantId}/subscriptions'
apss_customers_url     = f'https://api.partnercenter.microsoft.com/v1/customers/{apss_sharedTenantId}'
apss_invoices_url      = f'https://api.partnercenter.microsoft.com/v1/invoices/'
token_request_headers = {'Content-type': 'application/x-www-form-urlencoded; charset=utf-8'}

#zabbix connection setings
def zabbix_connect(zabbix_url,zabbix_monitored_host,zabbix_item_key,zabbix_value):
    try:
        zabbix_server = ZabbixSender(zabbix_url, 10051)
        logger.info(zabbix_server)
        # Send metrics to zabbix trapper
        packet = [ZabbixMetric(zabbix_monitored_host, zabbix_item_key, zabbix_value)]
        zabbix_result = zabbix_server.send(packet)
        logger.info(zabbix_result)
    except KeyError:
        logger.info(f"an error occurred when processing zabbix url")
        sys.exit(1)

#get token
apss_req           = requests.post(apss_token_url, data=apss_data, headers=token_request_headers)
apss_token_request = apss_req.json()
try:
    apss_token = apss_token_request['access_token']
except KeyError:
    logger.info(f"an error occurred when processing zabbix url")
    zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
    sys.exit(1)
apss_headers = {"Authorization": f"Bearer {apss_token}","Accept": "application/json"}

#get database credentials && connect
def db_connect(host,port,database,user,password):
    db = None
    try:
        db = mysql.connector.connect(
            host     = host,
            port     = port,
            database = database,
            user     = user,
            password = password
        )                 
    except Error as e:
        logger.info(e)
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)
    try:
        if db and db.is_connected():
            return db
    except Error as e:
        logger.info(e)
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)
    if db and db.is_connected():
        db.close()

#check BillingPeriod in database
def db_check(cursor,db_consumption_table,BillingPeriod,Tag):
    result = 0
    cursor.execute(f"""Select BillingPeriod,Tag FROM {db_consumption_table} WHERE Tag like '{Tag}'""")
    dbRequest = cursor.fetchall()
    for value in dbRequest:
        if BillingPeriod == str(value[0]):
            result = 1
        else:
            result = 0
    return result

#insert customers in database
def db_insert_customers(cursor,db_date,db_customers_table,Reference,TenantName,TenantId,Tag,Status,Created):
    cursor.execute(f"""INSERT INTO {db_customers_table}(Reference,TenantName,TenantId,Tag,Status,Created,CreatedAt,UpdatedAt)
        VALUES('{Reference}','{TenantName}','{TenantId}','{Tag}','{Status}','{Created}','{db_date}','{db_date}')
        ON DUPLICATE KEY UPDATE TenantName='{TenantName}',TenantId='{TenantId}',Tag='{Tag}',Status='{Status}',Created='{Created}',
        CreatedAt='{db_date}',UpdatedAt='{db_date}'
    """)
###Insert consumptions into database
def db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod):
    cursor.execute(f"""INSERT INTO {db_consumption_table}(Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,
        Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod,CreatedAt,UpdatedAt)
        VALUES('{Reference}','{Region}','{Service}','{Type}','{Category}','{SubCategory}','{Quantity}','{Unit}','{UnitPrice}','{Amount}',
        '{vatAmount}','{DiscountedAmount}','{Tag}','{ResourceTag}','{ResourceGroup}','{BillingPeriod}','{db_date}','{db_date}')
    """)
#delete consumptions in database
def db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag):
    cursor.execute(f"""DELETE FROM {db_consumption_table} WHERE BillingPeriod like '{BillingPeriod}' AND Tag like '{Tag}'""")

#get customers from APPS (Azure shared services)
def get_customers(apss_subscriptions_url,apss_headers,apss_sharedTenantId,db_customers_table,db_date):

    #create new dictionary
    accounts={}
    #counter
    count=0
    Task=False
    #csp tag
    Tag = "apss"

    db     = db_connect(db_host,db_port,db_database,db_user,db_password)
    cursor = db.cursor()

    r = requests.get(apss_subscriptions_url, headers=apss_headers)
    if r.status_code == 200:
        logger.info(f"APPS subscription url: {r.status_code}")
        r.encoding = 'utf-8-sig'
        nb_apss_subscriptions = json.loads(r.text)
        for apss_subscriptions in nb_apss_subscriptions['items']:
            count = count +1
            if apss_subscriptions['offerId'] == "MS-AZR-159P":           
                Reference  = apss_subscriptions['entitlementId']
            else:
                Reference  = apss_subscriptions['id']
            TenantName = apss_subscriptions['friendlyName']
            Status     = apss_subscriptions['status']
            if Status == 'active':
                Created    = apss_subscriptions['creationDate'][:10]
                TenantId   = apss_sharedTenantId

                #add information in dictionary
                accounts[count] = {'Reference':Reference,'TenantName':TenantName,'Tag':Tag,'Status':Status,'Created':Created,'TenantId':TenantId}                 
        ###only for debugging
        #print(accounts)

        #check if a accounts dictionary is empty
        if not accounts:
            logger.info("An error occurred while processing the licenses dictionary")
            zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
            sys.exit(1)
        
        #get information from dictionnay
        count_customers = 0
        for result in accounts.values():
            count_customers = count_customers +1
            Reference  = result['Reference']
            TenantName = result['TenantName']
            Tag        = result['Tag']
            Status     = result['Status']
            Created    = result['Created']
            TenantId   = result['TenantId']

            #insert data in database
            try:
                db_insert_customers(cursor,db_date,db_customers_table,Reference,TenantName,TenantId,Tag,Status,Created)
                db.commit()
                logger.info(f'{TenantName} has been added or updated in mysql database')
                Task = True
            except KeyError:
                logger.info('error occurred while inserting data mysql database')
                Task = False

        if Task:
            logger.info(f"{count_customers} Customers have been updated from APSS")
            zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',0)
        else:
            logger.info(f"Customers have not been updated from APSS")
            zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
            sys.exit(1)
    else:
        logger.info(f"APPS subscription url error: {r.status_code}")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)


#get monthly consumption from APPS (Azure shared services)
def get_consumption(apss_invoices_url,apss_headers,db_consumption_table,db_date,apss_month,BillingPeriod):

    #create new dictionary
    consumptions={}
    #counter
    count=0
    Task=False
    #csp tag
    Tag = "apss"

    try:
        db     = db_connect(db_host,db_port,db_database,db_user,db_password)
        cursor = db.cursor()

        #check consumptions from database
        result = db_check(cursor,db_consumption_table,BillingPeriod,Tag)
        if result != 0:
            logger.info(f"usage details (for {BillingPeriod}) have already imported from APSS")
            db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag)
            db.commit()
            logger.info(f"usage details (for {BillingPeriod}) have been deleted")
    except KeyError:
        logger.info("errors database connection failed")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)
    
    apss_month=str(apss_month)
    r = requests.get(apss_invoices_url, headers=apss_headers)
    if r.status_code == 200:
        logger.info(f"APPS invoices url: {r.status_code}")
        r.encoding='utf-8-sig'
        data = json.loads(r.text)

        for consumption in data['items']:
            billingId = consumption['id'] ## billingId == internal contract
            billingPeriodEndDate = consumption['billingPeriodEndDate']

            if billingPeriodEndDate == apss_month:
                consumption_url = apss_invoices_url+'Recurring-'+billingId+'/lineitems/Azure/BillingLineItems'
                r = requests.get(consumption_url, headers=apss_headers)

                if r.status_code == 200:
                    logger.info(f"APPS consumption url: {r.status_code}")
                    r.encoding='utf-8-sig'
                    data = json.loads(r.text)

                    for value in data['items']:
                        count = count+1               
                        postTaxEffectiveRate = value['postTaxEffectiveRate']
                        Reference            = value['subscriptionId']
                        Service              = value['serviceName']
                        Category             = value['serviceType']
                        SubCategory          = value['resourceName']
                        Quantity             = value['consumedQuantity']
                        Region               = value['region']
                        Unit                 = value['unit']
                        UnitPrice            = 'N/A'
                        Amount               = value['postTaxTotal']
                        DiscountedAmount     = Amount

                        #add information in dictionary
                        consumptions[count] = {'Reference':Reference,'Region':Region,'Service':Service,'Category':Category,'SubCategory':SubCategory,'Quantity':Quantity,'Unit':Unit,'UnitPrice':UnitPrice,'Amount':Amount,'DiscountedAmount':DiscountedAmount,'Tag':Tag}
                else:
                    logger.info(f"APPS consumption url error: {r.status_code}")
                    zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
                    sys.exit(1)
        ###only for debugging
        #print(consumptions)

        #check if a consumptions dictionary is empty
        if not consumptions:
            logger.info("An error occurred while processing the consumptions dictionary")
            zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
            sys.exit(1)
        
        #get information from dictionnay
        for result in consumptions.values():          
            Reference        = result['Reference']
            Service          = result['Service']
            Type             = "IaaS"
            Tag              = result['Tag']     
            Category         = result['Category']
            SubCategory      = result['SubCategory']
            Quantity         = result['Quantity']
            Region           = result['Region']
            Unit             = result['Unit']
            UnitPrice        = result['UnitPrice']
            Amount           = result['UnitPrice']
            vatAmount        = Amount
            DiscountedAmount = result['DiscountedAmount']            
            ResourceTag      = 'N/A'
            ResourceGroup    = 'N/A'
            
            #insert data in database
            try:
                db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod)                       
                db.commit()
                logger.info(f'Consumptions for {Reference} has been added in mysql database')
                Task = True
            except KeyError:
                logger.info('error occurred while inserting data mysql database')
                Task = False

        if Task:
            logger.info(f"usage details ({BillingPeriod}) have been imported successfully from APSS")
            zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',0)
        else:
            logger.info(f"usage details ({BillingPeriod}) have not been imported from APSS")
            zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
            sys.exit(1)
    else:
        logger.info(f"APPS invoices url error: {r.status_code}")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)
        

if __name__ == '__main__':
    get_customers(apss_subscriptions_url,apss_headers,apss_sharedTenantId,db_customers_table,db_date)
    get_consumption(apss_invoices_url,apss_headers,db_consumption_table,db_date,apss_month,BillingPeriod)
