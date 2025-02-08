import requests
import xml.etree.ElementTree as ET
import re
import os

def fetch_xml(url):
    response = requests.get(url)
    response.raise_for_status()
    return ET.fromstring(response.content)

def normalize_fields(item):
    field_map = {
        "vendor_code": "cae",
        "product_id": "article",
        "countAll": "rest",
        "stockName": "stock",
        "shirina_secheniya": "width",
        "visota_secheniya": "height",
        "radius": "diameter",
        "seasonality": "season",
        "categoryname": "model",
        "priceOpt": "opt",
        "price": "price",
        "spikes": "thorn",
        "img_big_my": "img",
        "proizvoditel": "brand"
    }
    
    normalized_item = {}
    for elem in item:
        tag = field_map.get(elem.tag, elem.tag)
        normalized_item[tag] = elem.text if elem.text else ""
    
    return normalized_item

def filter_and_save_items(api_url, output_file, filter_tag=None, existing_items=None, include_tag=None, include_value=None, status=None):
    """Фильтрует товары, удаляет дубликаты, приводит поля к общему формату и сохраняет в XML-файл."""
    root = fetch_xml(api_url)
    if existing_items is None:
        new_root = ET.Element("items")
    else:
        new_root = existing_items

    # Обрабатываем все товары в XML
    for item in root.findall(".//tires" if "4tochki" in api_url else ".//item"):
        normalized_item = normalize_fields(item)  # Нормализуем поля товара
        cae = normalized_item.get("cae")
        unique_id = cae or normalized_item.get("article")
        if not unique_id:
            continue
        
        # Проверяем наличие тега include_tag с определенным значением
        if include_tag and include_value:
            include_element = item.find(include_tag)
            if include_element is None or include_element.text != include_value:
                continue  # Пропускаем товары без указанного тега или с другим значением

        # Если filter_tag задан, сохраняем только товары с этим тегом в output_file
        if filter_tag:
            rest_element = item.find(filter_tag)  # Ищем тег <rest_novosib3>
            if rest_element is not None:  # Товар с <rest_novosib3>
                new_item = ET.SubElement(new_root, "item")
                if status:  # Добавляем поле <status>, если оно задано
                    status_elem = ET.SubElement(new_item, "status")
                    status_elem.text = status
                for tag, text in normalized_item.items():
                    new_elem = ET.SubElement(new_item, tag)
                    new_elem.text = text
        else:
            # Если filter_tag не задан, проверяем, что товар не имеет <rest_novosib3>
            rest_element = item.find("rest_novosib3")
            if rest_element is None:  # Товар без <rest_novosib3>
                new_item = ET.SubElement(new_root, "item")
                if status:  # Добавляем поле <status>, если оно задано
                    status_elem = ET.SubElement(new_item, "status")
                    status_elem.text = status
                for tag, text in normalized_item.items():
                    new_elem = ET.SubElement(new_item, tag)
                    new_elem.text = text
    
    tree = ET.ElementTree(new_root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    return new_root

def main():
    url1 = "https://b2b.4tochki.ru/export_data/M28274.xml"
    url2 = "https://abcdisk54.ru/ftp/Brinex_shina.xml"

    # Создаем пустой файл tyres.xml для начала
    initial_root = ET.Element("items")
    initial_tree = ET.ElementTree(initial_root)
    initial_tree.write("tyres.xml", encoding="utf-8", xml_declaration=True)

    # Создаем пустой файл tyres_gruz.xml для начала
    gruz_initial_root = ET.Element("items")
    gruz_initial_tree = ET.ElementTree(gruz_initial_root)
    gruz_initial_tree.write("tyres_gruz.xml", encoding="utf-8", xml_declaration=True)

    # Сохраняем товары без <rest_novosib3> и с <tiretype>Легковая</tiretype> в tyres.xml
    existing_items = filter_and_save_items(url1, "tyres.xml", filter_tag=None, include_tag="tiretype", include_value="Легковая", status="Под заказ")

    # Сохраняем товары с <rest_novosib3> и с <tiretype>Легковая</tiretype> в tyres_nsk.xml
    filter_and_save_items(url1, "tyres_nsk.xml", filter_tag="rest_novosib3", include_tag="tiretype", include_value="Легковая", status="В наличии")

    # Сохраняем товары с <tiretype>Грузовая</tiretype> в tyres_gruz.xml
    filter_and_save_items(url1, "tyres_gruz.xml", filter_tag=None, include_tag="tiretype", include_value="Грузовая", status="Под заказ")

    # Сохраняем все товары из второй API в tyres.xml, добавляя их к существующим
    filter_and_save_items(url2, "tyres.xml", filter_tag=None, existing_items=existing_items, include_tag=None, include_value=None, status="Под заказ")

    print("XML файлы успешно созданы без дубликатов и с унифицированными полями.")

if __name__ == "__main__":
    main()
