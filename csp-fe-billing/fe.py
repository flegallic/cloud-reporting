# -*- coding: utf-8 -*-
import os, sys
from pyzabbix import ZabbixMetric, ZabbixSender
from unicodedata import decimal
from unittest import registerResult
import requests,json,logging,urllib3,mysql.connector
from mysql.connector import Error
from datetime import date
from dateutil.relativedelta import relativedelta
from openpyxl import load_workbook
import csv
urllib3.disable_warnings()

#env variable
today         = date.today()
endDate       = date(today.year, today.month, 1)
startDate     = endDate + relativedelta(months=-1)
fe_month      = startDate.strftime("%Y%m")
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
log = '/var/log/fe_billing.log'
fileHandler = logging.FileHandler("{0}".format(log))
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)
#Get mySQL database credentials
db_host              = os.getenv('db_host')
db_port              = 3306
db_database          = os.getenv('db_database')
db_user              = os.getenv('db_user')
db_password          = os.getenv('db_password')
db_customers_table   = 'csp_accounts'
db_consumption_table = 'csp_consumptions'
db_date              = date(today.year, today.month, today.day).strftime("%Y-%m-%d")
#Get vault credentials
fe_autorizationId    = os.getenv('fe_autorizationId')
fe_token_url         = os.getenv('fe_token_url')
fe_cloudstore_token  = os.getenv('fe_cloudstore_token')
fe_contract_id       = os.getenv('fe_contract_id')
fe_data              = {"grant_type": "client_credentials"}
fe_headers           = {"Accept": "application/json","Authorization": f"{fe_autorizationId}"}
fe_contracts_url     = "https://api.orange.com/cloud/b2b/v1/contracts"
fe_contract_url      = "https://api.orange.com/cloud/b2b/v1/contract"
fe_bills_url         = "https://api.orange.com/cloud/b2b/v1/documents?documentType=comsumptionRatedReports"

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

###Get token access
def get_token(fe_token_url,fe_data,fe_headers):
    r = requests.post(fe_token_url, data=fe_data, headers=fe_headers)
    if r.status_code == 200:
        logger.info(f"token url: {r.status_code}")
        token = r.json()
        fe_orange_token = token['access_token']
        return fe_orange_token
    else:
        logger.info(f"token url error: {r.status_code}")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
        sys.exit(1)

###Get database credentials && connect
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
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
        sys.exit(1)
    try:
        if db and db.is_connected():
            return db
    except Error as e:
        logger.info(e)
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
        sys.exit(1)
    if db and db.is_connected():
        db.close()

###Check BillingPeriod in database
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

###Insert customers into database
def db_insert_customers(cursor,db_date,db_customers_table,Reference,TenantName,TenantId,Tag,Status,Created):
    cursor.execute(f"""INSERT INTO {db_customers_table}(Reference,TenantName,TenantId,Tag,Status,Created,CreatedAt,UpdatedAt)
        VALUES('{Reference}','{TenantName}','{TenantId}','{Tag}','{Status}','{Created}','{db_date}','{db_date}')
        ON DUPLICATE KEY UPDATE TenantName='{TenantName}',TenantId='{TenantId}',Tag='{Tag}',Status='{Status}',Created='{Created}',CreatedAt='{db_date}',UpdatedAt='{db_date}'
    """)
###Insert consumptions into database
def db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod):
    cursor.execute(f"""INSERT INTO {db_consumption_table}(Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,
        Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod,CreatedAt,UpdatedAt)
        VALUES('{Reference}','{Region}','{Service}','{Type}','{Category}','{SubCategory}','{Quantity}','{Unit}','{UnitPrice}','{Amount}',
        '{vatAmount}','{DiscountedAmount}','{Tag}','{ResourceTag}','{ResourceGroup}','{BillingPeriod}','{db_date}','{db_date}')
    """)
###Delete consumptions in database
def db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag):
    cursor.execute(f"""DELETE FROM {db_consumption_table} WHERE BillingPeriod like '{BillingPeriod}' AND Tag like '{Tag}'""")

###Get customers from Flexible engine
def get_customers(fe_token_url,fe_cloudstore_token,fe_data,fe_headers,fe_contracts_url,fe_contract_url,db_customers_table,db_date):
    #create new dictionary
    fe_customers={}
    fe_customers_temp={}
    #counter
    count=0
    task = False

    #connect to db
    db     = db_connect(db_host,db_port,db_database,db_user,db_password)
    cursor = db.cursor()
    
    #get reference from contracts
    token_access = get_token(fe_token_url,fe_data,fe_headers) #get token
    #header parameters
    contracts_headers  = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token_access}",
        "X-API-Key": f"{fe_cloudstore_token}"
    }
    res = requests.get(fe_contracts_url, headers=contracts_headers)
    if res.status_code == 200:
        logger.info(f"FE contracts url: {res.status_code}")
        nb_fe_contracts = res.json()
        for fe_contracts in nb_fe_contracts:
            count = count + 1
            Reference   = fe_contracts['id']

            #add information in new dictionary
            fe_customers_temp[count]= Reference
        #reset counter
        count=0

        ###only for debugging
        #print(fe_customers_temp)
    else:
        logger.info(f"contracts error from flexible engine: {res.status_code}")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
        sys.exit(1)

    #get tenant details from contract
    token_access = get_token(fe_token_url,fe_data,fe_headers) #get token
    for reference in fe_customers_temp.values():
        #header parameters
        contract_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token_access}",
            "X-API-Key": f"{fe_cloudstore_token}",
            "X-ECCS-Contract-Id": f"{reference}"
        }
        res = requests.get(fe_contract_url, headers=contract_headers)
        if res.status_code == 200:
            logger.info(f"FE contract url: {res.status_code}")
            nb_fe_contract = res.json()
            count = count + 1

            tenantName   = nb_fe_contract['name']
            contractType = nb_fe_contract['contractType']
            if 'platformId' not in nb_fe_contracts:
                platformId   = 'None'
            else:
                platformId   = nb_fe_contract['platformId']
            customer     = nb_fe_contract['customer']['id']
            customerName = nb_fe_contract['customer']['name']
            tenantId     = nb_fe_contract['id']
            tag          = (nb_fe_contract['offer']['name']).lower()
            createdAt    = nb_fe_contract['createdAt']
            updatedAt    = nb_fe_contract['updatedAt']
            status       = "active"

            #add information in dictionary
            fe_customers[count] = {'reference':reference,'tenantName':tenantName,'contractType':contractType,'platformId':platformId,'customer':customer,'customerName':customerName,'tenantId':tenantId,'tag':tag,'createdAt':createdAt,'updatedAt':updatedAt,'status':status}
        else:
            logger.info(f"contract error from flexible engine: {res.status_code}")
            pass
            
    ###only for debugging
    #print(fe_customers)

    #get information from dictionnay
    count_customers = 0
    for customer in fe_customers.values():
        count_customers = count_customers +1
        Reference   = customer['reference']
        TenantName  = customer['tenantName']
        TenantId    = customer['tenantId']
        Tag         = customer['tag']
        Status      = customer['status']
        Created     = customer['createdAt']

        #insert data in database
        try:
            db_insert_customers(cursor,db_date,db_customers_table,Reference,TenantName,TenantId,Tag,Status,Created)
            db.commit()
            logger.info(f'{TenantName} added in mysql database')
            task = True
        except KeyError:
            logger.info('error occurred while inserting data mysql database')
            task = False

    if task:
        logger.info(f"{count_customers} Customers have been updated from Flexible engine")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',0)
    else:
        logger.info(f"Customers have not been updated from Flexible engine")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
        sys.exit(1)


###Get monthly consumption from Flexible engine
def get_consumption(fe_token_url,fe_data,fe_bills_url,fe_headers,fe_cloudstore_token,fe_contract_id,db_consumption_table,db_date,fe_month,BillingPeriod):
    #create new dictionary
    fe_consumptions={}
    #counter
    count=0
    #fix tag
    Tag = "flexible engine"
    Task = False
    #current date
    fe_month=str(fe_month)

    #connect to db
    db     = db_connect(db_host,db_port,db_database,db_user,db_password)
    cursor = db.cursor()
    result = db_check(cursor,db_consumption_table,BillingPeriod,Tag)
    if result != 0:
        logger.info(f"usage details (for {BillingPeriod}) have already imported from Flexible engine")
        db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag)
        db.commit()
        logger.info(f"usage details (for {BillingPeriod}) have been deleted")

    #get reference from contracts
    token_access = get_token(fe_token_url,fe_data,fe_headers) #get token
    #header parameters
    fe_headers  = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token_access}",
        "X-API-Key": f"{fe_cloudstore_token}",
        "X-ECCS-Contract-Id": f"{fe_contract_id}"
    }
    res = requests.get(fe_bills_url, headers=fe_headers)
    if res.status_code == 200:
        logger.info(f"FE bills url: {res.status_code}")
        bills_request = res.json()

        for value in bills_request:
            if fe_month in value['period']:
                billsId = value['id']
                consumption_url = f"https://api.orange.com/cloud/b2b/v1/documents/{billsId}/file"
                res = requests.get(consumption_url, headers=fe_headers, allow_redirects=True)
                if res.status_code == 200:

                    open('comsumptionRatedReports.txt', 'wb').write(res.content)
                    with open('comsumptionRatedReports.txt', 'r') as fin:
                        data = fin.read().splitlines(True)
                    with open('comsumptionRatedReports.txt', 'w') as fout:
                        fout.writelines(data[1:])

                    with open("comsumptionRatedReports.txt",'r') as file:
                        for line in file:
                            count = count + 1
                            consumption = line.strip().split(';')

                            #check number of items
                            if len(consumption) != 27:
                                logger.info("list Monthly multi-groups consumption has been modified! (items != 27)")
                                logger.info("usage details have not been imported from Flexible engine")
                                zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
                                sys.exit(1)
                            else:
                            
                                BillingMode           = consumption[0]
                                BeginDate             = consumption[1]
                                EndDate               = consumption[2]
                                ServiceID             = consumption[3]
                                TenantLabel           = consumption[4]
                                Country               = consumption[5]
                                Region                = consumption[6]
                                ServiceCloud          = consumption[7]
                                CodeLabel             = consumption[8]
                                ChargeLabel           = consumption[9]
                                IdResource            = consumption[10]
                                Project               = consumption[11]
                                Tags                  = consumption[12]
                                Quantity              = consumption[13].replace(",",".")
                                BillingUnit           = consumption[14]
                                UnitPrice             = consumption[15].replace(",",".")
                                Amount                = consumption[16].replace(",",".")
                                VolumeDiscount        = consumption[17]
                                DiscountedAmount      = consumption[18].replace(",",".")
                                Currency              = consumption[19]
                                SubsChargeType        = consumption[20]
                                SubsBeginDate         = consumption[21]
                                SubsEndDate           = consumption[22]
                                SubsUpfront           = consumption[23]
                                SubsUpfrontDiscounted = consumption[24]
                                SubsFlavor            = consumption[25]
                                SubsDuration          = consumption[26]

                                #add information in dictionary
                                fe_consumptions[count] = {"count":count,
                                    "BillingMode":BillingMode,"BeginDate":BeginDate,"EndDate":EndDate,"ServiceID":ServiceID,
                                    "TenantLabel":TenantLabel,"Country":Country,"Region":Region,"ServiceCloud":ServiceCloud,
                                    "CodeLabel":CodeLabel,"ChargeLabel":ChargeLabel,"IdResource":IdResource,"Project":Project,
                                    "Tags":Tags,"Quantity":Quantity,"BillingUnit":BillingUnit,"UnitPrice":UnitPrice,
                                    "Amount":Amount,"VolumeDiscount":VolumeDiscount,"DiscountedAmount":DiscountedAmount,"Currency":Currency,
                                    "SubsChargeType":SubsChargeType,"SubsBeginDate":SubsBeginDate,"SubsEndDate":SubsEndDate,"SubsUpfront":SubsUpfront,
                                    "SubsUpfrontDiscounted":SubsUpfrontDiscounted,"SubsFlavor":SubsFlavor,"SubsDuration":SubsDuration}
                        
                    ###only for debugging
                    #print(fe_consumptions)

                    #check if a consumptions dictionary is empty
                    if not fe_consumptions:
                        logger.info("An error occurred while processing the consumptions dictionary")
                        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
                        sys.exit(1)
                    
                    #get information from dictionnay
                    for consumptions in fe_consumptions.values():          
                        Reference        = consumptions['ServiceID']
                        Service          = consumptions['ServiceCloud']
                        Type             = consumptions['BillingMode']
                        Category         = consumptions['CodeLabel']
                        SubCategory      = consumptions['ChargeLabel']
                        Quantity         = consumptions['Quantity']
                        Region           = consumptions['Region']
                        Unit             = consumptions['BillingUnit']
                        UnitPrice        = consumptions['UnitPrice']
                        Amount           = consumptions['Amount']
                        vatAmount        = consumptions['DiscountedAmount']
                        DiscountedAmount = consumptions['DiscountedAmount']            
                        ResourceTag      = consumptions['Tags']
                        ResourceGroup    = consumptions['Project']

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
                        logger.info(f"usage details ({BillingPeriod}) have been imported successfully from Flexible engine")
                        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',0)
                    else:
                        logger.info(f"usage details ({BillingPeriod}) have not been imported from Flexible engine")
                        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
                        sys.exit(1)
    else:
        logger.info(f"bills url error: {res.status_code}")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.fe',1)
        sys.exit(1)


if __name__ == '__main__':
    get_customers(fe_token_url,fe_cloudstore_token,fe_data,fe_headers,fe_contracts_url,fe_contract_url,db_customers_table,db_date)
    get_consumption(fe_token_url,fe_data,fe_bills_url,fe_headers,fe_cloudstore_token,fe_contract_id,db_consumption_table,db_date,fe_month,BillingPeriod)