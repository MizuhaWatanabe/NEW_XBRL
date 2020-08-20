for i, row in data.iterrows():
    tag_name = row["element"]

    for n in namespaces:
        if tag_name.startswith(n):
            tag_name = f"{n}:{tag_name.replace(n + '_', '')}"
            break

    tag = xbrl.find(tag_name)
    element = tag.element
    if element is None:
        continue

    item = {}
    for k in data.columns:
        item[k] = row[k]

    for i in range(parent_depth):
        parent_label = data[data["element"] == row[f"parent_{i}"]]["label"]
        item[f"parent_{i}_name"] = "" if len(parent_label) == 0 else parent_label.tolist()[0]
    
    item["value"] = element.text
    item["unit"] = element["unitRef"]

    context_id = element["contextRef"]
    if context_id.endswith("NonConsolidatedMember"):
        item["individual"] = True
    else:
        item["individual"] = False

    context = xbrl.find("xbrli:context", {"id": context_id})
    if item["period_type"] == "duration":
        item["period"] = context.find("xbrli:endDate").text
        item["period_begin"] = context.find("xbrli:startDate").text
    else:
        item["period"] = context.find("xbrli:instant").text
        item["period_begin"] = None

    xbrl_data.append(item)


xbrl_data = pd.DataFrame(xbrl_data)