## AWS billing reports

### Authentication
You must login to call Amazon API gateway. \
The examples in this section use the (non-working) credentials in the following table.
<table>
  <tr>
    <th>Parameter</th>
    <th>Value</th>
  </tr>
  <tr>
    <td>aws_access_key_id</td>
    <td>AKIAIOSFODNN7_EXAMPLE</td>
  </tr>
  <tr>
    <td>aws_secret_access_key</td>
    <td>wJalrXUtnFEMI/K7MDENG/bPxRfiCY_EXAMPLE</td>
  </tr>
  <tr>
    <td>region_name</td>
    <td>us-east-xxx</td>
  </tr>
  <tr>
    <td>RoleArn</td>
    <td>arn:aws:iam::account-of-role-to-assume:role/name-of-role</td>
  </tr>
  <tr>
    <td>RoleSessionName</td>
    <td>AssumeRoleSessionName</td>
  </tr>
</table>

### python script example
minimum version : Python 3.6.x
```python
# -*- coding: utf-8 -*-
import config
import requests,json,logging,urllib3,datetime,mysql.connector,boto3
from mysql.connector import Error
from datetime import datetime,date
from dateutil.relativedelta import relativedelta
```

### Environment variable
- Variables should be adapted for your specific context
```python
today         = date.today()
endDate       = date(today.year, today.month, 1)
startDate     = endDate + relativedelta(months=-1)
BillingPeriod = startDate.strftime("%Y-%m-28")
log = "/var/log/aws_billing.log"
logging.basicConfig(filename=log,level=logging.DEBUG,format='%(asctime)s %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
```

### VAULT AppRole authentication method
```python
vault_role_id     = config.vault_role_id
vault_secret_id   = config.vault_secret_id
vault_login_path  = config.vault_login_path
suivi_secret_path = config.suivi_secret_path
aws_secret_path    = config.aws_secret_path
```

```python
#Get vault token authentification with AppRole
def get_aws_vault_credentials(vault_role_id,vault_secret_id,vault_login_path,aws_secret_path):
    ##if Orange CA not installed
    urllib3.disable_warnings()

    payload = {"role_id": vault_role_id, "secret_id": vault_secret_id}
    r = requests.post(vault_login_path, json=payload, verify=False)
    token = r.json()['auth']['client_token']
    r = requests.get(aws_secret_path, headers={"X-Vault-Token":token}, verify=False)
    if r.status_code == 200:
        logging.info(f"Vault token: {r.status_code}")
        vault_result = r.json()
        return vault_result
    else:
        logging.info(f"vault token error: {r.status_code}")
```

### Get aws url + credentials
```python
vault_result = get_aws_vault_credentials(vault_role_id,vault_secret_id,vault_login_path,aws_secret_path)
aws_region_name                = vault_result['data']['aws_region_name']
aws_oab_access_key_id          = vault_result['data']['aws_oab_access_key_id']
aws_oab_secret_access_key      = vault_result['data']['aws_oab_secret_access_key']
aws_oab_roleArn                = vault_result['data']['aws_oab_roleArn']
aws_oab_roleSessionName        = vault_result['data']['aws_oab_roleSessionName']
aws_internal_access_key_id     = vault_result['data']['aws_internal_access_key_id']
aws_internal_secret_access_key = vault_result['data']['aws_internal_secret_access_key']
aws_internal_roleArn           = vault_result['data']['aws_internal_roleArn']
aws_internal_roleSessionName   = vault_result['data']['aws_internal_roleSessionName']
aws_spp_ecm_access_key_id      = vault_result['data']['aws_spp_ecm_access_key_id']
aws_spp_ecm_secret_access_key  = vault_result['data']['aws_spp_ecm_secret_access_key']
aws_spp_ecm_roleArn            = vault_result['data']['aws_spp_ecm_roleArn']
aws_spp_ecm_roleSessionName    = vault_result['data']['aws_spp_ecm_roleSessionName']
aws_spp_pm_access_key_id       = vault_result['data']['aws_spp_pm_access_key_id']
aws_spp_pm_secret_access_key   = vault_result['data']['aws_spp_pm_secret_access_key']
aws_spp_pm_roleArn             = vault_result['data']['aws_spp_pm_roleArn']
aws_spp_pm_roleSessionName     = vault_result['data']['aws_spp_pm_roleSessionName']
```

### Get Customers with RoleArn(IAM)
```python
def get_customers(
    aws_region_name,aws_oab_access_key_id,aws_oab_secret_access_key,
    aws_oab_roleArn,aws_oab_roleSessionName,aws_internal_access_key_id,
    aws_internal_secret_access_key,aws_internal_roleArn,aws_internal_roleSessionName,
    aws_spp_ecm_access_key_id,aws_spp_ecm_secret_access_key,aws_spp_ecm_roleArn,aws_spp_ecm_roleSessionName,
    aws_spp_pm_access_key_id,aws_spp_pm_secret_access_key,aws_spp_pm_roleArn,aws_spp_pm_roleSessionName):

    Tag        = 'aws'
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
        Email      = customers['Email']
        Created    = customers['JoinedTimestamp']
        #Tag        = 'aws-oab'
        Contact    = ''
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token
    if customers_request.get("NextToken") is not None:
        aws_token = customers_request["NextToken"]
        customers_request = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Email      = customers['Email']
            Created    = customers['JoinedTimestamp']
            #Tag        = 'aws-oab'
            Contact    = '' #unavailable
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}

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
        Email      = customers['Email']
        Created    = customers['JoinedTimestamp']
        #Tag        = 'aws-internal'
        Contact    = ''
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token
    if customers_request.get("NextToken") is not None:
        aws_token = customers_request["NextToken"]
        customers_request = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Email      = customers['Email']
            Created    = customers['JoinedTimestamp']
            #Tag        = 'aws-internal'
            Contact    = '' #unavailable
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}

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
        Email      = customers['Email']
        Created    = customers['JoinedTimestamp']
        #Tag        = 'aws-spp-ecm'
        Contact    = ''
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token
    if customers_request.get("NextToken") is not None:
        aws_token = customers_request["NextToken"]
        customers_request = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Email      = customers['Email']
            Created    = customers['JoinedTimestamp']
            #Tag        = 'aws-spp-ecm'
            Contact    = '' #unavailable
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}

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
        Email      = customers['Email']
        Created    = customers['JoinedTimestamp']
        #Tag        = 'aws-spp-pm'
        Contact    = ''
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token
    if customers_request.get("NextToken") is not None:
        aws_token = customers_request["NextToken"]
        customers_request = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Email      = customers['Email']
            Created    = customers['JoinedTimestamp']
            #Tag        = 'aws-spp-pm'
            Contact    = '' #unavailable
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}

    for aws_customers in customers_list.values():
        Reference   = aws_customers['Reference']
        TenantName  = aws_customers['TenantName']
        Contact     = aws_customers['Contact']
        Email       = aws_customers['Email']
        Tag         = aws_customers['Tag']
        Status      = (aws_customers['Status']).lower()
        Created     = aws_customers['Created']
        Id          = '' #unavailable

        print(Reference,TenantName,Contact,Email,Tag,Status,Created,Id)
    logging.info("AWS Customers have been updated")
```

### Get monthly consumption from AWS with RoleArn(IAM)
```python
def get_consumption(
    aws_oab_access_key_id,aws_oab_secret_access_key,aws_oab_roleArn,aws_oab_roleSessionName,
    aws_internal_access_key_id,aws_internal_secret_access_key,aws_internal_roleArn,aws_internal_roleSessionName,
    aws_spp_ecm_access_key_id,aws_spp_ecm_secret_access_key,aws_spp_ecm_roleArn,aws_spp_ecm_roleSessionName,
    aws_spp_pm_access_key_id,aws_spp_pm_secret_access_key,aws_spp_pm_roleArn,aws_spp_pm_roleSessionName,
    aws_region_name,startDate,endDate,BillingPeriod):

    Tag    = 'aws'
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
        DiscountedAmount = 'N/A'

        print(Reference,Region,Service,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,DiscountedAmount,Tag,BillingPeriod) 
    logging.info("Consumption usage details from AWS-OAB have been imported")


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
        DiscountedAmount = 'N/A'

        print(Reference,Region,Service,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,DiscountedAmount,Tag,BillingPeriod) 
    logging.info("Consumption usage details from AWS-internal have been imported")


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
        DiscountedAmount = 'N/A'

        print(Reference,Region,Service,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,DiscountedAmount,Tag,BillingPeriod) 
    logging.info("Consumption usage details from AWS-SPP-ECM have been imported")

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
        DiscountedAmount = 'N/A'

        print(Reference,Region,Service,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,DiscountedAmount,Tag,BillingPeriod)                    
    logging.info("Consumption usage details from AWS-SPP-PM have been imported")
```


### DEPRECIATED - Get Customers without RoleArn(IAM)
```python
def get_csp_customers(aws_access_key_id,aws_secret_access_key,aws_region_name):
    print('Please wait a moment...(this can again take several minutes)')

    customers_list = {}
    boto3session = boto3.Session(region_name=f'{aws_region_name}',aws_access_key_id=f'{aws_access_key_id}',aws_secret_access_key=f'{aws_secret_access_key}')
    clientorga = boto3session.client('organizations')
    ###customers without token
    customers_request  = clientorga.list_accounts()
    aws_customers_list = customers_request["Accounts"]
    for customers in aws_customers_list:
        Reference  = customers['Id'] 
        TenantName = customers['Name']   
        Status     = customers['Status']
        Email      = customers['Email']
        Created    = customers['JoinedTimestamp']
        Tag        = 'aws'
        Contact    = ''
        customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}
    ###customers with token (if exist)
    if customers_request.get("NextToken") is not None:
        customers_request  = clientorga.list_accounts()
        aws_token = customers_request["NextToken"]
        customers_request  = clientorga.list_accounts(NextToken=aws_token)
        aws_customers_list = customers_request["Accounts"]
        for customers in aws_customers_list:      
            Reference  = customers['Id'] 
            TenantName = customers['Name']   
            Status     = customers['Status']
            Email      = customers['Email']
            Created    = customers['JoinedTimestamp']
            Tag        = 'aws'
            Contact    = '' #unavailable
            customers_list[Reference] = {'TenantName':TenantName,'Reference':Reference,'Contact':Contact,'Email':Email,'Tag':Tag,'Created':Created,'Status':Status}
        for aws_customers in customers_list.values():
            Reference   = aws_customers['Reference']
            TenantName  = aws_customers['TenantName']
            Contact     = aws_customers['Contact']
            Email       = aws_customers['Email']
            Tag         = aws_customers['Tag']
            Status      = (aws_customers['Status']).lower()
            Created     = aws_customers['Created']
            Id          = '' #unavailable

            ### print()
```

### DEPRECIATED - Get monthly consumption from AWS without RoleArn(IAM)
```python
def get_aws_invoices(aws_access_key_id,aws_secret_access_key,aws_region_name,startDate,endDate,BillingPeriod)
    print('Please wait a moment...(this can again take several minutes)')

    startDate=str(startDate)
    endDate=str(endDate)
    boto3session = boto3.Session(region_name=f'{aws_region_name}',aws_access_key_id=f'{aws_access_key_id}',aws_secret_access_key=f'{aws_secret_access_key}')
    clientorga = boto3session.client('organizations')
    clientcostexplorer = boto3session.client('ce')
    invoices_list = {}
    ##request by service
    cost_request = clientcostexplorer.get_cost_and_usage(
    TimePeriod={
        'Start': startDate,
        'End': endDate
    },
    Granularity='MONTHLY',
    Metrics=['BlendedCost','UnblendedCost','UsageQuantity'],
    GroupBy=[
        {
            'Type': 'DIMENSION',
            'Key': 'USAGE_TYPE'
        },
        {
            'Type': 'DIMENSION',
            'Key': 'SERVICE'
        }        
    ]
    )
    i = 0
    for value in cost_request['ResultsByTime'][0]['Groups']:
        i = i +1
        Service       = value['Keys'][1]
        Category = value['Keys'][0]

        invoices_list[Category] = {'Category':Category,'Service':Service}

    ##request by usage
    cost_request = clientcostexplorer.get_cost_and_usage(
    TimePeriod={
        'Start': startDate,
        'End': endDate
    },
    Granularity='MONTHLY',
    Metrics=['BlendedCost','UnblendedCost','UsageQuantity'],
    GroupBy=[
        {
            'Type': 'DIMENSION',
            'Key': 'USAGE_TYPE'
        },
        {
            'Type': 'DIMENSION',
            'Key': 'LINKED_ACCOUNT'
        }        
    ]
    )
    for value in cost_request['ResultsByTime'][0]['Groups']:
        Reference        = value['Keys'][1]
        Category         = value['Keys'][0]
        SubCategory      = 'N/A'
        Quantity         = value['Metrics']['UsageQuantity']['Amount']
        Region           = aws_region_name
        Unit             = value['Metrics']['UsageQuantity']['Unit']
        UnitPrice        = 'N/A'
        Amount           = value['Metrics']['UnblendedCost']['Amount']
        DiscountedAmount = value['Metrics']['BlendedCost']['Amount']

        for value in invoices_list.values():
            usageCategory   = value['Category']
            Service    = value['Service']
            if usageCategory == Category:
                ### print()
```
