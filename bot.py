from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import dotenv, os
from selenium.webdriver.common.action_chains import ActionChains

import extract

dotenv.load_dotenv()

def get_driver_wait():
    CHROME_BROWSER_PATH = '/opt/google/chrome/google-chrome'
    CHROMEDRIVER_PATH = '/home/dhvan/Documents/baja-auto-order/chromedriver'

    chrome_options = Options()
    chrome_options.binary_location = CHROME_BROWSER_PATH

    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--headless')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    chrome_service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    wait = WebDriverWait(driver, 20)

    return driver, wait

def accept_cookie_banner(driver):
    try:
        print("-> Looking for cookie banner...")

        cookie_accept_selectors = [
            "//button[@id='CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll']",
            "//button[contains(@class, 'CybotCookiebotDialogBodyButton')]",
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Allow all')]",
            "//a[@id='CybotCookiebotDialogBodyLevelButtonAccept']"
        ]
        
        cookie_button_found = False
        for selector in cookie_accept_selectors:
            try:
                cookie_button = driver.find_element(By.XPATH, selector)
                if cookie_button.is_displayed():
                    cookie_button.click()
                    print("-> Cookie banner accepted.")
                    cookie_button_found = True
                    time.sleep(1) 
                    break
            except NoSuchElementException:
                continue
        
        if not cookie_button_found:
            print("-> No cookie banner found or already dismissed.")
            
    except Exception as e:
        print(f"-> Cookie banner handling skipped: {e}")

def ms_login(driver, wait):
    driver.get('https://metalsupermarkets.com/login')
    accept_cookie_banner(driver)

    MAX_LOGIN_ATTEMPTS = 3
    logged_in = False

    for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
        print(f"-> Attempting to log in (Attempt {attempt}/{MAX_LOGIN_ATTEMPTS})...")
        
        email_field = wait.until(EC.element_to_be_clickable((By.NAME, "msm_email")))
        email_field.clear()
        for char in os.getenv('MS_USERNAME'):
            email_field.send_keys(char)
            time.sleep(0.05)

        password_field = wait.until(EC.element_to_be_clickable((By.NAME, "msm_password")))
        password_field.clear()
        for char in os.getenv('MS_PASSWORD'):
            password_field.send_keys(char)
            time.sleep(0.05)
            
        time.sleep(1)

        sign_in_button = driver.find_element(By.XPATH, "//form[@id='loginform']//button[@type='submit']")
        ActionChains(driver).move_to_element(sign_in_button).click().perform()

        if(attempt > 1):
            wait.until(EC.url_contains('/my-account'))
            logged_in = True
            break
        else:
            time.sleep(1)
            
    if not logged_in:
        print("Not logged in")
        driver.quit()
        exit()

def mc_login(driver, wait):
    driver.get('https://www.mcmaster.com/')

    time.sleep(1)

    login_button = wait.until(EC.element_to_be_clickable((By.ID, "LoginUsrCtrlWebPart_LoginLnk")))
    login_button.click()

    email_field = wait.until(EC.element_to_be_clickable((By.ID, "Email")))
    email_field.clear()
    for char in os.getenv('MC_USERNAME'):
        email_field.send_keys(char)
        time.sleep(0.05)

    password_field = wait.until(EC.element_to_be_clickable((By.ID, "Password")))
    password_field.clear()
    for char in os.getenv('MC_PASSWORD'):
        password_field.send_keys(char)
        time.sleep(0.05)

    time.sleep(1)

    sign_in_button = driver.find_element(By.XPATH, "//input[@type='submit' and @value='Log in']")
    ActionChains(driver).move_to_element(sign_in_button).click().perform()

    time.sleep(2)

    print("-> Logged In")

# NEEDS pro_link, pro_sku, pro_width, pro_length, sel_quantity
def ms_add_to_cart(driver, wait, data):
    for item in data:
        item_details = {prop[0]: prop[1] for prop in item}
        print(f"Processing: ({item_details['pro_sku']})")

        try:
            driver.get(item_details['pro_link'])
            item_sku = item_details['pro_sku']
            xpath_selector = f"//tr[.//input[@name='pro_sku' and @value='{item_sku}']]"
            product_row = wait.until(EC.presence_of_element_located((By.XPATH, xpath_selector)))

            if 'pro_width' in item_details:
                width_input = product_row.find_element(By.CLASS_NAME, 'pro_width')
                width_input.clear()
                width_input.send_keys(item_details['pro_width'])

            length_input = product_row.find_element(By.CLASS_NAME, 'pro_length')
            length_input.clear()
            length_input.send_keys(item_details['pro_length'])

            quantity_input = product_row.find_element(By.CLASS_NAME, 'sel_quantity')
            quantity_input.clear()
            quantity_input.send_keys(item_details['sel_quantity'])

            time.sleep(1)

            print("-> Waiting for button overlay to disappear...")
            button_cell = product_row.find_element(By.CLASS_NAME, 'productbtn')
            loader_overlay = button_cell.find_element(By.CLASS_NAME, 'price-loader')
            wait.until(EC.invisibility_of_element(loader_overlay))
            print("-> Overlay gone. Button is clear.")

            # 3. Now find the button and click it
            add_to_cart_button = button_cell.find_element(By.CLASS_NAME, 'addtocart')
            
            driver.execute_script("arguments[0].click();", add_to_cart_button)

            print(f"-> Successfully added {item_details['pro_sku']} to cart.")
            time.sleep(1)
        except:
            pass

# NEEDS: part_number, quantity, extra_attr
def mc_add_to_cart(driver, wait, data):
    quantity_xpath = "//input[contains(@class, 'input-simple--qty')] | //label[contains(., 'Quantity')]/preceding-sibling::input"
    add_button_xpath = "//button[contains(@class, 'add-to-order-pd')] | //button[contains(., 'ADD TO ORDER')]"
    for item in data:
        item_details = {prop[0]: prop[1] for prop in item}
        print(f"-> Processing: {item_details['part_number']}")
        driver.get(item_details['link'])
        
        quantity_input = wait.until(
            EC.presence_of_element_located((By.XPATH, quantity_xpath))
        )
        wait.until(EC.element_to_be_clickable(quantity_input))
        quantity_input.clear()
        quantity_input.send_keys(item_details['quantity'])

        add_button = wait.until(
            EC.presence_of_element_located((By.XPATH, add_button_xpath))
        )
        wait.until(EC.element_to_be_clickable(add_button))
        add_button.click()

        if(len(item) > 3):
            wait.until(EC.element_to_be_clickable(add_button))
            add_button.click()

def mc_paste_cart(driver, wait, data):
    driver.get('https://mcmaster.com/order')

    short_wait = WebDriverWait(driver, 2)

    try:
        switch_button = short_wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, 'switch-mode-link'))
        )
    except:
        print('Items are probably in cart, need to click add line')
        add_line_button = short_wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, 'order-pad-add-line'))
        )

        # add_line_button.click()
        driver.execute_script("arguments[0].click();", add_line_button)

        switch_button = short_wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, 'switch-mode-link'))
        )

    # switch_button.click()
    driver.execute_script("arguments[0].click();", switch_button)

    bulk_input = wait.until(
        EC.element_to_be_clickable((By.ID, 'bulk-lines-textarea'))
    )

    for item in data:
        item_details = {prop[0]: prop[1] for prop in item}
        bulk_input.send_keys(f'{item_details['part_number']}, {item_details['quantity']}\n')
        print(f'Added item: {item_details["part_number"]}')

    submit_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'button-add-bulk-lines')]"))
    )

    submit_button.click()

def metal_supermarkets(data):
    driver, wait = get_driver_wait()
    ms_login(driver, wait)
    ms_add_to_cart(driver, wait, data)

def mcmaster(data):
    driver, wait = get_driver_wait()
    mc_login(driver, wait)
    mc_paste_cart(driver, wait, data)
    # mc_add_to_cart(driver, wait, data)

def add_to_cart(csv_data):
    print('-> Starting process')
    ms, mc = extract.raw_to_array(csv_data)

    if(len(ms) >= 1):
        metal_supermarkets(ms)
    if(len(mc) >= 1):
        mcmaster(mc)
    
    print('-> ALL DONE')