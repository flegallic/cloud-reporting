# -*- coding: utf-8 -*-
import os,sys
from pyzabbix import ZabbixMetric, ZabbixSender
import requests,json,sys,logging,urllib3,datetime,mysql.connector,boto3
from mysql.connector import Error
from datetime import datetime,date
from dateutil.relativedelta import relativedelta

#env variable
today         = date.today()
endDate       = date(today.year, today.month, 1)
startDate     = endDate + relativedelta(months=-1)
BillingPeriod = startDate.strftime("%Y-%m-28")
#zabbix monitoring
zabbix_url            = os.getenv('zabbix_url')
zabbix_monitored_host = os.getenv('zabbix_monitored_host')
zabbix_item_key       = ''
zabbix_value          = 0
# logging
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log = '/var/log/aws_billing.log'
fileHandler = logging.FileHandler("{0}".format(log))
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)
#Get vault credentials
db_host              = os.getenv('db_host')
db_port              = 3306
db_database          = os.getenv('db_database')
db_user              = os.getenv('db_user')
db_password          = os.getenv('db_password')
db_customers_table   = 'csp_accounts'
db_consumption_table = 'csp_consumptions'
db_date              = date(today.year, today.month, today.day).strftime("%Y-%m-%d")
#Get vault credentials
aws_region_name                = os.getenv('aws_region_name')
aws_oab_access_key_id          = os.getenv('aws_oab_access_key_id')
aws_oab_secret_access_key      = os.getenv('aws_oab_secret_access_key')
aws_oab_roleArn                = os.getenv('aws_oab_roleArn')
aws_oab_roleSessionName        = os.getenv('aws_oab_roleSessionName')
aws_internal_access_key_id     = os.getenv('aws_internal_access_key_id')
aws_internal_secret_access_key = os.getenv('aws_internal_secret_access_key')
aws_internal_roleArn           = os.getenv('aws_internal_roleArn')
aws_internal_roleSessionName   = os.getenv('aws_internal_roleSessionName')
aws_spp_ecm_access_key_id      = os.getenv('aws_spp_ecm_access_key_id')
aws_spp_ecm_secret_access_key  = os.getenv('aws_spp_ecm_secret_access_key')
aws_spp_ecm_roleArn            = os.getenv('aws_spp_ecm_roleArn')
aws_spp_ecm_roleSessionName    = os.getenv('aws_spp_ecm_roleSessionName')
aws_spp_pm_access_key_id       = os.getenv('aws_spp_pm_access_key_id')
aws_spp_pm_secret_access_key   = os.getenv('aws_spp_pm_secret_access_key')
aws_spp_pm_roleArn             = os.getenv('aws_spp_pm_roleArn')
aws_spp_pm_roleSessionName     = os.getenv('aws_spp_pm_roleSessionName')

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

#Get database credentials && connect
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
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.aws',1)
        sys.exit(1)
    try:
        if db and db.is_connected():
            return db
    except Error as e:
        logger.info(e)
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.aws',1)
        sys.exit(1)
    if db and db.is_connected():
        db.close()

#Check BillingPeriod in database
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

#Insert customers in database
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
#Delete consumptions in database
def db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag):
    cursor.execute(f"""DELETE FROM {db_consumption_table} WHERE BillingPeriod like '{BillingPeriod}' AND Tag like '{Tag}'""")

#Get customers from AWS (multi Orga)
def get_customers(
    aws_region_name,aws_oab_access_key_id,aws_oab_secret_access_key,
    aws_oab_roleArn,aws_oab_roleSessionName,aws_internal_access_key_id,
    aws_internal_secret_access_key,aws_internal_roleArn,aws_internal_roleSessionName,
    aws_spp_ecm_access_key_id,aws_spp_ecm_secret_access_key,aws_spp_ecm_roleArn,aws_spp_ecm_roleSessionName,
    aws_spp_pm_access_key_id,aws_spp_pm_secret_access_key,aws_spp_pm_roleArn,aws_spp_pm_roleSessionName,
    db_customers_table,db_date):

    Tag    = 'aws'
    Task   = False
    db     = db_connect(db_host,db_port,db_database,db_user,db_password)
    cursor = db.cursor()
    customers_list = {}

    #DT-Monthly-Billing-Report-AWS-OAB
    sesh = boto3.session.Session(
        aws_access_key_id=f'{aws_oab_access_key_id}',
        aws_secret_access_key=f'{aws_oab_secret_access_key}',
        region_name=f'{aws_region_name}'  
    )
    sts_client = sesh.client('sts')    
    assumed_role_object = sts_client.assume_role(
        RoleArn = f'{aws_oab_roleArn}',
        RoleSessionName=f'{aws_oab_roleSessionName}'
    )
    credentials = assumed_role_object['Credentials']
    clientorga = boto3.client(
        'organizations',
        aws_access_key_id = credentials['AccessKeyId'],
        aws_secret_access_key = credentials['SecretAccessKey'],
        aws_session_token = credentials['SessionToken']
    ) 
    customers_request  = clientorga.list_accounts()
    aws_customers_list = customers_request["Accounts"]
    for customers in aws_customers_list:
        Reference  = customers['Id'] 
        TenantName = customers['Name']   
        Status     = customers['Status']
        Created    = customers['JoinedTimestamp']
        #Tag        = 'aws-oab'
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token
    if customers_request.get("NextToken") is not None:
        aws_token = customers_request["NextToken"]
        customers_request = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Created    = customers['JoinedTimestamp']
            #Tag        = 'aws-oab'
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Tag':Tag,'Created':Created,'Status':Status}

    #DT-Monthly-Billing-Report-Internal
    sesh = boto3.session.Session(
        aws_access_key_id=f'{aws_internal_access_key_id}',
        aws_secret_access_key=f'{aws_internal_secret_access_key}',
        region_name=f'{aws_region_name}'    
    )
    sts_client = sesh.client('sts')    
    assumed_role_object = sts_client.assume_role(
        RoleArn = f'{aws_internal_roleArn}',
        RoleSessionName=f'{aws_internal_roleSessionName}'
    )
    credentials = assumed_role_object['Credentials']
    clientorga = boto3.client(
        'organizations',
        aws_access_key_id = credentials['AccessKeyId'],
        aws_secret_access_key = credentials['SecretAccessKey'],
        aws_session_token = credentials['SessionToken']
    )
    customers_request  = clientorga.list_accounts()
    aws_customers_list = customers_request["Accounts"]
    for customers in aws_customers_list:
        Reference  = customers['Id'] 
        TenantName = customers['Name']   
        Status     = customers['Status']
        Created    = customers['JoinedTimestamp']
        #Tag        = 'aws-internal'
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token
    if customers_request.get("NextToken") is not None:
        aws_token = customers_request["NextToken"]
        customers_request = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Created    = customers['JoinedTimestamp']
            #Tag        = 'aws-internal'
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Tag':Tag,'Created':Created,'Status':Status}

    #DT-Monthly-Billing-Report-SPP-ECM
    sesh = boto3.session.Session(
        aws_access_key_id=f'{aws_spp_ecm_access_key_id}',
        aws_secret_access_key=f'{aws_spp_ecm_secret_access_key}',
        region_name=f'{aws_region_name}' 
    )
    sts_client = sesh.client('sts')    
    assumed_role_object = sts_client.assume_role(
        RoleArn = f'{aws_spp_ecm_roleArn}',
        RoleSessionName=f'{aws_spp_ecm_roleSessionName}'
    )
    credentials = assumed_role_object['Credentials']
    clientorga = boto3.client(
        'organizations',
        aws_access_key_id = credentials['AccessKeyId'],
        aws_secret_access_key = credentials['SecretAccessKey'],
        aws_session_token = credentials['SessionToken']
    )
    customers_request  = clientorga.list_accounts()
    aws_customers_list = customers_request["Accounts"]
    for customers in aws_customers_list:
        Reference  = customers['Id'] 
        TenantName = customers['Name']   
        Status     = customers['Status']
        Created    = customers['JoinedTimestamp']
        #Tag        = 'aws-spp-ecm'
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token
    if customers_request.get("NextToken") is not None:
        aws_token = customers_request["NextToken"]
        customers_request = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Created    = customers['JoinedTimestamp']
            #Tag        = 'aws-spp-ecm'
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Tag':Tag,'Created':Created,'Status':Status}

    #DT-Monthly-Billing-Report-SPP-PM
    sesh = boto3.session.Session(
        aws_access_key_id=f'{aws_spp_pm_access_key_id}',
        aws_secret_access_key=f'{aws_spp_pm_secret_access_key}',
        region_name=f'{aws_region_name}'     
    )
    sts_client = sesh.client('sts')    
    assumed_role_object = sts_client.assume_role(
        RoleArn = f'{aws_spp_pm_roleArn}',
        RoleSessionName=f'{aws_spp_pm_roleSessionName}'
    )
    credentials = assumed_role_object['Credentials']
    clientorga = boto3.client(
        'organizations',
        aws_access_key_id = credentials['AccessKeyId'],
        aws_secret_access_key = credentials['SecretAccessKey'],
        aws_session_token = credentials['SessionToken']
    )
    customers_request  = clientorga.list_accounts()
    aws_customers_list = customers_request["Accounts"]
    for customers in aws_customers_list:
        Reference  = customers['Id'] 
        TenantName = customers['Name']   
        Status     = customers['Status']
        Created    = customers['JoinedTimestamp']
        #Tag        = 'aws-spp-pm'
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token
    if customers_request.get("NextToken") is not None:
        aws_token = customers_request["NextToken"]
        customers_request = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Created    = customers['JoinedTimestamp']
            #Tag        = 'aws-spp-pm'
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Tag':Tag,'Created':Created,'Status':Status}
    
    count_customers = 0
    for aws_customers in customers_list.values():
        count_customers = count_customers +1
        Reference   = aws_customers['Reference']
        TenantName  = aws_customers['TenantName']
        Tag         = aws_customers['Tag']
        Status      = (aws_customers['Status']).lower()
        Created     = aws_customers['Created']
        TenantId    = '' #unavailable

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
        logger.info(f"{count_customers} Customers have been updated from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.aws',0)
    else:
        logger.info(f"Customers have not been updated from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.aws',1)
        sys.exit(1)

#Get monthly consumption from AWS (multi Orga)
def get_consumption(
    aws_oab_access_key_id,aws_oab_secret_access_key,aws_oab_roleArn,aws_oab_roleSessionName,
    aws_internal_access_key_id,aws_internal_secret_access_key,aws_internal_roleArn,aws_internal_roleSessionName,
    aws_spp_ecm_access_key_id,aws_spp_ecm_secret_access_key,aws_spp_ecm_roleArn,aws_spp_ecm_roleSessionName,
    aws_spp_pm_access_key_id,aws_spp_pm_secret_access_key,aws_spp_pm_roleArn,aws_spp_pm_roleSessionName,
    aws_region_name,db_consumption_table,db_date,startDate,endDate,BillingPeriod):

    Tag    = 'aws'
    Task   = False
    db     = db_connect(db_host,db_port,db_database,db_user,db_password)
    cursor = db.cursor()
    result = db_check(cursor,db_consumption_table,BillingPeriod,Tag)
    if result != 0:
        logger.info("Consumption usage details from AWS have already imported")
        db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag)
        db.commit()
        logger.info(f"Consumption usage details have been deleted")

    startDate=str(startDate)
    endDate=str(endDate)
    
    #DT-Monthly-Billing-Report-AWS-OAB
    sesh = boto3.session.Session(
        aws_access_key_id=f'{aws_oab_access_key_id}',
        aws_secret_access_key=f'{aws_oab_secret_access_key}',
        region_name=f'{aws_region_name}'     
    )
    sts_client = sesh.client('sts')    
    assumed_role_object = sts_client.assume_role(
        RoleArn = f'{aws_oab_roleArn}',
        RoleSessionName=f'{aws_oab_roleSessionName}'
    )
    credentials = assumed_role_object['Credentials']
    clientorga = boto3.client(
        'ce',
        aws_access_key_id = credentials['AccessKeyId'],
        aws_secret_access_key = credentials['SecretAccessKey'],
        aws_session_token = credentials['SessionToken']
    )

    ##request by usage
    cost_request = clientorga.get_cost_and_usage(
    TimePeriod={
        'Start': startDate,
        'End': endDate
    },
    Granularity='MONTHLY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {'Type': 'DIMENSION','Key': 'SERVICE'},
        {'Type': 'DIMENSION','Key': 'LINKED_ACCOUNT'}        
    ]
    )
    for value in cost_request['ResultsByTime'][0]['Groups']:
        Reference        = value['Keys'][1]
        Service          = value['Keys'][0]
        Category         = 'N/A'
        SubCategory      = 'N/A'
        Quantity         = 'N/A'
        Region           = 'N/A'
        Unit             = 'N/A'
        UnitPrice        = 'N/A'
        Amount           = value['Metrics']['UnblendedCost']['Amount']
        vatAmount        = Amount
        DiscountedAmount = 'N/A'
        Type='IaaS'
        ResourceTag='N/A'
        ResourceGroup='N/A'

        #insert data in database
        try:
            db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod)                       
            db.commit()
            logger.info(f'Consumptions for AWS-OAB/{Reference} has been added in mysql database')
            Task = True
        except KeyError:
            logger.info('error occurred while inserting data mysql database')
            Task = False

    if Task:
        logger.info(f"usage details (AWS-OAB/{BillingPeriod}) have been imported successfully from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',0)
    else:
        logger.info(f"usage details (AWS-OAB/{BillingPeriod}) have not been imported from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)

    #DT-Monthly-Billing-Report-AWS-Internal
    sesh = boto3.session.Session(
        aws_access_key_id=f'{aws_internal_access_key_id}',
        aws_secret_access_key=f'{aws_internal_secret_access_key}',
        region_name=f'{aws_region_name}'     
    )
    sts_client = sesh.client('sts')    
    assumed_role_object = sts_client.assume_role(
        RoleArn = f'{aws_internal_roleArn}',
        RoleSessionName=f'{aws_internal_roleSessionName}'
    )
    credentials = assumed_role_object['Credentials']
    clientorga = boto3.client(
        'ce',
        aws_access_key_id = credentials['AccessKeyId'],
        aws_secret_access_key = credentials['SecretAccessKey'],
        aws_session_token = credentials['SessionToken']
    )   
    ##request by usage
    cost_request = clientorga.get_cost_and_usage(
    TimePeriod={
        'Start': startDate,
        'End': endDate
    },
    Granularity='MONTHLY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {'Type': 'DIMENSION','Key': 'SERVICE'},
        {'Type': 'DIMENSION','Key': 'LINKED_ACCOUNT'}        
    ]
    )
    for value in cost_request['ResultsByTime'][0]['Groups']:
        Reference        = value['Keys'][1]
        Service          = value['Keys'][0]
        Category         = 'N/A'
        SubCategory      = 'N/A'
        Quantity         = 'N/A'
        Region           = 'N/A'
        Unit             = 'N/A'
        UnitPrice        = 'N/A'
        Amount           = value['Metrics']['UnblendedCost']['Amount']
        vatAmount        = Amount
        DiscountedAmount = 'N/A'
        Type='IaaS'
        ResourceTag='N/A'
        ResourceGroup='N/A'

        #insert data in database
        try:
            db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod)                       
            db.commit()
            logger.info(f'Consumptions for AWS-internal/{Reference} has been added in mysql database')
            Task = True
        except KeyError:
            logger.info('error occurred while inserting data mysql database')
            Task = False

    if Task:
        logger.info(f"usage details (AWS-internal/{BillingPeriod}) have been imported successfully from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',0)
    else:
        logger.info(f"usage details (AWS-internal/{BillingPeriod}) have not been imported from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)


    #DT-Monthly-Billing-Report-AWS-SPP-ECM
    sesh = boto3.session.Session(
        aws_access_key_id=f'{aws_spp_ecm_access_key_id}',
        aws_secret_access_key=f'{aws_spp_ecm_secret_access_key}',
        region_name=f'{aws_region_name}'     
    )
    sts_client = sesh.client('sts')    
    assumed_role_object = sts_client.assume_role(
        RoleArn = f'{aws_spp_ecm_roleArn}',
        RoleSessionName=f'{aws_spp_ecm_roleSessionName}'
    )
    credentials = assumed_role_object['Credentials']
    clientorga = boto3.client(
        'ce',
        aws_access_key_id = credentials['AccessKeyId'],
        aws_secret_access_key = credentials['SecretAccessKey'],
        aws_session_token = credentials['SessionToken']
    )   
    ##request by usage
    cost_request = clientorga.get_cost_and_usage(
    TimePeriod={
        'Start': startDate,
        'End': endDate
    },
    Granularity='MONTHLY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {'Type': 'DIMENSION','Key': 'SERVICE'},
        {'Type': 'DIMENSION','Key': 'LINKED_ACCOUNT'}        
    ]
    )
    for value in cost_request['ResultsByTime'][0]['Groups']:
        Reference        = value['Keys'][1]
        Service          = value['Keys'][0]
        Category         = 'N/A'
        SubCategory      = 'N/A'
        Quantity         = 'N/A'
        Region           = 'N/A'
        Unit             = 'N/A'
        UnitPrice        = 'N/A'
        Amount           = value['Metrics']['UnblendedCost']['Amount']
        vatAmount        = Amount
        DiscountedAmount = 'N/A'
        Type='IaaS'
        ResourceTag='N/A'
        ResourceGroup='N/A'

        #insert data in database
        try:
            db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod)                       
            db.commit()
            logger.info(f'Consumptions for AWS-SPP-ECM/{Reference} has been added in mysql database')
            Task = True
        except KeyError:
            logger.info('error occurred while inserting data mysql database')
            Task = False

    if Task:
        logger.info(f"usage details (AWS-SPP-ECM/{BillingPeriod}) have been imported successfully from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',0)
    else:
        logger.info(f"usage details (AWS-SPP-ECM/{BillingPeriod}) have not been imported from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)

    #DT-Monthly-Billing-Report-AWS-SPP-PM
    sesh = boto3.session.Session(
        aws_access_key_id=f'{aws_spp_pm_access_key_id}',
        aws_secret_access_key=f'{aws_spp_pm_secret_access_key}',
        region_name=f'{aws_region_name}'     
    )
    sts_client = sesh.client('sts')    
    assumed_role_object = sts_client.assume_role(
        RoleArn = f'{aws_spp_pm_roleArn}',
        RoleSessionName=f'{aws_spp_pm_roleSessionName}'
    )
    credentials = assumed_role_object['Credentials']
    clientorga = boto3.client(
        'ce',
        aws_access_key_id = credentials['AccessKeyId'],
        aws_secret_access_key = credentials['SecretAccessKey'],
        aws_session_token = credentials['SessionToken']
    )
    
    ##request by usage
    cost_request = clientorga.get_cost_and_usage(
    TimePeriod={
        'Start': startDate,
        'End': endDate
    },
    Granularity='MONTHLY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {'Type': 'DIMENSION','Key': 'SERVICE'},
        {'Type': 'DIMENSION','Key': 'LINKED_ACCOUNT'}        
    ]
    )
    for value in cost_request['ResultsByTime'][0]['Groups']:
        Reference        = value['Keys'][1]
        Service          = value['Keys'][0]
        Category         = 'N/A'
        SubCategory      = 'N/A'
        Quantity         = 'N/A'
        Region           = 'N/A'
        Unit             = 'N/A'
        UnitPrice        = 'N/A'
        Amount           = value['Metrics']['UnblendedCost']['Amount']
        vatAmount        = Amount
        DiscountedAmount = 'N/A'
        Type='IaaS'
        ResourceTag='N/A'
        ResourceGroup='N/A'

        #insert data in database
        try:
            db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod)                       
            db.commit()
            logger.info(f'Consumptions for AWS-SPP-PM/{Reference} has been added in mysql database')
            Task = True
        except KeyError:
            logger.info('error occurred while inserting data mysql database')
            Task = False

    if Task:
        logger.info(f"usage details (AWS-SPP-PM/{BillingPeriod}) have been imported successfully from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',0)
    else:
        logger.info(f"usage details (AWS-SPP-PM/{BillingPeriod}) have not been imported from AWS")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.apss',1)
        sys.exit(1)


if __name__ == '__main__':
    get_customers(aws_region_name,aws_oab_access_key_id,aws_oab_secret_access_key,aws_oab_roleArn,aws_oab_roleSessionName,aws_internal_access_key_id,aws_internal_secret_access_key,aws_internal_roleArn,aws_internal_roleSessionName,aws_spp_ecm_access_key_id,aws_spp_ecm_secret_access_key,aws_spp_ecm_roleArn,aws_spp_ecm_roleSessionName,aws_spp_pm_access_key_id,aws_spp_pm_secret_access_key,aws_spp_pm_roleArn,aws_spp_pm_roleSessionName,db_customers_table,db_date)
    get_consumption(aws_oab_access_key_id,aws_oab_secret_access_key,aws_oab_roleArn,aws_oab_roleSessionName,aws_internal_access_key_id,aws_internal_secret_access_key,aws_internal_roleArn,aws_internal_roleSessionName,aws_spp_ecm_access_key_id,aws_spp_ecm_secret_access_key,aws_spp_ecm_roleArn,aws_spp_ecm_roleSessionName,aws_spp_pm_access_key_id,aws_spp_pm_secret_access_key,aws_spp_pm_roleArn,aws_spp_pm_roleSessionName,aws_region_name,db_consumption_table,db_date,startDate,endDate,BillingPeriod)
