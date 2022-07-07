# -*- coding: utf-8 -*-
import os,sys
import requests,logging,mysql.connector
from mysql.connector import Error
from openpyxl import load_workbook
from datetime import date
from dateutil.relativedelta import relativedelta

#logging
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log = '/var/log/fusion.log'
fileHandler = logging.FileHandler("{0}".format(log))
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)
#date
today         = date.today()
endDate       = date(today.year, today.month, 1)
startDate     = endDate + relativedelta(months=-1)
currentDate   = startDate.strftime("01_%m_%Y")
#env variable
artifactory_apiKey = os.getenv('artifactory_apiKey')
headers = {
    "X-JFrog-Art-Api":f"{artifactory_apiKey}"
}
fileName   = f"FR_Project_Performance_Synthesis_{currentDate}.xlsx"
url        = f"https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/generic-CR_FUSION/fusion_folder/{fileName}"
#get mySQL database credentials
db_host         = os.getenv('db_host')
db_port         = 3306
db_database     = os.getenv('db_database')
db_user         = os.getenv('db_user')
db_password     = os.getenv('db_password')
db_fusion_table = 'csp_fusion'

#function
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
        return
    try:
        if db and db.is_connected():
            return db
    except Error as e:
        logger.info(e)
    if db and db.is_connected():
        db.close()

#insert project code into database
def db_insert_fusion(cursor,db_fusion_table,BusinessUnit,ProjectNumber,ProjectName,ProjectDescription,ProjectUnit,ProjectOrganisation,ProjectType,ProjectMode,Techno,BusinessManagement,ProjectManager,ProjectStatus,StartDate,EndDate):
    cursor.execute(f"""INSERT INTO {db_fusion_table}(BusinessUnit,ProjectNumber,ProjectName,ProjectDescription,ProjectUnit,ProjectOrganisation,ProjectType,ProjectMode,Techno,BusinessManagement,ProjectManager,ProjectStatus,StartDate,EndDate)
    VALUES('{BusinessUnit}','{ProjectNumber}','{ProjectName}','{ProjectDescription}','{ProjectUnit}','{ProjectOrganisation}','{ProjectType}','{ProjectMode}','{Techno}','{BusinessManagement}','{ProjectManager}','{ProjectStatus}','{StartDate}','{EndDate}')
    """)

#delete project code in database
def db_delete_fusion(cursor,db_fusion_table):
    cursor.execute(f"""DELETE FROM {db_fusion_table}""")

#get project Fusion code
def get_account_fusion(url,headers,fileName):
    #counter
    count = 0
    Task = False

    try:
        db     = db_connect(db_host,db_port,db_database,db_user,db_password)
        cursor = db.cursor()
        db_delete_fusion(cursor,db_fusion_table)
        db.commit()
        logger.info(f"Previous project code have been deleted")
    except KeyError:
        logger.info("Error establishing a database connection error")
        sys.exit(1)

    #get file from artifactory
    res = requests.get(url,headers=headers)
    if res.status_code == 200:
        logger.info(f"Url status: {res.status_code}")
        #import and save to local file
        open(fileName, 'wb').write(res.content)
        logger.info(f"File downloaded successfully: {fileName}")
        #read file
        workbook = load_workbook(filename = fileName)
        sheet_ranges = workbook['Sheet1']
        #delete first line
        sheet_ranges.delete_rows(0,1)

        for code in sheet_ranges:
            #check number of items
            if len(code) != 14:
                logger.info("number of columns have been modified! (items != 14)")
                logger.info("projects code have not been imported from file")
                sys.exit(1)
            else:
                count = count + 1
                BusinessUnit        = str(code[0].value)
                ProjectNumber       = str(code[1].value)
                ProjectName         = str(code[2].value).replace("•", "-").replace("'", "-").replace(":", "-").replace("è", "e").replace("é", "e").replace("`", " ").replace(",", "-").replace("/", "-")
                ProjectDescription  = str(code[3].value).replace("•", "-").replace("'", "-").replace(":", "-").replace("è", "e").replace("é", "e").replace("`", " ").replace(",", "-").replace("/", "-")
                ProjectDescription  = ProjectDescription[0:240]
                ProjectUnit         = str(code[4].value)
                ProjectOrganisation = str(code[5].value).replace("•", "-").replace("'", "-").replace(":", "-").replace("è", "e").replace("é", "e").replace("`", " ").replace(",", "-").replace("/", "-")
                ProjectType         = str(code[6].value).replace("•", "-").replace("'", "-").replace(":", "-").replace("è", "e").replace("é", "e").replace("`", " ").replace(",", "-").replace("/", "-")
                ProjectMode         = str(code[7].value)
                Techno              = str(code[8].value).replace("•", "-").replace("'", "-").replace(":", "-").replace("è", "e").replace("é", "e").replace("`", " ").replace(",", "-").replace("/", "-")
                BusinessManagement  = str(code[9].value).replace("•", "-").replace("'", "-").replace(":", "-").replace("è", "e").replace("é", "e").replace("`", " ").replace(",", "-").replace("/", "-")
                ProjectManager      = str(code[10].value).replace("•", "-").replace("'", "-").replace(":", "-").replace("è", "e").replace("é", "e").replace("`", " ").replace(",", "").replace("/", "-")
                ProjectStatus       = str(code[11].value)
                StartDate           = str(code[12].value)
                EndDate             = str(code[13].value)

                #insert data in database
                try:
                    db_insert_fusion(cursor,db_fusion_table,BusinessUnit,ProjectNumber,ProjectName,ProjectDescription,ProjectUnit,ProjectOrganisation,ProjectType,ProjectMode,Techno,BusinessManagement,ProjectManager,ProjectStatus,StartDate,EndDate)                     
                    db.commit()
                    logger.info(f'Project code {ProjectNumber} has been added in mysql database')
                    Task = True
                except KeyError:
                    logger.info('Error occurred while inserting data mysql database')
                    Task = False

        if Task:
            logger.info("Project code from fusion file have been imported")
        else:
            logger.info("There was a error when importing. Please try again later.")
    else:
        logger.info(f"There was an error opening this document. This file cannot be found: {res.status_code}")
        sys.exit(1)

if __name__ == '__main__':
    get_account_fusion(url,headers,fileName)

