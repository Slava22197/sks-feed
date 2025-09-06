import requests
import hashlib
import base64
import datetime
import xml.etree.ElementTree as ET
import pytz

# --- Параметри API (відкрито) ---
URL = "http://sks-service.org/api/v2.0/"
password = "e887471317b2554442c165557e442093"
clientID = "00048"

# --- Хелпер: отримати поточний час у Києві ---
def get_datetime():
    kyiv_tz = pytz.timezone("Europe/Kyiv")
    return datetime.datetime.now(kyiv_tz).strftime("%Y-%m-%d %H:%M")

# --- Хелпер: запит до API ---
def api_call(typeRequest):
    dateTime = get_datetime()
    signature_raw = password + clientID + typeRequest + dateTime + password
    signature = base64.b64encode(hashlib.sha1(signature_raw.encode("utf-8")).digest()).decode()

    data = {
        "clientID": clientID,
        "typeRequest": typeRequest,
        "dateTime": dateTime,
        "signature": signature
    }

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "UTF-8",
        "Content-Type": "application/json; charset=UTF-8"
    }

    print(f"--> API call: {typeRequest} @ {dateTime}")
    r = requests.post(URL, json=data, headers=headers)
    print("<-- HTTP", r.status_code)

    if r.status_code != 200:
        raise Exception(f"HTTP error {r.status_code}: {r.text}")

    j = r.json()
    if j.get("state") != "SUCCESS":
        print(f"⚠️ {typeRequest} failed: API FAIL for {typeRequest}: {j}")
        return {}
    return j

# --- Завантаження категорій ---
def get_categories():
    resp = api_call("reqCategories")
    return resp.get("categories", [])

# --- Завантаження продуктів ---
def get_products():
    resp = api_call("reqAllProducts")
    return resp.get("products", [])

# --- Конвертація availability ---
def map_availability(av):
    if av in ("1", 1):
        return ("true", "1")
    elif av in ("2", 2):
        return ("true", "100")
    else:
        return ("false", "0")

# --- Націнка ---
def apply_markup(price):
    try:
        p = float(price)
    except:
        return price

    if p <= 0.1: return round(p * 4.5, 2)
    if p <= 0.3: return round(p * 3.3, 2)
    if p <= 0.75: return round(p * 2.7, 2)
    if p <= 2: return round(p * 1.85, 2)
    if p <= 5: return round(p * 1.65, 2)
    if p <= 10: return round(p * 1.55, 2)
    if p <= 20: return round(p * 1.5, 2)
    if p <= 30: return round(p * 1.43, 2)
    if p <= 50: return round(p * 1.38, 2)
    if p <= 75: return round(p * 1.35, 2)
    if p <= 100: return round(p * 1.33, 2)
    return round(p * 1.3, 2)

# --- Формування XML ---
def write_xml(cats, prods):
    yml = ET.Element("yml_catalog", date=get_datetime())
    shop = ET.SubElement(yml, "shop")

    categories = ET.SubElement(shop, "categories")
    for c in cats:
        cat_raw = str(c.get("categoryID", ""))
        if "/" in cat_raw:
            cid, parent = cat_raw.split("/", 1)
        else:
            cid, parent = cat_raw, ""
        cat_el = ET.SubElement(categories, "category", id=cid)
        if parent:
            cat_el.set("parentId", parent)
        cat_el.text = c.get("categoryNameUA") or c.get("categoryName") or ""

    offers = ET.SubElement(shop, "offers")
    for p in prods:
        offer = ET.SubElement(offers, "offer", id=str(p.get("productID", "")))

        # categoryId (тільки перша частина)
        cat_raw = str(p.get("categoryID", ""))
        cat_id = cat_raw.split("/")[0] if "/" in cat_raw else cat_raw
        ET.SubElement(offer, "categoryId").text = cat_id

        # Назви
        ET.SubElement(offer, "name").text = p.get("productNameUA") or p.get("productName") or ""
        ET.SubElement(offer, "vendor").text = p.get("brand", "")
        ET.SubElement(offer, "vendorCode").text = p.get("vendorCode", "")
        ET.SubElement(offer, "article").text = p.get("article", "")

        # Ціни
        base_price = p.get("priceUSD", 0)
        ET.SubElement(offer, "priceUSD").text = str(base_price)
        ET.SubElement(offer, "price").text = str(apply_markup(base_price))

        # Вага
        ET.SubElement(offer, "weight").text = str(p.get("weight", ""))

        # Наявність і кількість
        av, qty = map_availability(p.get("availability"))
        ET.SubElement(offer, "available").text = av
        ET.SubElement(offer, "quantity").text = qty

        # Фото (основне + додаткові)
        img = p.get("imageURL")
        if img:
            ET.SubElement(offer, "picture").text = img
            for i in range(1, 6):
                extra = img.replace(".jpg", f"-{i}.jpg")
                ET.SubElement(offer, "picture").text = extra

    tree = ET.ElementTree(yml)
    tree.write("products.xml", encoding="utf-8", xml_declaration=True)
    print("✅ Written products.xml")

# --- Основна логіка ---
def main():
    print("Отримую категорії...")
    cats = get_categories()

    print("Отримую продукти...")
    prods = get_products()

    write_xml(cats, prods)

if __name__ == "__main__":
    main()
