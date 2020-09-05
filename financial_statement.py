# -*- coding: utf-8 -*-
import edinet, xbrl_config
import pandas as pd
import numpy as np
import os, urllib3, openpyxl, requests
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile
from bs4 import BeautifulSoup
urllib3.disable_warnings()

class Element():

    def __init__(self, name, element, location, taxonomy):
        self.name = name
        self.element = element
        self.location = location
        self.taxonomy = taxonomy

    def definition(self):
        def_dir = self.taxonomy.root
        path, element_name = self.location.split('#')
        location = self.location
        target_tag = ''

        if path.startswith(self.taxonomy.reference_prefix):
            path = path.replace(self.taxonomy.reference_prefix, '')
            path = os.path.join(self.taxonomy.reference_root, path)
            target_tag = 'xsd:element'
        else:
            path = os.path.join(self.taxonomy.root, path)
            target_tag = 'element'

        xml = self.taxonomy._read_from_cache(path)
        _def = xml.find(target_tag, {'id': element_name})
        return _def

    def label(self, kind='ja', verbose=True):
        label_ext = '_lab.xml'
        if kind == 'en': label_ext = '_lab-en.xml'
        elif kind == 'g': label_ext = '_gla.xml'
        label = None

        label_dir = self.taxonomy.root
        path, element_name = self.location.split('#')
        location = self.location
        target_attribute = ''

        if path.startswith(self.taxonomy.reference_prefix):
            path = path.replace(self.taxonomy.reference_prefix, '')
            label_dir_reference = os.path.join(self.taxonomy.reference_root, f'{os.path.dirname(path)}/label')
            label_dir = label_dir_reference
            location = f'../{os.path.basename(path)}#{element_name}'
            target_attribute = 'id'

        targets = []
        for f in os.listdir(label_dir):
            label_path = os.path.join(label_dir, f)
            if not label_path.endswith(label_ext):
                continue

            label_xml = self.taxonomy._read_from_cache(label_path)
            targets = self._read_link(xml=label_xml, arc_name='link:labelArc', location=location, target_name='link:label', target_attribute=target_attribute)

        if len(targets) > 1:
            for lb in targets:
                if lb['xlink:role'].endswith('verboseLink') and verbose:
                    label = lb
                    break
                else:
                    label = lb
        elif len(targets) > 0:
            label = targets[0]

        return label

    def _read_link(self, xml, arc_name, location='', target_name='', target_attribute=''):

        location = location if location else self.location
        label = xml.find('link:loc', {'xlink:href': location})
        arc = None

        if label is not None:
            arc = xml.find(arc_name, {'xlink:from': label['xlink:label']})
        else:
            arc = xml.find(arc_name, {'xlink:label': self.name})

        if arc is None:
            return []

        target_name = target_name if target_name else 'link:loc'
        target_attribute = target_attribute if target_attribute else 'xlink:label'
        targets = []
        if arc is not None:
            targets = xml.find_all(target_name, {target_attribute: arc['xlink:to']})

        return targets


class Taxonomy():

    def __init__(self, root, reference_root, reference_prefix=''):
        self.root = root
        self.reference_root = reference_root
        self.reference_prefix = reference_prefix
        self._cache = {}
        if not self.reference_prefix:
            self.reference_prefix = 'http://disclosure.edinet-fsa.go.jp/taxonomy/'

    def _read_from_cache(self, path):
        xml = None
        if path in self._cache:
            xml = self._cache[path]
        else:
            with open(path, encoding='utf-8-sig') as f:
                xml = BeautifulSoup(f, 'lxml-xml')
            self._cache[path] = xml
        return self._cache[path]

    def read(self, href):
        path = href
        element = ''
        use_parent = False

        if '#' in path:
            path, element = path.split('#')

        if path.startswith(self.reference_prefix):
            path = path.replace(self.reference_prefix, '')
            path = os.path.join(self.reference_root, path)
        else:
            path = os.path.join(self.root, path)

        xml = self._read_from_cache(path)

        if element:
            xml = xml.select(f'#{element}')
            if len(xml) > 0:
                xml = xml[0]
            xml = Element(element, xml, href, self)

        return xml


class Node():

    def __init__(self, element, order=0):
        self.element = element
        self.parent = None
        self.order = order

    def add_parent(self, parent):
        self.parent = parent

    @property
    def name(self):
        return self.element['xlink:href'].split('#')[-1]

    @property
    def label(self):
        return self.element['xlink:label']

    @property
    def location(self):
        return self.element['xlink:href']

    @property
    def depth(self):
        return len(self.get_parents())

    @property
    def path(self):
        parents = list(reversed(self.get_parents()))
        if len(parents) == 0:
            return self.name
        else:
            path = str(self.order) + ' ' + self.name
            for p in parents:
                path = p.name + '/' + path
            return path

    def get_parents(self):
        parents = []
        if self.parent is None:
            return parents
        else:
            p = self.parent
            while p is not None:
                parents.insert(0, p)
                p = p.parent
            return parents


def taxonomy_check(taxonomy_dir):
    for year, url in xbrl_config.taxonomy_link_list.items():
        taxonomy_file = taxonomy_dir.joinpath(f'{year}_taxonomy.zip')
        res = requests.get(url, stream=True)
        with taxonomy_file.open(mode='wb') as f:
            for chunk in res.iter_content(1024):
                f.write(chunk)

        with ZipFile(taxonomy_file, 'r') as zip:
            for f in zip.namelist():
                dir_names = f.split('/')
                if dir_names[1] == 'taxonomy' and dir_names[-1] != '':
                    _to = taxonomy_dir.joinpath('/'.join(dir_names[2:]))
                    _to.parent.mkdir(parents=True, exist_ok=True)
                    with _to.open('wb') as _to_f:
                        _to_f.write(zip.read(f))
        taxonomy_file.unlink()
    print('Taxonomy check completed')
    return False

def digitize(_str):
    try:
        float(_str)
    except:
        return _str
    return float(_str)

company_list = [4732]
taxonomy_check_needed = False

taxonomy_dir = Path.cwd().joinpath('TAXONOMY_FILES')
taxonomy_dir.mkdir(parents=True, exist_ok=True)
if taxonomy_check_needed: taxonomy_check_needed = taxonomy_check(taxonomy_dir)

for role in xbrl_config.role_ref:
    for company in company_list:
        print(f'Compiling {role} data of {company}...')
        company_dir = Path.cwd().joinpath('XBRL_FILES', str(company))
        doc_id_list = [doc_id for doc_id in os.listdir(company_dir) if not doc_id.startswith('.')]
        doc_id_list.sort()
        excel_dir = Path.cwd().joinpath(f'EXCEL_FILES/{str(company)}')
        excel_dir.mkdir(parents=True, exist_ok=True)

        initial_flag = True
        financial_statement = pd.DataFrame()
        period_list, period_list_only_FY =[], []
        for doc_id in doc_id_list:
            doc_id_dir = company_dir.joinpath(doc_id)
            xbrl_dir = edinet.xbrl_file.XBRLDir(doc_id_dir)
            taxonomy = Taxonomy(xbrl_dir._document_folder, taxonomy_dir)

            accounting_standard = xbrl_dir.xbrl.find('jpdei_cor:AccountingStandardsDEI').text
            FY_or_Q = 'FY' if xbrl_dir.xbrl.find('jpdei_cor:TypeOfCurrentPeriodDEI').text == 'FY' else 'Q'
            role_key = accounting_standard + '_' + FY_or_Q
            profile = [xbrl_dir.xbrl.find(k).text for k in xbrl_config.profile_items[FY_or_Q].values()]
            print(profile[0], profile[1], profile[2], doc_id, profile[3])

            # -*- Compiling data by FY/Q, accounting standard -*-
            pre_def = xbrl_dir.pre.find('link:presentationLink', {'xlink:role': xbrl_config.role_ref[role][role_key][0]})
            nodes = {}
            for i, arc in enumerate(pre_def.find_all('link:presentationArc')):
                if not arc['xlink:arcrole'].endswith('parent-child'):
                    print('unexpected arctype')
                    continue

                parent = Node(pre_def.find('link:loc', {'xlink:label': arc['xlink:from']}), i)
                child = Node(pre_def.find('link:loc', {'xlink:label': arc['xlink:to']}), arc['order'])

                if child.name not in nodes:
                    nodes[child.name] = child
                else:
                    nodes[child.name].order = arc['order']

                if parent.name not in nodes:
                    nodes[parent.name] = parent

                nodes[child.name].add_parent(nodes[parent.name])

            parent_depth = -1
            for name in nodes:
                if parent_depth < nodes[name].depth:
                    parent_depth = nodes[name].depth

            data = []
            for name in nodes:
                n = nodes[name]
                item = {}
                parents = n.get_parents()
                parents = parents + ([''] * (parent_depth - len(parents)))

                item_order = digitize(n.order)
                order_bottom = 'order'

                at_bottom = False
                for i, p in enumerate(parents):
                    name = p if isinstance(p, str) else p.name
                    if isinstance(p, str) and not at_bottom:
                        order = digitize(n.order)
                        item_order = np.nan
                        order_bottom = f'parent_{i}_order'
                        at_bottom = True
                    elif isinstance(p, str) and at_bottom:
                        order = np.nan
                    else:
                        order = digitize(p.order)

                    item[f'parent_{i}'] = name
                    item[f'parent_{i}_order'] = digitize(order)

                item['order'] = item_order
                item['order_bottom'] = order_bottom
                item['element'] = n.name
                item['element_content'] = n.name.split('_')[-1]
                item['depth'] = n.depth

                if initial_flag or item['element_content'] not in financial_statement.index.values:
                    item['label'] = taxonomy.read(n.location).label().text
                    _def = taxonomy.read(n.location).definition()
                    item['abstract'] = _def['abstract']
                    item['type'] = _def['type']
                    if 'xbrli:periodType' in _def.attrs:
                        item['period_type'] = _def['xbrli:periodType']
                    if 'xbrli:balance' in _def.attrs:
                        item['balance'] = _def['xbrli:balance']
                else:
                    item['label'] = financial_statement.at[item['element_content'], 'label']
                    item['abstract'] = financial_statement.at[item['element_content'], 'abstract']
                    item['type'] = financial_statement.at[item['element_content'], 'type']
                    item['period_type'] = financial_statement.at[item['element_content'], 'period_type']
                    item['balance'] = financial_statement.at[item['element_content'], 'balance']

                data.append(item)

            df = pd.DataFrame(data)
            # -*- For debug -*-
            #df.to_excel('df.xlsx', sheet_name=f'{role}')

            xbrl = xbrl_dir.xbrl
            schema = xbrl.find('xbrli:xbrl')
            namespaces = {}
            for a in schema.element.attrs:
                if a.startswith('xmlns:'):
                    namespaces[a.replace('xmlns:', '')] = schema.element.attrs[a]

            xbrl_data = []
            for i, row in df.iterrows():
                tag_name = row['element']

                for n in namespaces:
                    if tag_name.startswith(n):
                        tag_name = f"{n}:{tag_name.replace(n + '_', '')}"
                        break

                tag = xbrl.find(tag_name, {'contextRef': xbrl_config.role_ref[role][role_key][1]})
                element = tag.element
                if element is None:
                    continue

                item = {}
                for k in df.columns:
                    item[k] = row[k]

                for i in range(parent_depth):
                    parent_label = df[df["element"] == row[f"parent_{i}"]]["label"]
                    item[f"parent_{i}_name"] = "" if len(parent_label) == 0 else parent_label.tolist()[0]

                label_reallocated = item['label']
                item.pop('label')
                item['label'] = label_reallocated

                context_id = element["contextRef"]
                if not context_id.endswith("NonConsolidatedMember"):
                    context = xbrl.find("xbrli:context", {"id": context_id})
                    if item["period_type"] == "duration":
                        period = context.find("xbrli:endDate").text
                    else:
                        period = context.find("xbrli:instant").text

                    period = period + '_amd' if doc_id.endswith('_amd') else period
                    item["unit"] = element["unitRef"]
                    item[period] = digitize(element.text)

                    xbrl_data.append(item)

            period_list += [period]
            period_list_only_FY = period_list_only_FY + [period] if FY_or_Q == 'FY' else period_list_only_FY
            xbrl_data = pd.DataFrame(xbrl_data)
            if initial_flag:
                financial_statement = xbrl_data.set_index('element_content')
                fs_parent_depth = parent_depth
                initial_flag = False
            else:
                financial_statement[period] = ''
                for index, row in xbrl_data.iterrows():
                    if row['element_content'] in financial_statement.index.values:
                        financial_statement.at[row['element_content'], period] = row[period]
                    else:
                        parent_num = row['depth'] - 1
                        extracted_df = financial_statement.copy()
                        extracted_df = extracted_df[extracted_df[f'parent_{parent_num}'] == row[f'parent_{parent_num}']]
                        order_bottom = row['order_bottom']
                        current_max_order = digitize(extracted_df[order_bottom].max())
                        extracted_row = extracted_df[extracted_df[order_bottom] == current_max_order]
                        financial_statement.loc[(financial_statement[f'parent_{parent_num}'] == row[f'parent_{parent_num}']) & (financial_statement[order_bottom] == current_max_order), order_bottom] = current_max_order + 1

                        added_row = {}
                        for i in range(fs_parent_depth):
                            added_row[f'parent_{i}'] = np.nan if extracted_row[f'parent_{i}'].empty else extracted_row[f'parent_{i}'].values[0]
                            added_row[f'parent_{i}_order'] = np.nan if extracted_row[f'parent_{i}_order'].empty else digitize(extracted_row[f'parent_{i}_order'].values[0])
                            added_row[f'parent_{i}_name'] = row[f'parent_{i}_name']
                        added_row[order_bottom] = current_max_order
                        added_row['order_bottom'] = order_bottom
                        added_row['depth'] = row['depth']

                        for item in xbrl_config.miscellaneous_output_items:
                            added_row[item] = row[item]

                        added_row['label'] = row['label']
                        added_row['unit'] = row['unit']
                        added_row[period] = row[period]

                        added_data = pd.DataFrame([added_row]).set_index('element_content')
                        financial_statement = financial_statement.append(added_data)

        period_list.sort()
        period_list_only_FY.sort()
        parent_list = [f'parent_{i}' for i in range(fs_parent_depth)]
        parent_order_list = [f'parent_{i}_order' for i in range(fs_parent_depth)]
        parent_name_list = [f'parent_{i}_name' for i in range(fs_parent_depth)]
#        output_order = parent_name_list + ['label', 'unit'] + period_list
#        output_order_only_FY = parent_name_list + ['label', 'unit'] + period_list_only_FY

        # -*- For debug -*-
        output_order = parent_list + parent_order_list + ['order', 'order_bottom', 'depth'] + xbrl_config.miscellaneous_output_items + parent_name_list + ['label', 'unit'] + period_list
        output_order_only_FY = parent_list + parent_order_list + ['order', 'order_bottom', 'depth'] + xbrl_config.miscellaneous_output_items + parent_name_list + ['label', 'unit'] + period_list_only_FY

        financial_statement.sort_values(by=[c for c in df.columns if c.endswith('order')], inplace=True)

        financial_statement_all = financial_statement.reset_index()[output_order]
        financial_statement_all.to_excel(f'{excel_dir}/{company}_{role}_all.xlsx', sheet_name=f'{role}')
        financial_statement_FY = financial_statement.reset_index()[output_order_only_FY]
        financial_statement_FY.to_excel(f'{excel_dir}/{company}_{role}_FY.xlsx', sheet_name=f'{role}')

        print('')
