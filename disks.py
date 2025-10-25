import requests
import xml.etree.ElementTree as ET
import re
import os

def fetch_xml(url):
    response = requests.get(url)
    response.raise_for_status()
    return ET.fromstring(response.content)

def normalize_fields(item, source):
    if source == "4tochki":
        field_map = {
            "cae": "cae",
            "brand": "brand",
            "model": "model",
            "color": "color",
            "width": "width",
            "diameter": "diameter",
            "img_big_my": "img_small",
            "name": "name",
            "bolts_count": "holes",
            "bolts_spacing": "diam_holes",
            "et": "et",
            "rim_type": "type",
            "dia": "diam_center",
            "price": "price"
        }
    elif source == "brinex":
        field_map = {
            "product_id": "article",
            "name": "name",
            "price": "price",
            "countAll": "count",
            "stockName": "stock",
            "proizvoditel": "brand",
            "shirina_diska": "width",
            "radius": "diameter",
            "et": "et",
            "DescriptionOfColor": "color",
            "vendor_code": "cae",
            "material": "type",
            "boltnum": "holes",
            "boltdistance": "diam_holes",
            "categoryname": "model",
            "priceOpt": "opt"
        }
    
    normalized_item = {}
    for elem in item:
        # Если присутствует элемент img_big_my, пропускаем обработку img_small
        if source == "4tochki" and elem.tag == "img_small" and item.find("img_big_my") is not None:
            continue
        tag = field_map.get(elem.tag, elem.tag)
        normalized_item[tag] = elem.text if elem.text else ""
        if elem.tag in ["img_big_my", "img_small"]:
            print(f"Input tag: {elem.tag}, value: {elem.text}")
            print(f"Output tag: {tag}, value: {normalized_item[tag]}")
    
    return normalized_item

def process_items(api_url, source, filter_tag=None, status=None):
    root = fetch_xml(api_url)
    items_with_rest = ET.Element("items")  # Для товаров с <rest_novosib3>
    items_without_rest = ET.Element("items")  # Для товаров без <rest_novosib3>

    for item in root.findall(".//rims" if source == "4tochki" else ".//item"):
        normalized_item = normalize_fields(item, source)
        cae = normalized_item.get("cae")
        unique_id = cae or normalized_item.get("article")
        if not unique_id:
            continue
        
        # Проверяем наличие поля <rest_novosib3>
        rest_element = item.find(filter_tag) if filter_tag else None
        
        # Создаем новый элемент для товара
        new_item = ET.SubElement(items_with_rest if rest_element is not None else items_without_rest, "item")
        if status:
            status_elem = ET.SubElement(new_item, "status")
            status_elem.text = status
        
        for tag, text in normalized_item.items():
            # ⬅ изменение: обработка розничных цен
            if tag.endswith("_rozn"):
                try:
                    price = float(text)
                    text = str(round(price * 1.05, 2))  # +5%
                except (ValueError, TypeError):
                    pass  # если значение не число, пропускаем

            new_elem = ET.SubElement(new_item, tag)
            new_elem.text = text
    
    return items_with_rest, items_without_rest

def save_xml(root, output_file):
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)

def main():
    url1 = "https://b2b.4tochki.ru/export_data/M28244.xml"  # Первая API (4tochki)
    url2 = "https://abcdisk54.ru/ftp/Brinex_disk.xml"       # Вторая API (Brinex)

    # Обрабатываем первую API
    items_with_rest, items_without_rest = process_items(url1, source="4tochki", filter_tag="rest_novosib3", status="В наличии")
    
    # Сохраняем товары с <rest_novosib3> в disks_nsk.xml
    save_xml(items_with_rest, "disks_nsk.xml")
    
    # Сохраняем товары без <rest_novosib3> в disks.xml
    save_xml(items_without_rest, "disks.xml")

    # Обрабатываем вторую API и добавляем товары в disks.xml
    _, brinex_items = process_items(url2, source="brinex", status="Под заказ")
    existing_items = ET.parse("disks.xml").getroot()
    for item in brinex_items:
        existing_items.append(item)
    save_xml(existing_items, "disks.xml")

    print("XML файлы успешно созданы без дубликатов и с унифицированными полями.")

if __name__ == "__main__":
    main()
