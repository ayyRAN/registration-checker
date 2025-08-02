# import threading
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from twilio.rest import Client
from dotenv import load_dotenv
import os

COURSES = [367, 414, 322, 320, 465, 340, 472]  # your courses
SUBJECT = "Computer Science"
TERMS = [
    # ("Fall 2025", "//div[@id='select2-result-label-4']/.."),
    ("Winter 2026", "//div[@id='select2-result-label-3']/..")
]


load_dotenv("creds.env")
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_number = os.getenv("TWILIO_NUMBER")
my_number = os.getenv("MY_NUMBER")
client = Client(account_sid, auth_token)

def send_sms(message):
    client.messages.create(
        body=message,
        from_=twilio_number,
        to=my_number
    )

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")  # Faster loading
    options.add_argument("--log-level=3")
    
    if os.getenv('GITHUB_ACTIONS'):
        # In GitHub Actions, use system Chrome
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    else:
        # Local development
        service = Service(executable_path="chromedriver.exe")
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://loris.wlu.ca/register/ssb/term/termSelection?mode=courseSearch")
    return driver

def click_term_dropdown(driver, wait):
    term = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Select a term...']/..")))
    term.click()
    return True

def click_specific_term(driver, wait, term_xpath):
    dropdown_option = wait.until(EC.visibility_of_element_located((By.XPATH, term_xpath)))
    dropdown_option.click()
    continue_button = wait.until(EC.element_to_be_clickable((By.ID, "term-go")))
    continue_button.click()
    return True

def click_subject_input_and_type(driver, wait, subject_name):
    subject = wait.until(EC.element_to_be_clickable((By.ID, 's2id_txt_subject')))
    subject.click()
    input_subject = wait.until(lambda d: subject.find_element(By.ID, 's2id_autogen1'))
    input_subject.send_keys(subject_name)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(@class,'select2-results')]//div[contains(text(), '" + subject_name + "')]")))
    input_subject.send_keys("\n")
    return True

def click_course_input_and_type(driver, wait, course_num):
    course_number = wait.until(EC.element_to_be_clickable((By.ID, 'txt_courseNumber')))
    course_number.click()
    course_number.clear()
    course_number.send_keys(f'{course_num}\n')
    return True

def click_search_button(driver, wait):
    search_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'form-button') and contains(@class, 'search-section-button')]")))
    search_button.click()
    return True

def check_if_course_exists(driver):
    """Check if course exists by looking for specific indicators"""
    try:
        # First, check for explicit "no results" or "not found" messages
        no_sections_messages = [
            "//div[contains(text(), 'No sections found')]",
            "//div[contains(text(), 'no sections')]",
            "//div[contains(text(), 'No results')]",
            "//p[contains(text(), 'No sections found')]",
            "//div[contains(text(), 'Course not found')]",
            "//div[contains(@class, 'no-results')]"
        ]
        
        for xpath in no_sections_messages:
            try:
                element = driver.find_element(By.XPATH, xpath)
                if element.is_displayed():
                    return False  # Course doesn't exist or has no sections
            except NoSuchElementException:
                continue
        
        # Check if we find a "View Sections" button (more specific xpath)
        view_sections_xpaths = [
            "//button[contains(@aria-label, 'View Sections')]",
            "//button[contains(@class, 'section-details-button')]",
            "//a[contains(text(), 'View Sections')]"
        ]
        
        for xpath in view_sections_xpaths:
            try:
                element = driver.find_element(By.XPATH, xpath)
                if element.is_displayed():
                    return True  # Course exists
            except NoSuchElementException:
                continue
        
        # If no explicit indicators, assume course exists and let the expand function handle it
        return True
            
    except Exception as e:
        print(f"Error checking if course exists: {e}")
        return True  # Default to assuming it exists

def click_expand_course(driver, wait, course_num):
    """Try to expand course sections with better error handling"""
    xpath = f"//button[contains(@aria-label, 'CP {course_num} View Sections') or contains(@aria-label, '{course_num} View Sections')]"
    
    try:
        # First check if the expand button exists
        expand_button = driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].scrollIntoView(true);", expand_button)
        time.sleep(0.5)  # Brief pause after scrolling
        expand_button.click()
        print(f"[Step 7] Clicked 'View Sections' for course {course_num}")
        
        # Wait for sections to load with a shorter timeout
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "section-content")))
            print(f"[Step 8] Sections loaded for course {course_num}")
            return True
        except TimeoutException:
            # Try alternative selectors for section content
            alternative_selectors = [
                "//td[@data-property='status']",
                "//table[contains(@class, 'sections')]", 
                "//div[contains(@class, 'section-detail')]"
            ]
            
            for selector in alternative_selectors:
                try:
                    driver.find_element(By.XPATH, selector)
                    print(f"[Step 8] Sections found for course {course_num} (using alternative selector)")
                    return True
                except NoSuchElementException:
                    continue
            
            print(f"[Step 8] Sections may not have loaded for course {course_num}, but continuing...")
            return True  # Continue anyway
            
    except NoSuchElementException:
        return False
    except Exception as e:
        print(f"[Step 7] Error expanding course {course_num}: {e}")
        return False

def get_course_status(driver, wait, course_num, term_name):
    """Extract course status information with better error handling"""
    try:
        # Wait for status cells with a reasonable timeout
        status_cells = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, '//td[@data-property="status"]'))
        )
        
        if status_cells:
            section_count = 0
            for cell in status_cells:
                try:
                    title = cell.get_attribute('title')
                    if not title:
                        continue
                    
                    section_count += 1
                    title = title.upper().replace("  ", " ").strip()
                    main_seats = 0
                    waitlist_seats = 0
                    is_full = False

                    # Parse the title to extract seat information
                    if "FULL:" in title:
                        is_full = True
                        parts = title.split(".")
                        for part in parts:
                            part = part.strip()
                            if part.startswith("FULL:"):
                                try:
                                    # Extract seats from "FULL: X OF Y"
                                    seat_info = part.split("FULL:")[1].strip()
                                    if "OF" in seat_info:
                                        available = int(seat_info.split("OF")[0].strip())
                                        main_seats = available  # This should be 0 for full classes
                                except:
                                    main_seats = 0
                            elif "WAITLIST" in part and "OF" in part:
                                try:
                                    # Extract waitlist info "X OF Y WAITLIST"
                                    waitlist_available = int(part.split("OF")[0].strip())
                                    waitlist_seats = waitlist_available
                                except:
                                    waitlist_seats = 0
                    else:
                        # Not full, extract available seats
                        try:
                            if "OF" in title:
                                main_seats = int(title.split("OF")[0].strip())
                            else:
                                main_seats = 0
                        except:
                            main_seats = 0

                    # Determine status
                    if is_full and waitlist_seats == 0:
                        status = "Full"
                    elif main_seats > 0 or waitlist_seats > 0:
                        status = "Open"
                    else:
                        status = "Full"
                    
                    # Format output similar to your original
                    section_info = f"Section {section_count}" if section_count > 1 else ""
                    result = f"{term_name} | CP {course_num} {section_info}: {status}"
                    
                    # Add seat details for debugging
                    if main_seats > 0:
                        result += f" ({main_seats} seats)"
                    if waitlist_seats > 0:
                        result += f" ({waitlist_seats} waitlist)"
                    
                    print(result)

                    # Uncomment to send SMS when open
                    if status == "Open":
                        send_sms(result)
                    
                except Exception as e:
                    print(f"Error processing status cell {section_count} for course {course_num}: {e}")
                    continue
                    
            if section_count == 0:
                print(f"{term_name} | Course CP {course_num}: No sections with status found")
        else:
            print(f"{term_name} | Course CP {course_num}: No status information found")
            
    except TimeoutException:
        print(f"{term_name} | Course CP {course_num}: Status information not loaded in time")
    except Exception as e:
        print(f"{term_name} | Course CP {course_num}: Error getting status - {e}")

def check_term_courses(term_name, term_xpath):
    driver = setup_driver()
    wait = WebDriverWait(driver, 10)  # Increased timeout for main operations

    try:
        # Step 1: Click term dropdown
        click_term_dropdown(driver, wait)

        # Step 2: Select specific term
        click_specific_term(driver, wait, term_xpath)
        time.sleep(2)  # wait for page load after term selection

        # Step 3: Select subject and type it
        click_subject_input_and_type(driver, wait, SUBJECT)
        time.sleep(1)

        for course_num in COURSES:
            try:
                # Step 4: Enter course number
                click_course_input_and_type(driver, wait, course_num)
                time.sleep(1)

                # Step 5: Click search sections button
                click_search_button(driver, wait)
                time.sleep(3)  # wait for results

                # Step 6: Check if course exists before trying to expand
                course_exists = check_if_course_exists(driver)
                
                if not course_exists:
                    print(f"{term_name} | Course CP {course_num}: Not available this term")
                else:
                    # Step 7: Try to expand course sections
                    expanded = click_expand_course(driver, wait, course_num)
                    if expanded:
                        # Step 8: Get course status
                        get_course_status(driver, wait, course_num, term_name)
                    else:
                        # Even if expand failed, try to get status in case sections are already visible
                        try:
                            status_cells = driver.find_elements(By.XPATH, '//td[@data-property="status"]')
                            if status_cells:
                                get_course_status(driver, wait, course_num, term_name)
                            else:
                                print(f"{term_name} | Course CP {course_num}: Could not access sections")
                        except Exception as e:
                            print(f"{term_name} | Course CP {course_num}: Could not access sections - {e}")

            except Exception as e:
                print(f"Error processing course {course_num}: {e}")
                # Continue with next course even if this one fails

            # Step 9: Navigate back for next course
            try:
                return_button = driver.find_element(By.XPATH, "//a[contains(@class, 'form-button') and contains(@class, 'return-course-button')]")
                return_button.click()
                
                search_again_button = wait.until(EC.element_to_be_clickable((By.ID, 'search-again-button')))
                search_again_button.click()
                time.sleep(1)
                
            except Exception as e:
                print(f"Error navigating back after course {course_num}: {e}")
                # If navigation fails, we might need to refresh or restart
                break

    except Exception as e:
        print(f"Fatal error in check_term_courses: {e}")
    finally:
        driver.quit()

# def main():
#     threads = []
#     for term_name, term_xpath in TERMS:
#         t = threading.Thread(target=check_term_courses, args=(term_name, term_xpath))
#         t.start()
#         threads.append(t)
#         print(threads)
#     for t in threads:
#         t.join()

if __name__ == "__main__":
    for term_name, term_xpath in TERMS:
        print(f"\n{'='*50}")
        print(f"Checking {term_name}")
        print(f"{'='*50}")
        check_term_courses(term_name, term_xpath)




