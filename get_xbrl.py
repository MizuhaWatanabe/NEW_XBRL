# -*- coding: utf-8 -*-
import requests, json, urllib3, datetime, os, sys
import xbrl_config
from zipfile import ZipFile
from io import BytesIO
urllib3.disable_warnings()

def download_xbrl(search_conditions):
    securities_report_dict = {}
    for stock in search_conditions['stocks']:
        securities_report_dict[str(stock) + '0'] = [] # securities_report_dict to be [ticker: [docID, formCode], ...]

    period = search_conditions['end_date'] - search_conditions['start_date']
    period = int(period.days)
    day_list = []
    for d in range(period):
        day = search_conditions['start_date'] + datetime.timedelta(days=d)
        day_list.append(day)
    day_list.append(search_conditions['end_date'])

    for day in day_list:
        url = 'https://disclosure.edinet-fsa.go.jp/api/v1/documents.json'
        params = {'date': day,'type': 2}
        try:
            res = requests.get(url, params=params, verify=False, timeout=(10.0, 30.0))
        except requests.exceptions.Timeout:
            print(f'Skip JSON loading for {day} due to timeout')
            pass
        json_data = json.loads(res.text)
        print(f'\r{day}', end='')

        if 'results' in json_data:
            print('\r', end='')
            for num in range(len(json_data['results'])):
                filer_name = json_data['results'][num]['filerName']
                security_code = json_data['results'][num]['secCode']
                ordinance_code = json_data['results'][num]['ordinanceCode']
                form_code = json_data['results'][num]['formCode']
                document_id = json_data['results'][num]['docID']
                document_description = json_data['results'][num]['docDescription']
                submit_datetime = json_data['results'][num]['submitDateTime']

                if security_code in securities_report_dict.keys() and\
                   ordinance_code == search_conditions['ordinance'] and\
                   form_code in search_conditions['forms']:

                    print(submit_datetime, document_id, security_code[:-1], filer_name, document_description)
                    securities_report_dict[security_code] += [[document_id, form_code]]

    print('\n')
    for ticker, docs in securities_report_dict.items():
        directory_path = os.getcwd() + '/XBRL_FILES'
        if not os.path.exists(directory_path): os.mkdir(directory_path)
        company_path = directory_path + '/' + ticker[:-1]
        if not os.path.exists(company_path): os.mkdir(company_path)
        for doc in docs:
            save_path = company_path + '/' + doc[0] if doc[1].endswith('0') else company_path + '/' + doc[0] + '_amd'
            if not os.path.exists(save_path):
                os.mkdir(save_path)
                url = 'https://disclosure.edinet-fsa.go.jp/api/v1/documents/' + doc[0]
                params = {'type': 1}
                res = requests.get(url, params=params, verify=False)
                saved_file = ZipFile(BytesIO(res.content))
                saved_file.extractall(save_path)
                print(f'Complete downloading XBRL file for {ticker[:-1]} {doc[0]}')
            else:
                print(f'XBRL file for {ticker[:-1]} {doc[0]} already exists')


search_conditions = {
        'start_date': datetime.date(2015, 12, 31),
        'end_date'  : datetime.date(2020, 8, 30),
        'stocks'    : [4666, 4732, 6902, 7201, 7202, 7203, 7205, 7211, 7259, 7261, 7267, 7269, 7270, 7272],
        #        'stocks'    : xbrl_config.listed_ticker_list,
        'forms'     : ['030000', '030001', '043000', '043001'],
        'ordinance' : '010'
        }

download_xbrl(search_conditions)
