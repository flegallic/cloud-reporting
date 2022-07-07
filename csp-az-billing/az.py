# -*- coding: utf-8 -*-
import os,sys
from pyzabbix import ZabbixMetric, ZabbixSender
import requests,json,logging,mysql.connector
from mysql.connector import Error
from datetime import date
from dateutil.relativedelta import relativedelta

#env variable
today            = date.today()
endDate          = date(today.year, today.month, 1)
startDate        = endDate + relativedelta(months=-1)
BillingMonth     = startDate.strftime("%Y-%m")
BillingPeriod    = startDate.strftime("%Y-%m-28")
licenseStartDate = (endDate + relativedelta(months=-1)).strftime("%Y-%m-28")
licenseEndDate   = endDate.strftime("%Y-%m-04")
current_date     = date(today.year, today.month, today.day).strftime("%Y-%m-%d")
bill_lines_date  = date(today.year, today.month, today.day).strftime("%Y-%m-15")
Tag           = 'azure'
SaaS          = 'SaaS'
IaaS          = 'IaaS'
ResourceTag   = 'N/A'
ResourceGroup = 'N/A'
Region        = 'N/A'
Task = False
#zabbix monitoring
zabbix_url            = os.getenv('zabbix_url')
zabbix_monitored_host = os.getenv('zabbix_monitored_host')
zabbix_item_key       = ''
zabbix_value          = 0
#logging
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log = '/var/log/az_billing.log'
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
az_url_healthcheck  = 'https://xsp.arrow.com/index.php/api/whoami'
az_customers_url    = 'https://xsp.arrow.com/index.php/api/customers'
az_licences_url     = 'https://xsp.arrow.com/index.php/api/v2/licenses'
az_consumption_url  = 'https://xsp.arrow.com/index.php/api/consumption/license'
az_apikey          = os.getenv('apikey')
az_signature       = os.getenv('signature')
az_headers          = {'apikey': f'{az_apikey}','signature': f'{az_signature}','Content-Type': 'application/json'}

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

###API Healthcheck
def az_api_healthcheck(az_url_healthcheck,az_licences_url):
    r = requests.get(az_url_healthcheck, headers=az_headers)
    if r.status_code == 200:
        logger.info(f"API healthcheck url: {r.status_code}")
    else:
        logger.info(f"API healthcheck url error: {r.status_code}")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)

    r = requests.get(az_licences_url, headers=az_headers)
    if r.status_code == 200:
        logger.info(f"licenses healthcheck url: {r.status_code}")
    else:
        logger.info(f"licenses healthcheck url error: {r.status_code}")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
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
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    try:
        if db and db.is_connected():
            return db
    except Error as e:
        logger.info(e)
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    if db and db.is_connected():
        db.close()

###Check BillingPeriod in database
def db_check(cursor,db_consumption_table,BillingPeriod,Tag,Type):
    result = 0
    cursor.execute(f"""Select BillingPeriod,Tag FROM {db_consumption_table} WHERE Tag like '{Tag}' AND Type like '{Type}'""")
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

###Insert licenses/consumptions into database
def db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod):
    cursor.execute(f"""INSERT INTO {db_consumption_table}(Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,
        Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod,CreatedAt,UpdatedAt)
        VALUES('{Reference}','{Region}','{Service}','{Type}','{Category}','{SubCategory}','{Quantity}','{Unit}','{UnitPrice}','{Amount}',
        '{vatAmount}','{DiscountedAmount}','{Tag}','{ResourceTag}','{ResourceGroup}','{BillingPeriod}','{db_date}','{db_date}')
    """)

###Delete licenses/consumptions from database
def db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag,Type):
    cursor.execute(f"""DELETE FROM {db_consumption_table} WHERE BillingPeriod like '{BillingPeriod}' AND Tag like '{Tag}' AND Type like '{Type}'""")

###Get licenses from Azure (Arrow Tier 2)
def get_licenses(az_licences_url,az_headers,Tag):
    #create new dictionary
    licenses={}
    #counter
    count=0

    az_api_healthcheck(az_url_healthcheck,az_licences_url)
    r = requests.get(az_licences_url, headers=az_headers)
    nb_azure_customers = r.json()
    
    for azure_customers in nb_azure_customers['data']['licenses']:       
        count= count+1
        license_id                    = azure_customers['license_id']
        parent_license_id             = azure_customers['parent_license_id']
        friendlyName                  = azure_customers['friendlyName']
        customer_ref                  = azure_customers['customer_ref']
        state                         = azure_customers['state']
        service_ref                   = azure_customers['service_ref']
        sku                           = azure_customers['sku']
        name                          = azure_customers['name']
        seats                         = azure_customers['seats']
        activeSeats                   = azure_customers['activeSeats']['number']
        activation_datetime           = azure_customers['activation_datetime']
        expiry_datetime               = azure_customers['expiry_datetime']
        orderReference                = azure_customers['order']['reference']
        vendor_license_id             = azure_customers['vendor_license_id']
        periodicity                   = azure_customers['periodicity']
        term                          = azure_customers['term']
        category                      = azure_customers['category']
        program                       = azure_customers['program']
        associatedSubscriptionProgram = azure_customers['associatedSubscriptionProgram']
        priceCurrency                 = azure_customers['price']['currency']
        priceUnitBuy                  = azure_customers['price']['unit']['buy']
        priceUnitSell                 = azure_customers['price']['unit']['sell']
        priceTotalBuy                 = azure_customers['price']['total']['buy']
        priceTotalSell                = azure_customers['price']['total']['sell']

        #add information in dictionary
        licenses[count] = {'license_id':license_id,'parent_license_id':parent_license_id,'friendlyName':friendlyName,'customer_ref':customer_ref,'state':state,'service_ref':service_ref,'sku':sku,'name':name,'seats':seats,'activeSeats':activeSeats,'activation_datetime':activation_datetime,'expiry_datetime':expiry_datetime,'orderReference':orderReference,'vendor_license_id':vendor_license_id,'periodicity':periodicity,'term':term,'category':category,'program':program,'associatedSubscriptionProgram':associatedSubscriptionProgram,'priceCurrency':priceCurrency,'priceUnitBuy':priceUnitBuy,'priceUnitSell':priceUnitSell,'priceTotalBuy':priceTotalBuy,'priceTotalSell':priceTotalSell,'Tag':Tag}                 
    ###only for debugging
    #print(licenses)

    #check if a licenses dictionary is empty
    if not licenses:
        logger.info("An error occurred while processing the licenses dictionary")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    #return information from dictionary
    return licenses

###Get customers
def get_customers(az_customers_url,db_customers_table,db_date,Tag):
    #create new dictionary
    customers_list={}  
    #counter
    count=0

    az_api_healthcheck(az_url_healthcheck,az_licences_url)
    try:
        #get customers from licenses dictionary
        customers = get_licenses(az_licences_url,az_headers,Tag)
    except KeyError:
        logger.info("errors with dictionaries licenses")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    try:
        db     = db_connect(db_host,db_port,db_database,db_user,db_password)
        cursor = db.cursor()
    except KeyError:
        logger.info("errors database connection failed")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    
    for result in customers.values():
        count= count+1

        if result['friendlyName'] == None:
            continue

        Reference   = result['customer_ref']       
        License     = result['license_id']
        TenantName  = result['friendlyName']
        Status      = result['state']
        Created     = result['activation_datetime']
        Created     =(Created[0:10])
        Sku          = result['sku']  
        Category    = result['category']

        #add information in dictionary
        customers_list[Reference]= {'TenantName':TenantName,'License':License,'Reference':Reference,'Tag':Tag,'Status':Status,'Created':Created,'Sku':Sku,'Category':Category}
    ###only for debugging
        #customers_list[count] = {'count':count,'TenantName':TenantName,'License':License,'Reference':Reference,'Tag':Tag,'Status':Status,'Created':Created,'Sku':Sku,'Category':Category}
    #print(customers_list)

    #check if a customers dictionary is empty
    if not customers_list:
        logger.info("An error occurred while processing the customers dictionary")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)

    r = requests.get(az_customers_url, headers=az_headers)
    nb_azure_customers = r.json()
    for azure_customers in nb_azure_customers['data']['customers']:
        Reference = azure_customers['Reference']
        try:
            TenantId   = azure_customers['Details']['TenantID']
        except KeyError:
            TenantId = "N/A"
        if Reference in customers_list:
            customers_list[Reference]['TenantId'] = TenantId

    #get information from dictionnay
    count_customers = 0
    for customer in customers_list.values():
        count_customers = count_customers +1
        Reference   = customer['Reference']
        TenantName  = customer['TenantName']
        TenantId    = customer['TenantId']
        Tag         = customer['Tag']       
        Status      = customer['Status']
        Created     = customer['Created']

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
        logger.info(f"{count_customers} Customers have been updated from Azure")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',0)
    else:
        logger.info(f"Customers have not been updated from Azure")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)

###Get licenses details
def get_licenses_details(db_consumption_table,db_date,BillingPeriod,Tag,Region,ResourceTag,ResourceGroup):
    #create new dictionary
    licenses_consumptions={}
    #counter
    count=0

    az_api_healthcheck(az_url_healthcheck,az_licences_url)
    try:
        #get licenses from licenses dictionary
        licence = get_licenses(az_licences_url,az_headers,Tag)
    except KeyError:
        logger.info("errors with dictionaries licenses")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    try:
        db     = db_connect(db_host,db_port,db_database,db_user,db_password)
        cursor = db.cursor()

        #check licenses from database
        result = db_check(cursor,db_consumption_table,BillingPeriod,Tag,SaaS)
        if result != 0:
            logger.info(f"licenses details ({BillingPeriod}) have already imported from Azure")
            db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag,SaaS)
            db.commit()
            logger.info(f"licenses details ({BillingPeriod}) have been deleted")
    except KeyError:
        logger.info("errors database connection failed")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    
    for result in licence.values():
        #filter category by cloud 
        if "SaaS" in result['category']:
            count = count+1

            if result['state'] == 'active':
                TenantName       = result['friendlyName']
                Reference        = result['customer_ref']
                License          = result['license_id']
                Service          = result['license_id']
                Service          = f'License-{Service}'
                Type             = result['category']
                Category         = result['service_ref']          
                SubCategory      = result['name']
                Quantity         = result['seats']
                Unit             = 'License'
                UnitPrice        = result['priceUnitBuy']
                Amount           = result['priceTotalBuy']
                vatAmount        = result['priceTotalSell']
                DiscountedAmount = result['priceTotalBuy']

                #add information in dictionary
                licenses_consumptions[count] = {'count':count,'TenantName':TenantName,'Reference':Reference,'License':License,'Service':Service,'Type':Type,'Tag':Tag,'Category':Category,'SubCategory':SubCategory,'Quantity':Quantity,'Region':Region,'Unit':Unit,'UnitPrice':UnitPrice,'Amount':Amount,'vatAmount':vatAmount,'DiscountedAmount':DiscountedAmount,'ResourceTag':ResourceTag,'ResourceGroup':ResourceGroup}
    ###only for debugging
    #print(licenses_consumptions)

    #check if a licenses dictionary is empty
    if not licenses_consumptions:
        logger.info("An error occurred while processing the licenses dictionary")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    
    #get information from dictionnay
    for licences in licenses_consumptions.values():
        Reference        = licences['Reference']
        Service          = licences['Service']
        Type             = licences['Type']
        Tag              = licences['Tag']  
        Category         = licences['Category']
        SubCategory      = licences['SubCategory']
        Quantity         = licences['Quantity']
        Region           = licences['Region']
        Unit             = licences['Unit']
        UnitPrice        = licences['UnitPrice']
        Amount           = licences['Amount']
        vatAmount        = licences['vatAmount']
        DiscountedAmount = Amount
        ResourceTag      = licences['ResourceTag']
        ResourceGroup    = licences['ResourceGroup']

        #insert data in database
        try:
            db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod)
            db.commit()
            logger.info(f'{Service} has been added in mysql database')
            Task = True
        except KeyError:
            logger.info('error occurred while inserting data mysql database')
            Task = False

    if Task:
        logger.info(f"licenses details ({BillingPeriod}) have been imported successfully from Azure")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',0)
    else:
        logger.info(f"licenses details ({BillingPeriod}) have not been imported from Azure")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)

###Get azure licenses invoices
def get_azure_licences_invoices(db_consumption_table,db_date,BillingPeriod,Tag,ResourceTag,ResourceGroup):  
    #create new dictionary
    licenses_invoices={}
    #counter
    count=0
    Task=False

    az_api_healthcheck(az_url_healthcheck,az_licences_url)
    try:
        db     = db_connect(db_host,db_port,db_database,db_user,db_password)
        cursor = db.cursor()

        #check licenses from database
        result = db_check(cursor,db_consumption_table,BillingPeriod,Tag,SaaS)
        if result != 0:
            logger.info(f"licenses details ({BillingPeriod}) have already imported from Azure")
            db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag,SaaS)
            db.commit()
            logger.info(f"licenses details ({BillingPeriod}) have been deleted")
    except KeyError:
        logger.info("errors database connection failed")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    
    invoices_url = f"https://xsp.arrow.com/index.php/api/billLines?start_date={licenseStartDate}&end_date={licenseEndDate}&vendors[]=Microsoft&programs[]=MSCSP&categories[]=SAAS"
    res = requests.get(invoices_url, headers=az_headers)
    az_invoices = res.json()

    for invoices in az_invoices['data']['bill_lines']:
        count=count+1
        TenantName          = invoices['customer_name']
        Reference           = 'XSP'+invoices['customer_short_name']
        Service             = 'License-'+invoices['arrow_sku']
        Category            = invoices['item_name']
        SubCategory         = invoices['item_sales_reference']
        Quantity            = invoices['item_original_quantity']
        Region              = invoices['customer_state']
        Unit                = 'License'
        UnitPrice           = invoices['reseller_pro_rated_unit_discounted_price']
        Amount              = invoices['reseller_total_discounted_price']
        vatAmount           = invoices['reseller_total_with_vat_price']
        DiscountedAmount    = invoices['reseller_total_discounted_price']       
        order_creation_date = invoices['order_creation_date']

        #add information in dictionary
        licenses_invoices[count] = {'count':count,'TenantName':TenantName,'Reference':Reference,'Service':Service,'Type':SaaS,'Tag':Tag,'Category':Category,'SubCategory':SubCategory,'Quantity':Quantity,'Region':Region,'Unit':Unit,'UnitPrice':UnitPrice,'Amount':Amount,'vatAmount':vatAmount,'DiscountedAmount':DiscountedAmount,'order_creation_date':order_creation_date,'ResourceTag':ResourceTag,'ResourceGroup':ResourceGroup}
    ###only for debugging
    #print(licenses_invoices)

    #check if a licenses dictionary is empty
    if not licenses_invoices:
        logger.info("An error occurred while processing the licenses dictionary")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)

    #get information from dictionnay
    for licences in licenses_invoices.values():
        TenantName        = licences['TenantName']
        Reference        = licences['Reference']
        Service          = licences['Service']
        Type             = licences['Type']
        Tag              = licences['Tag']  
        Category         = licences['Category']
        SubCategory      = licences['SubCategory']
        Quantity         = licences['Quantity']
        Region           = licences['Region']
        Unit             = licences['Unit']
        UnitPrice        = licences['UnitPrice']
        Amount           = licences['Amount']
        vatAmount        = licences['vatAmount']
        DiscountedAmount = licences['DiscountedAmount']
        ResourceTag      = licences['ResourceTag']
        ResourceGroup    = licences['ResourceGroup']   

        #insert data in database
        try:
            db_insert_consumption(cursor,db_date,db_consumption_table,Reference,Region,Service,Type,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,vatAmount,DiscountedAmount,Tag,ResourceTag,ResourceGroup,BillingPeriod)
            db.commit()
            logger.info(f'License for {TenantName} has been added in mysql database')
            Task = True
        except KeyError:
            logger.info('error occurred while inserting data mysql database')
            Task = False

    if Task:
        logger.info(f"licenses details ({BillingPeriod}) have been imported successfully from Azure")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',0)
    else:
        logger.info(f"licenses details ({BillingPeriod}) have not been imported from Azure")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)

###Get azure consumptions
def get_azure_consumptions(db_consumption_table,db_date,BillingPeriod,Tag,IaaS):
    #create new dictionary
    azure_consumptions={}
    #counter
    count=0
    Task=False

    az_api_healthcheck(az_url_healthcheck,az_licences_url)
    try:
        #get licenses from licenses dictionary
        azure = get_licenses(az_licences_url,az_headers,Tag)
    except KeyError:
        logger.info("errors with dictionaries licenses")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)
    try:
        db     = db_connect(db_host,db_port,db_database,db_user,db_password)
        cursor = db.cursor()

        #check licenses from database
        result = db_check(cursor,db_consumption_table,BillingPeriod,Tag,IaaS)
        if result != 0:
            logger.info(f"usage details (for {BillingPeriod}) have already imported from Azure")
            db_delete_consumption(cursor,db_consumption_table,BillingPeriod,Tag,IaaS)
            db.commit()
            logger.info(f"usage details (for {BillingPeriod}) have been deleted")
    except KeyError:
        logger.info("errors database connection failed")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)

    for result in azure.values():
        #filter category by cloud 
        if "IaaS" in result['category']:          
            TenantName       = result['friendlyName']
            Reference        = result['customer_ref']
            License          = result['license_id']

            consumption_url = az_consumption_url+'/'+License+'?month='+BillingMonth+'&columns[0]=Vendor Ressource SKU&columns[1]=Vendor Product Name&columns[2]=Vendor Meter Category&columns[3]=Vendor Meter Sub-Category&columns[4]=Resource Group&columns[5]=UOM&columns[6]=Country currency code&columns[7]=Level Chargeable Quantity&columns[8]=Region&columns[9]=Resource Name&columns[10]=Country customer unit&columns[11]=Country customer total&columns[12]=Country reseller unit&columns[13]=Country reseller total&columns[14]=Vendor Billing Start Date&columns[15]=Vendor Billing End Date&columns[16]=Cost Center&columns[17]=Project&columns[18]=Environment&columns[19]=Application&columns[20]=Custom Tag&columns[21]=Name&columns[22]=Usage Start date'        
            r = requests.get(consumption_url, headers=az_headers)
            az_consumption = r.json()
            
            #check number of items in headers
            if len(az_consumption['data']['headers']) != 23:
                logger.info("list Monthly multi-groups consumption has been modified! (headers != 23)")
                logger.info("usage details have not been imported from Azure")
                zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
                sys.exit(1)
            else:
                for value in az_consumption['data']['lines']:
                    count = count+1
                    
                    if result['state'] == 'active':
                        VendorRessourceSKU      = value[0]
                        CountryCustomerUnit     = value[1]
                        CountryCustomerTotal    = value[2]
                        CountryResellerUnit     = value[3]
                        CountryResellerTotal    = value[4]
                        VendorBillingStartDate  = value[5]
                        VendorBillingEndDate    = value[6]
                        CostCenter              = value[7]
                        Project                 = value[8]
                        Environment             = value[9]
                        Application             = value[10]
                        VendorProductName       = value[11]
                        ResourceTag             = value[12]
                        Name                    = value[13]
                        UsageStartDate          = value[14]
                        VendorMeterCategory     = value[15]
                        VendorMeterSubCategory  = value[16]
                        ResourceGroup           = value[17]
                        Uom                     = value[18]
                        CountryCurrencyCode     = value[19]
                        LevelChargeableQuantity = value[20]
                        Region                  = value[21]
                        ResourceName            = value[22]

                        #add information in dictionary
                        azure_consumptions[count] = {'count':count,'TenantName':TenantName,'Reference':Reference,'License':License,'Type':IaaS,'Tag':Tag,'VendorRessourceSKU':VendorRessourceSKU,'CountryCustomerUnit':CountryCustomerUnit,'CountryCustomerTotal':CountryCustomerTotal,'CountryResellerUnit':CountryResellerUnit,'CountryResellerTotal':CountryResellerTotal,'VendorBillingStartDate':VendorBillingStartDate,'VendorBillingEndDate':VendorBillingEndDate,'CostCenter':CostCenter,'Project':Project,'Environment':Environment,'Application':Application,'VendorProductName':VendorProductName,'ResourceTag':ResourceTag,'Name':Name,'UsageStartDate':UsageStartDate,'VendorMeterCategory':VendorMeterCategory,'VendorMeterSubCategory':VendorMeterSubCategory,'ResourceGroup':ResourceGroup,'Uom':Uom,'CountryCurrencyCode':CountryCurrencyCode,'LevelChargeableQuantity':LevelChargeableQuantity,'Region':Region,'ResourceName':ResourceName}
    ###only for debugging
    #print(azure_consumptions)

    #check if a consumptions dictionary is empty
    if not azure_consumptions:
        logger.info("An error occurred while processing the consumptions dictionary")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)

    #get information from dictionnay
    for consumptions in azure_consumptions.values():
        Reference        = consumptions['Reference']
        Service          = consumptions['VendorMeterCategory']
        Type             = consumptions['Type']
        Tag              = consumptions['Tag']     
        Category         = consumptions['VendorMeterSubCategory']
        SubCategory      = consumptions['VendorProductName']
        Quantity         = consumptions['LevelChargeableQuantity']
        Region           = consumptions['Region']
        Unit             = consumptions['Uom']
        UnitPrice        = consumptions['CountryResellerUnit']
        Amount           = (Quantity*UnitPrice)
        vatAmount        = Amount + (Amount*0.12)
        DiscountedAmount = Amount              
        ResourceTag      = consumptions['ResourceTag']
        ResourceGroup    = consumptions['ResourceGroup']

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
        logger.info(f"usage details ({BillingPeriod}) have been imported successfully from Azure")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',0)
    else:
        logger.info(f"usage details ({BillingPeriod}) have not been imported from Azure")
        zabbix_connect(zabbix_url,zabbix_monitored_host,'csp.az',1)
        sys.exit(1)


if __name__ == '__main__':
    get_customers(az_customers_url,db_customers_table,db_date,Tag)
    if current_date == bill_lines_date:
        get_azure_licences_invoices(db_consumption_table,db_date,BillingPeriod,Tag,ResourceTag,ResourceGroup)
    else:
        get_licenses_details(db_consumption_table,db_date,BillingPeriod,Tag,Region,ResourceTag,ResourceGroup)
    get_azure_consumptions(db_consumption_table,db_date,BillingPeriod,Tag,IaaS)