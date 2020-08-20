# -*- coding: utf-8 -*-
import requests, urllib3, datetime, os
from zipfile import ZipFile
from io import BytesIO
urllib3.disable_warnings()

def download_xbrl(search_conditions):
    period = search_conditions['end_date'] - search_conditions['start_date']
    period = int(period.days)
    day_list = []
    for d in range(period):
        day = search_conditions['start_date'] + datetime.timedelta(days=d)
        day_list.append(day)
    day_list.append(search_conditions['end_date'])


    for stock in search_conditions['stocks']:
        securities_report_doc_list = []
        for day in day_list:
            url = 'https://disclosure.edinet-fsa.go.jp/api/v1/documents.json'
            params = {'date': day,'type': 2}
            res = requests.get(url, params=params, verify=False)
            json_data = res.json()

            if 'results' in json_data:
                for num in range(len(json_data['results'])):
                    filer_name = json_data['results'][num]['filerName']
                    security_code = json_data['results'][num]['secCode']
                    ordinance_code = json_data['results'][num]['ordinanceCode']
                    form_code = json_data['results'][num]['formCode']
                    document_id = json_data['results'][num]['docID']
                    document_description = json_data['results'][num]['docDescription']
                    submit_datetime = json_data['results'][num]['submitDateTime']

                    if security_code == str(stock) + '0' and\
                       ordinance_code == search_conditions['ordinance'] and\
                       form_code in search_conditions['forms']:

                        print(submit_datetime, document_id, stock, filer_name, document_description)
                        securities_report_doc_list.append(document_id)
                        number_of_documents = len(securities_report_doc_list)


        for index, doc_id in enumerate(securities_report_doc_list):
            print(doc_id, ':', index + 1, '/', number_of_documents)
            directory_path = os.getcwd() + '/XBRL_FILES'
            if not os.path.exists(directory_path): os.mkdir(directory_path)
            company_path = directory_path + '/' + str(stock)
            if not os.path.exists(company_path): os.mkdir(company_path)
            save_path = company_path + '/' + doc_id
            if not os.path.exists(save_path):
                os.mkdir(save_path)
                url = 'https://disclosure.edinet-fsa.go.jp/api/v1/documents/' + doc_id
                params = {'type': 1}
                filename = doc_id + '.zip'
                res = requests.get(url, params=params, verify=False)
                saved_file = ZipFile(BytesIO(res.content))
                saved_file.extractall(save_path)



search_conditions = {
        'start_date': datetime.date(2019, 12, 11),
        'end_date'  : datetime.date(2020, 8, 9),
        'stocks'    : [7201, 7202, 7203, 7205, 7211, 7261, 7267, 7269, 7270, 7272, 6902, 7259, 4666],
        'forms'     : ['030000', '030001', '043000', '043001'],
        'ordinance' : '010'
        }

download_xbrl(search_conditions)


