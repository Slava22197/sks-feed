#!/usr/bin/env python3
# sks_xml.py
# Формує products.xml з SKS API

import os
import requests
import hashlib
import base64
import datetime
import xml.etree.ElementTree as ET

# ---- Конфіг ----
SKS_PASSWORD = os.environ.get("SKS_PASSWORD", "e887471317b2554442c165557e442093")
SKS_CLIENTID = os.environ.get("SKS_CLIENTID", "00048")
IMG_BASE = os.environ.get("IMG_BASE", "https://imga.sks-service.org/new/")
API_URL = os.environ.get("API_URL", "http://sks-service.org/api/v2.0/")

# ---- Хелпери ----
def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def make_signature(typeRequest, dateTime):
    raw = f"{SKS_PASSWORD}{SKS_CLIENTID}{typeRequest}{dateTime}{SKS_PASSWORD}"
    return base64.b64encode(hashlib.sha1(raw.encode("utf-8")).digest()).decode()

def api_call(typeRequest, timeout=30):
    dateTime = now_str()
    data = {
        "clientID": SKS_CLIENTID,
        "typeRequest": typeRequest,
        "dateTime": dateTime,
        "signature": make_signature(typeRequest, dateTime),
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json; charset=UTF-8"}
    r = requests.post(API_URL, json=data, headers=headers, timeout=timeout)
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}: {r.text}")
    j = r.json()
    if j.get("state") != "SUCCESS":
        raise Exception(f"API FAIL for {typeRequest}: {j}")
    return j

def get_categories():
    # пробуємо обидва варіанти (лат. і кир. С)
    for t in ("req\u0421ategories", "reqCategories"):
        try:
            return api_call(t).get("categories", [])
        except Exception:
            continue
    return []

def get_products():
    return api_call("reqAllProducts").get("products", [])

def extract_all_images(prod, max_extra=10):
    imgs = []
    base_url = prod.get("imageURL")
    if base_url:
        filename = base_url.strip().split("/")[-1]
        imgs.append(IMG_BASE.rstrip("/") + "/" + filename)
        if filename.lower().endswith(".jpg"):
            base_no_ext = filename[:-4]
            for i in range(1, max_extra + 1):
                imgs.append(f"{IMG_BASE.rstrip('/')}/{base_no_ext}-{i}.jpg")
    return imgs

def calc_price(purchase):
    p = float(purchase)
    if p < 0.1:
        return p * 4.5
    elif p < 0.3:
        return p * 3.3
    elif p < 0.75:
        return p * 2.7
    elif p < 2:
        return p * 1.85
    elif p < 5:
        return p * 1.65
    elif p < 10:
        return p * 1.55
    elif p < 20:
        return p * 1.5
    elif p < 30:
        return p * 1.43
    elif p < 50:
        return p * 1.38
    elif p < 75:
        return p * 1.35
    elif p < 100:
        return p * 1.33
    else:
        return p * 1.3

def write_xml(categories, products, out_file="products.xml"):
    yml_date = now_str()
    root = ET.Element("yml_catalog", attrib={"date": yml_date})
    shop = ET.SubElement(root, "shop")
    ET.SubElement(shop, "name").text = "SKS"

    # currencies
    currencies_el = ET.SubElement(shop, "currencies")
    ET.SubElement(currencies_el, "currency", attrib={"id": "USD", "rate": "1"})

    # categories
    categories_el = ET.SubElement(shop, "categories")
    for cat in categories:
        raw_id = str(cat.get("categoryID", "")).strip()
        attrs = {}
        if "/" in raw_id:
            parts = raw_id.split("/")
            attrs["id"] = parts[0]
            attrs["parentId"] = parts[1] if len(parts) > 1 else ""
        else:
            attrs["id"] = raw_id
            parent = cat.get("parentCategoryID") or cat.get("parentID")
            if parent and str(parent) not in ("0", ""):
                attrs["parentId"] = str(parent)
        el = ET.SubElement(categories_el, "category", attrib=attrs)
        el.text = str(cat.get("categoryNameUA") or cat.get("categoryName") or "").strip()

    # offers
    offers = ET.SubElement(shop, "offers")
    for prod in products:
        offer = ET.SubElement(offers, "offer", attrib={"id": str(prod.get("productID", ""))})

        ET.SubElement(offer, "name").text = str(prod.get("productNameUA") or prod.get("productName") or "")

        # purchase and calculated price
        raw_price = str(prod.get("priceUSD") or "0").replace(",", ".")
        try:
            purchase_price = float(raw_price)
        except Exception:
            purchase_price = 0.0
        ET.SubElement(offer, "purchase_price").text = f"{purchase_price:.2f}"
        ET.SubElement(offer, "price").text = f"{calc_price(purchase_price):.2f}"
        ET.SubElement(offer, "currencyId").text = "USD"

        # availability -> available (true/false per rule) and quantity
        avail = str(prod.get("availability", "")).strip()
        if avail in ("1", "2"):
            ET.SubElement(offer, "available").text = "true"
        else:
            ET.SubElement(offer, "available").text = "false"

        qty = "0"
        if avail == "1":
            qty = "1"
        elif avail == "2":
            qty = "100"
        ET.SubElement(offer, "quantity").text = qty

        # categoryId (тільки перша частина до "/")
        if prod.get("categoryID"):
            cat_raw = str(prod.get("categoryID"))
            if "/" in cat_raw:
                cat_id = cat_raw.split("/")[0]
            else:
                cat_id = cat_raw
            ET.SubElement(offer, "categoryId").text = cat_id

        # vendor / article / model
        if prod.get("brand") or prod.get("brandUA"):
            ET.SubElement(offer, "vendor").text = str(prod.get("brandUA") or prod.get("brand"))
        if prod.get("article"):
            ET.SubElement(offer, "article").text = str(prod.get("article"))
        if prod.get("vendorCode"):
            ET.SubElement(offer, "model").text = str(prod.get("vendorCode"))
        if prod.get("weight"):
            ET.SubElement(offer, "weight").text = str(prod.get("weight"))

        # images
        for img in extract_all_images(prod, max_extra=10):
            ET.SubElement(offer, "picture").text = img

        # description (мінімальна)
        desc_parts = []
        if prod.get("amountInPackage"):
            desc_parts.append(f"Кількість в упаковці: {prod.get('amountInPackage')}")
        if desc_parts:
            ET.SubElement(offer, "description").text = " | ".join(desc_parts)

    tree = ET.ElementTree(root)
    tree.write(out_file, encoding="utf-8", xml_declaration=True)
    print(f"✅ Written {out_file}")

def main():
    cats = []
    prods = []
    try:
        print("Отримую категорії...")
        cats = get_categories()
    except Exception as e:
        print("Помилка категорій:", e)
    try:
        print("Отримую продукти...")
        prods = get_products()
    except Exception as e:
        print("Помилка продуктів:", e)
        raise
    write_xml(cats, prods, out_file="products.xml")

if __name__ == "__main__":
    main()
