from collections import defaultdict
import pprint
import bs4, csv
from datetime import datetime
import dotenv, os
import requests
from concurrent.futures import ThreadPoolExecutor

dotenv.load_dotenv()

def html_ms(filename, input_content=None):
    if(input_content): 
        html_content = input_content
    else:
        with open(filename, 'r', encoding='utf-8') as f:
            html_content = f.read()


    soup = bs4.BeautifulSoup(html_content, 'lxml')
    cart_items = soup.select('[id^="cartitem_"]')
    output_cart = []

    for item in cart_items:
        output_item = []
        item_name = item.select_one('h3.product-name').string
        item_info = item.select_one('p.product-info').string
        output_item.append(['pro_name', item_name])
        output_item.append(['pro_info', item_info])
        output_item.append(['pro_link', f'https://www.metalsupermarkets.com/product/{item_name.lower().replace(" ", "-")}'])
        item_inputs = item.select('input')
        for input in item_inputs:
            try:
                output_item.append([input['name'], input['value']])
            except:
                output_item.append([input['class'][0], input['value']])
        output_cart.append(output_item)

    return output_cart

def html_mc(filename, input_content = None):
    if(input_content): 
        html_content = input_content
    else: 
        with open(filename, 'r', encoding='utf-8') as f:
            html_content = f.read()


    soup = bs4.BeautifulSoup(html_content, 'lxml')
    cart_items = soup.select('[class="order-pad-line"]')
    output_cart = []
    for item in cart_items:
        # print(item)
        part_number = item.select_one('[id^="line-part-number-input"]')['value']
        quantity = item.select_one('[id^="line-quantity-input"]')['value']
        price = item.select_one('[class*="line-unit-price"]').get_text().split()[0]
        title = item.select_one('[class*=title-text]').get_text()
        description = item.select_one('[class*=description-print--view]').get_text()

        # Assumes that mcmaster only ever has 1 extra attribute
        extra_attr = item.select_one('[class="inline-spec-attribute-text-with-input"]')
        if(extra_attr): extra_attr = extra_attr.get_text()
        output_cart.append([
            ['title', title],
            ['description', description],
            ['part_number', part_number],
            ['quantity', quantity],
            ['price', price],
            ['extra_attr', extra_attr]
        ])

    return output_cart

def array_to_csv(data, output_filename):
    all_keys = set()
    for item in data:
        for kv in item:
            all_keys.add(kv[0])

    header = sorted(list(all_keys))

    with(open(output_filename, 'w', newline='', encoding='utf-8') as f):
        writer = csv.DictWriter(f, fieldnames=header)
        # writer.writeheader()

        for item in data:
            item_dict = {kv[0]: kv[1] for kv in item}
            writer.writerow(item_dict)

def raw_to_array(raw_input):
    header = ['ordered', 'approved', 'vendor', 'part_number', 'description', 'unit_price', 'quantity', 'dimensions', 'link']
    mc = []
    ms = []

    for input_str in raw_input:
        item_list = input_str.split('||')
        item = [[key, value] for key, value in zip(header, item_list)]

        item_dict = {kv[0].strip(): kv[1].strip() for kv in item}

        if(item_dict['vendor'] == "MetalSupermarkets"):
            dims = item_dict['dimensions'].split('X')
            ms_item = {
                'pro_link': item_dict['link'],
                'pro_sku': item_dict['part_number'],
                'pro_length': dims[0].strip(),
                'sel_quantity': item_dict['quantity']
            }

            if(len(dims) > 1):
                ms_item['pro_width'] = dims[1]
            ms.append(list(ms_item.items()))
        
        elif(item_dict['vendor'] == "McMaster"):
            dims = item_dict['dimensions']
            mc_item = {
                'part_number': item_dict['part_number'],
                'quantity': item_dict['quantity'],
                'link': item_dict['link']
            }

            if(dims):
                mc_item['extra_attr'] = dims.strip()

            mc.append(list(mc_item.items()))

    return (ms, mc)

        
def csv_to_array(input_filename):
    header = ['ordered', 'approved', 'vendor', 'part_number', 'description', 'unit_price', 'quantity', 'dimensions', 'link']
    mc = []
    ms = []

    with(open(input_filename, 'r') as f):
        items = f.readlines()

        for item_str in items:
            item_list = item_str.split('||')
            item = [[key, value] for key, value in zip(header, item_list)]

            item_dict = {kv[0].strip(): kv[1].strip() for kv in item}

            if(item_dict['vendor'] == "MetalSupermarkets"):
                dims = item_dict['dimensions'].split('X')
                ms_item = {
                    'pro_link': item_dict['link'],
                    'pro_sku': item_dict['part_number'],
                    'pro_length': dims[0].strip(),
                    'sel_quantity': item_dict['quantity']
                }

                if(len(dims) > 1):
                    ms_item['pro_width'] = dims[1]
                ms.append(list(ms_item.items()))
            
            elif(item_dict['vendor'] == "McMaster"):
                dims = item_dict['dimensions']
                mc_item = {
                    'part_number': item_dict['part_number'],
                    'quantity': item_dict['quantity'],
                    'link': item_dict['link']
                }

                if(dims):
                    mc_item['extra_attr'] = dims.strip()

                mc.append(list(mc_item.items()))

    return (ms, mc)

def send_request(link):
    try:
        requests.get(link, timeout=10)
        print("Submitted part request")
    except requests.RequestException as e:
        print(f'Failed to send request, error: {e}')


def create_vendor_part(vendor, item):
    if(vendor == "MetalSupermarkets"):
        dimensions = item.get('pro_length', -1)
        if(item.get('pro_width')):
            dimensions = f'{item.get("pro_length")} X {item.get("pro_width")}'

        link = f'https://www.metalsupermarkets.com/product/{item.get('pro_name').lower().replace(" ", "-")}'

        return {
            'vendor': 'MetalSupermarkets',
            'part_number': item.get('pro_sku', 'N/A'),
            'description': f'{item.get('pro_name', 'N/A')}, {item.get('pro_info')}',
            'unit_price': item.get('price_value', -1),
            'quantity': item.get('sel_quantity', -1),
            'dimensions': dimensions,
            'url': link
        }
    if(vendor == "McMaster"):        
        return {
            'vendor': 'McMaster',
            'part_number': item.get('part_number', 'N/A'),
            'description': f'{item.get("title", "N/A")}, {item.get("description", "N/A")}',
            'unit_price': item.get('price', -1),
            'quantity': item.get('quantity', ''),
            'dimensions': item.get('extra_attr', ''),
            'url': f'https://mcmaster.com/{item.get('part_number', '')}'
        }


def submit(vendor, data):
    form_link_template = os.getenv('SUBMIT_FORM_LINK')
    
    request_list = []
    for item in data:
        item_dict = {kv[0]: kv[1] for kv in item}
        form_link_filled = form_link_template.format_map(create_vendor_part(vendor, item_dict))
        request_list.append(form_link_filled)

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(send_request, request_list)
    
    print(f'All {len(data)} parts have been submitted')

def metal_supermarkets(html_filepath, input_content=None):
    data = html_ms(html_filepath, input_content)
    submit('MetalSupermarkets', data)

def mcmaster(html_filepath, input_content=None):
    print('Method Called')
    data = html_mc(html_filepath, input_content)
    submit('McMaster', data)
    return data

# mcmaster('inputs/mc.html')
# metal_supermarkets('inputs/cart.html')
# html_mc('inputs/mc.html')
# csv_to_array('output.csv')