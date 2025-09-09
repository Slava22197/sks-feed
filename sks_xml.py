#!/usr/bin/env python3
# sks_xml.py
# Формує products.xml з SKS API

import requests
import hashlib
import base64
import datetime
import pytz
import time
import xml.etree.ElementTree as ET

# ---- Конфіг ----
SKS_PASSWORD = "e887471317b2554442c165557e442093"
SKS_CLIENTID = "00048"
IMG_BASE = "https://imga.sks-service.org/new/"
API_URL = "http://sks-service.org/api/v2.0/"

# ---- Хелпери ----
def now_str():
    tz = pytz.timezone("Europe/Kyiv")
    return datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")

def make_signature(typeRequest, dateTime):
    raw = f"{SKS_PASSWORD}{SKS_CLIENTID}{typeRequest}{dateTime}{SKS_PASSWORD}"
    sig = base64.b64encode(hashlib.sha1(raw.encode("utf-8")).digest()).decode()
    print("DEBUG: dateTime =", dateTime)
    print("DEBUG: typeRequest =", typeRequest)
    print("DEBUG: signature_raw =", raw)
    print("DEBUG: signature =", sig)
    return sig

def api_call(typeRequest, timeout=30):
    dateTime = now_str()
    data = {
        "clientID": SKS_CLIENTID,
        "typeRequest": typeRequest,
        "dateTime": dateTime,
        "signature": make_signature(typeRequest, dateTime),
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json; charset=UTF-8"}
    print(f"--> API call: {typeRequest} @ {dateTime}")
    r = requests.post(API_URL, json=data, headers=headers, timeout=timeout)
    print("<-- HTTP", r.status_code)
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}: {r.text}")
    j = r.json()
    if j.get("state") != "SUCCESS":
        print(f"⚠️ {typeRequest} failed: API FAIL for {typeRequest}: {j}")
        raise Exception(f"API FAIL for {typeRequest}: {j}")
    return j

# ---- Категорії ----
def get_categories():
    for t in ("reqСategories", "reqCategories"):  # кирилична + латинська
        try:
            return api_call(t).get("categories", [])
        except Exception as e:
            print("DEBUG: fail with", t, e)
            continue
    return []

# ---- Продукти з обробкою error=9 ----
def get_products():
    while True:
        try:
            return api_call("reqAllProducts").get("products", [])
        except Exception as e:
            if "error': 9" in str(e):
                print("⚠️ Перевищено ліміт! Чекаю 3700 секунд (1 год + запас)...")
                time.sleep(3700)
                continue
            raise

# ---- XML ----
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

        raw_price = str(prod.get("priceUSD") or "0").replace(",", ".")
        try:
            purchase_price = float(raw_price)
        except Exception:
            purchase_price = 0.0
        ET.SubElement(offer, "purchase_price").text = f"{purchase_price:.2f}"
        ET.SubElement(offer, "price").text = f"{purchase_price:.2f}"
        ET.SubElement(offer, "currencyId").text = "USD"

        avail = str(prod.get("availability", "")).strip()
        ET.SubElement(offer, "availability").text = avail

    tree = ET.ElementTree(root)
    tree.write(out_file, encoding="utf-8", xml_declaration=True)
    print(f"✅ Written {out_file}")

# ---- Main ----
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
    write_xml(cats, prods, out_file="products.xml")

if __name__ == "__main__":
    main()
