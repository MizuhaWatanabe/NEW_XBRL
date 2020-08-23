# -*- coding: utf-8 -*-
import edinet, taxonomies
import pandas as pd
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
    for year, url in taxonomies.link_list.items():
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
        int(_str)
    except:
        return _str
    return int(_str)

company_list = ['TEST']
taxonomy_check_needed = False

JGAAP_role_ref = {'BS': ['rol_ConsolidatedBalanceSheet', 'CurrentYearInstant'],
        'PL': ['rol_ConsolidatedStatementOfIncome', 'CurrentYearDuration'],
        'CF': ['rol_ConsolidatedStatementOfCashFlows', 'CurrentYearDuration']
        }

taxonomy_dir = Path.cwd().joinpath('TAXONOMY_FILES')
taxonomy_dir.mkdir(parents=True, exist_ok=True)
if taxonomy_check_needed: taxonomy_check_needed = taxonomy_check(taxonomy_dir)

for JGAAP_role in JGAAP_role_ref:
    for company in company_list:
        company_dir = Path.cwd().joinpath('XBRL_FILES', str(company))
        doc_id_list = [doc_id for doc_id in os.listdir(company_dir) if not doc_id.startswith('.')]
        excel_dir = Path.cwd().joinpath(f'EXCEL_FILES/{str(company)}')
        excel_dir.mkdir(parents=True, exist_ok=True)

        for doc_id in doc_id_list:
            doc_id_dir = company_dir.joinpath(doc_id)
            xbrl_dir = edinet.xbrl_file.XBRLDir(doc_id_dir)

            accounting_standard = xbrl_dir.xbrl.find('jpdei_cor:AccountingStandardsDEI').text
            FY_or_Q = xbrl_dir.xbrl.find('jpdei_cor:TypeOfCurrentPeriodDEI').text
            current_FY_end = datetime.strptime(xbrl_dir.xbrl.find('jpdei_cor:CurrentFiscalYearEndDateDEI').text, '%Y-%m-%d')

            if FY_or_Q == 'FY' and accounting_standard == 'Japan GAAP':
                role_ref_tags = xbrl_dir.xbrl.find_all('link:roleRef')
                role_ref_elements = [t.element for t in role_ref_tags]
                role_refs = {}
                for e in role_ref_elements:
                    role_refs[e['roleURI']] = e['xlink:href']

                taxonomy = Taxonomy(xbrl_dir._document_folder, taxonomy_dir)
                roles = {}
                for r in role_refs:
                    role_name = taxonomy.read(role_refs[r]).element.find('link:definition').text
                    roles[role_name] = r

                role_name_BS = [k for k, v in roles.items() if JGAAP_role_ref[JGAAP_role][0] in v][0]
                pre_def = xbrl_dir.pre.find('link:presentationLink', {'xlink:role': roles[role_name_BS]})
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

                    for i, p in enumerate(parents):
                        name = p if isinstance(p, str) else p.name
                        order = '0' if isinstance(p, str) else p.order
                        item[f'parent_{i}'] = name
                        item[f'parent_{i}_order'] = int(order)

                    item['element'] = n.name
                    item['order'] = int(n.order)
                    item['depth'] = n.depth
                    item['label'] = taxonomy.read(n.location).label().text

                    _def = taxonomy.read(n.location).definition()
                    item['abstract'] = _def['abstract']
                    item['type'] = _def['type']
                    if 'xbrli:periodType' in _def.attrs:
                        item['period_type'] = _def['xbrli:periodType']
                    if 'xbrli:balance' in _def.attrs:
                        item['balance'] = _def['xbrli:balance']

                    data.append(item)

                df = pd.DataFrame(data)
                df.sort_values(by=[c for c in df.columns if c.endswith('order')], inplace=True)


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

                    tag = xbrl.find(tag_name, {'contextRef': JGAAP_role_ref[JGAAP_role][1]})
                    element = tag.element
                    if element is None:
                        continue

                    item = {}
                    for k in df.columns:
                        item[k] = row[k]

                    parent_sort = ['order']
                    for i in range(parent_depth):
                        parent_label = df[df["element"] == row[f"parent_{i}"]]["label"]
                        item[f"parent_{i}_name"] = "" if len(parent_label) == 0 else parent_label.tolist()[0]
                        parent_sort.append(f'parent_{parent_depth - i - 1}_order')

                    context_id = element["contextRef"]
                    if not context_id.endswith("NonConsolidatedMember"):
                        context = xbrl.find("xbrli:context", {"id": context_id})
                        if item["period_type"] == "duration":
                            item["period"] = context.find("xbrli:endDate").text
                            item["period_begin"] = context.find("xbrli:startDate").text
                        else:
                            item["period"] = context.find("xbrli:instant").text
                            item["period_begin"] = None

                        item[item["period"]] = digitize(element.text)
                        item["unit"] = element["unitRef"]

                        xbrl_data.append(item)

                file_name_FY = current_FY_end.strftime('FY%-m_%y')
                file_name_Q = '' if FY_or_Q == 'FY' else f'_{FY_or_Q}'
                file_name = file_name_FY + file_name_Q

                xbrl_data = pd.DataFrame(xbrl_data)
                xbrl_data.sort_values(parent_sort)
                xbrl_data.to_excel(f'{excel_dir}/{company}_{file_name}_{doc_id}_{JGAAP_role}.xlsx', sheet_name=f'{file_name}')












