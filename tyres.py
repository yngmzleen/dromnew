import requests
import xml.etree.ElementTree as ET
import re
import os
from typing import Optional

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
        "img_big_my": "img_small",
        "proizvoditel": "brand"
    }
    
    normalized_item = {}
    for elem in item:
        tag = field_map.get(elem.tag, elem.tag)
        normalized_item[tag] = elem.text if elem.text else ""
    return normalized_item

def _to_number(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    s = text.strip().replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None

def adjust_retail_prices_plus10(root: ET.Element) -> None:
    """
    Проходит по всем <item> в root и увеличивает значения тегов *_rozn на 10%.
    Если существует парный базовый тег без суффикса _rozn, берём его значение как оптовую цену.
    Иначе увеличиваем текущее значение *_rozn.
    """
    for item in root.findall(".//item"):
        # Собираем карту тег -> элемент
        tag_map = {}
        for child in list(item):
            tag_map[child.tag] = child
        
        for tag, elem in tag_map.items():
            if tag.endswith("_rozn"):
                base_tag = tag[:-5]  # срезаем "_rozn"
                base_elem = tag_map.get(base_tag)
                
                base_val = _to_number(base_elem.text) if base_elem is not None else None
                rozn_val = _to_number(elem.text)
                
                # Приоритет: базовый (оптовый) тег, если он числовой; иначе текущее розничное значение
                source_val = base_val if base_val is not None else rozn_val
                if source_val is None:
                    continue  # пропускаем неликвидные/нечисловые
                
                new_val = int(round(source_val * 1.10))
                elem.text = str(new_val)

def filter_and_save_items(api_url, output_file, filter_tag=None, existing_items=None,
                          include_tag=None, include_value=None, status=None,
                          postprocess_retail_10pct=False):
    """Фильтрует товары, удаляет дубликаты, приводит поля к общему формату и сохраняет в XML-файл.
       Если postprocess_retail_10pct=True — увеличивает все *_rozn на 10% (для tyres_gruz.xml)."""
    root = fetch_xml(api_url)
    if existing_items is None:
        new_root = ET.Element("items")
    else:
        new_root = existing_items

    # Обрабатываем все товары в XML
    for item in root.findall(".//tires" if "4tochki" in api_url else ".//item"):
        # Проверяем модель перед нормализацией
        model_elem = item.find('categoryname')
        is_lt610 = model_elem is not None and model_elem.text == 'LT610'
        
        normalized_item = normalize_fields(item)  # Нормализуем поля товара
        
        # Если это модель LT610, добавляем или изменяем поле thorn
        if is_lt610:
            normalized_item['thorn'] = 'Липучка'
        cae = normalized_item.get("cae")
        unique_id = cae or normalized_item.get("article")
        if not unique_id:
            continue
        
        # Проверяем include_tag/include_value
        if include_tag and include_value:
            include_element = item.find(include_tag)
            if include_element is None or include_element.text != include_value:
                continue  # Пропускаем

        # Если filter_tag задан — сохраняем только товары, у которых этот тег существует
        if filter_tag:
            rest_element = item.find(filter_tag)
            if rest_element is not None:
                new_item = ET.SubElement(new_root, "item")
                if status:
                    status_elem = ET.SubElement(new_item, "status")
                    status_elem.text = status
                for tag, text in normalized_item.items():
                    new_elem = ET.SubElement(new_item, tag)
                    new_elem.text = text
                # LT610 -> thorn
                model_elem_new = new_item.find('model')
                if model_elem_new is not None and model_elem_new.text == 'LT610':
                    thorn_elem = new_item.find('thorn')
                    if thorn_elem is None:
                        thorn_elem = ET.SubElement(new_item, 'thorn')
                    thorn_elem.text = 'Липучка'
        else:
            # Если filter_tag не задан — исключаем товары с <rest_novosib3>
            rest_element = item.find("rest_novosib3")
            if rest_element is None:
                new_item = ET.SubElement(new_root, "item")
                if status:
                    status_elem = ET.SubElement(new_item, "status")
                    status_elem.text = status
                for tag, text in normalized_item.items():
                    new_elem = ET.SubElement(new_item, tag)
                    new_elem.text = text
                # LT610 -> thorn
                model_elem_new = new_item.find('model')
                if model_elem_new is not None and model_elem_new.text == 'LT610':
                    thorn_elem = new_item.find('thorn')
                    if thorn_elem is None:
                        thorn_elem = ET.SubElement(new_item, 'thorn')
                    thorn_elem.text = 'Липучка'
    
    # Постобработка розничных цен для этого конкретного файла (если нужно)
    if postprocess_retail_10pct:
        adjust_retail_prices_plus10(new_root)

    tree = ET.ElementTree(new_root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    return new_root

def main():
    url1 = "https://b2b.4tochki.ru/export_data/M28274.xml"
    url2 = "https://abcdisk54.ru/ftp/Brinex_shina.xml"

    # Создаем пустые файлы-шаблоны
    ET.ElementTree(ET.Element("items")).write("tyres.xml", encoding="utf-8", xml_declaration=True)
    ET.ElementTree(ET.Element("items")).write("tyres_gruz.xml", encoding="utf-8", xml_declaration=True)

    # Легковые (без rest_novosib3) -> tyres.xml
    existing_items = filter_and_save_items(
        url1, "tyres.xml",
        filter_tag=None,
        include_tag="tiretype", include_value="Легковая",
        status="Под заказ"
    )

    # Легковые (с rest_novosib3) -> tyres_nsk.xml
    filter_and_save_items(
        url1, "tyres_nsk.xml",
        filter_tag="rest_novosib3",
        include_tag="tiretype", include_value="Легковая",
        status="В наличии"
    )

    # Грузовые -> tyres_gruz.xml (и здесь делаем +10% для всех *_rozn)
    filter_and_save_items(
        url1, "tyres_gruz.xml",
        filter_tag=None,
        include_tag="tiretype", include_value="Грузовая",
        status="Под заказ",
        postprocess_retail_10pct=True  # <<< ключевая опция
    )

    # Вторая выгрузка — добавляем к легковым в tyres.xml
    filter_and_save_items(
        url2, "tyres.xml",
        filter_tag=None,
        existing_items=existing_items,
        include_tag=None, include_value=None,
        status="Под заказ"
    )

    print("XML файлы успешно созданы; в tyres_gruz.xml розничные цены *_rozn увеличены на 10%.")

if __name__ == "__main__":
    main()
