## Flexible Engine billing reports

### Authentication
You must create a key to call Arrow API : https://developer.orange.com/myapps \
The examples in this section use the (non-working) credentials in the following table.
<table>
  <tr>
    <th>Parameter</th>
    <th>Value</th>
  </tr>
  <tr>
    <td>orange_token</td>
    <td>feEXAMPLE</td>
  </tr>
  <tr>
    <td>cloudstore_token</td>
    <td>EYSEXvsjFcEXAMPLEKEY</td>
  </tr>
  <tr>
    <td>Contract ID</td>
    <td>xxxxxxxxxxxxxxxxxx</td>
  </tr>
</table>

### python script example
minimum version : Python 3.6.x
```python
# -*- coding: utf-8 -*-
import config
import requests,json,logging,urllib3,datetime,mysql.connector
from mysql.connector import Error
from datetime import datetime,date
from dateutil.relativedelta import relativedelta
from openpyxl import load_workbook
urllib3.disable_warnings()
```

### Environment variable
- Variables should be adapted for your specific context
```python
today         = date.today()
endDate       = date(today.year, today.month, 1)
startDate     = endDate + relativedelta(months=-1)
fe_month      = startDate.strftime("%Y%m")
BillingPeriod = startDate.strftime("%Y-%m-28")
log = "/var/log/fe_billing.log"
logging.basicConfig(filename=log,level=logging.DEBUG,format='%(asctime)s %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
```

### VAULT AppRole authentication method
```python
vault_role_id     = config.vault_role_id
vault_secret_id   = config.vault_secret_id
vault_login_path  = config.vault_login_path
suivi_secret_path = config.suivi_secret_path
fe_secret_path    = config.fe_secret_path
```

```python
#Get vault token authentification with AppRole
def get_fe_vault_credentials(vault_role_id,vault_secret_id,vault_login_path,fe_secret_path):
    ##if Orange CA not installed
    urllib3.disable_warnings()

    payload = {"role_id": vault_role_id, "secret_id": vault_secret_id}
    r = requests.post(vault_login_path, json=payload, verify=False)
    token = r.json()['auth']['client_token']
    r = requests.get(fe_secret_path, headers={"X-Vault-Token":token}, verify=False)
    if r.status_code == 200:
        logging.info(f"Vault token: {r.status_code}")
        vault_result = r.json()
        return vault_result
    else:
        logging.info(f"vault token error: {r.status_code}")
```

### Get fe url + credentials
```python
vault_result = get_fe_vault_credentials(vault_role_id,vault_secret_id,vault_login_path,fe_secret_path)
fe_autorizationId    = vault_result['data']['Authorization header']
fe_token_url         = vault_result['data']['token_url']
fe_cloudstore_token  = vault_result['data']['Cloudstore token']
fe_contract_id       = vault_result['data']['Contract ID']
fe_data              = {"grant_type": "client_credentials"}
fe_headers           = {"Accept": "application/json","Authorization": f"{fe_autorizationId}"}
fe_customers_url     = "https://api.orange.com/cloud/b2b/v1/contracts"
fe_contract_url      = "https://api.orange.com/cloud/b2b/v1/contract"
fe_bills_url         = "https://api.orange.com/cloud/b2b/v1/documents?documentType=bills"
```

### Get Customers
```python
def get_customers(fe_token_url,fe_cloudstore_token,fe_data,fe_headers,fe_customers_url,fe_contract_url):

    r = requests.post(fe_token_url, data=fe_data, headers=fe_headers)
    if r.status_code == 200:
        logging.info(f"FE token url: {r.status_code}")
        token = r.json()
        fe_orange_token = token['access_token']
        contracts_headers  = {
            "Accept": "application/json",
            "Authorization": f"Bearer {fe_orange_token}",
            "X-API-Key": f"{fe_cloudstore_token}"
        }
        r = requests.get(fe_customers_url, headers=contracts_headers)
        if r.status_code == 200:
            logging.info(f"FE customers url: {r.status_code}")
            nb_fe_customers = r.json()
            for fe_customers in nb_fe_customers:
                Reference   = fe_customers['id']
                TenantName  = fe_customers['name']
                Created     = fe_customers['createdAt']
                Tag         = (fe_customers['offer']['name']).lower()
                contract_headers = {
                    "Accept": "application/json",
                    "Authorization": f"Bearer {fe_orange_token}",
                    "X-API-Key": f"{fe_cloudstore_token}",
                    "X-ECCS-Contract-Id": f"{Reference}"
                }
                r = requests.get(fe_contract_url, headers=contract_headers)
                if r.status_code == 200:
                    logging.info(f"FE contract url: {r.status_code}")
                    nb_fe_contracts = r.json()

                    LastName   = (nb_fe_contracts['contact']['lastName']).upper()
                    FirstName  = (nb_fe_contracts['contact']['firstName']).lower()
                    Contact    = f"{FirstName} {LastName}"
                    Email      = nb_fe_contracts['contact']['email']
                    Status     = 'active'
                    if 'platformId' not in nb_fe_contracts:
                        Id  = 'None'
                    else:
                        Id  = nb_fe_contracts['platformId']

                    print(Reference,TenantName,Contact,Email,Tag,Status,Created,Id)

                else:
                    logging.info(f"FE contract url error: {r.status_code}")
            logging.info("FE Customers have been updated")
        else:
            logging.info(f"FE customers url error: {r.status_code}")
    else:
        logging.info(f"FE token url error: {r.status_code}")
```

### Get monthly consumption from FE (the last bill)
```python
def get_consumption(fe_token_url,fe_data,fe_bills_url,fe_headers,fe_cloudstore_token,fe_contract_id,fe_month,BillingPeriod):

    Tag    = 'flexible engine'
    fe_month=str(fe_month)

    r = requests.post(fe_token_url, data=fe_data, headers=fe_headers)
        if r.status_code == 200:
            logging.info(f"FE token url: {r.status_code}")
            token = r.json()
            fe_orange_token = token['access_token']
        else:
            logging.info(f"FE token url: {r.status_code}")

        fe_headers  = {"Accept": "application/json","Authorization": f"Bearer {fe_orange_token}","X-API-Key": f"{fe_cloudstore_token}","X-ECCS-Contract-Id": f"{fe_contract_id}"}
        r = requests.get(fe_bills_url, headers=fe_headers)
        if r.status_code == 200:
            logging.info(f"FE bills url: {r.status_code}")
            bills_request = r.json()
            for value in bills_request:
                if fe_month in value['period']:
                    billsId = value['id']
                    consumption_url = f"https://api.orange.com/cloud/b2b/v1/documents/{billsId}/file"
                    r = requests.get(consumption_url, headers=fe_headers, allow_redirects=True)
                    if r.status_code == 200:
                        logging.info(f"FE consumption url: {r.status_code}")
                        open('fe.xlsx', 'wb').write(r.content)
                        workbook = load_workbook(filename = "fe.xlsx")
                        sheet_ranges = workbook['Billing Report']
                        sheet_ranges.delete_rows(0,13)

                        for x in sheet_ranges:
                            Reference        = x[0].value
                            Service          = x[10].value
                            Category         = x[11].value
                            SubCategory      = x[7].value
                            Quantity         = x[12].value
                            Region           = x[9].value
                            Unit             = x[13].value
                            UnitPrice        = x[14].value
                            Amount           = x[15].value
                            DiscountedAmount = x[17].value

                            print(Reference,Region,Service,Category,SubCategory,Quantity,Unit,UnitPrice,Amount,DiscountedAmount,Tag,BillingPeriod)

                        logging.info("Consumption usage details from Flexible engine have been imported")
                    else:
                        logging.info(f"FE consumption url error: {r.status_code}")
        else:
            logging.info(f"FE bills url error: {r.status_code}")                   
```
