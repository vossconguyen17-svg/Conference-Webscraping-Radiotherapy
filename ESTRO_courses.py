import os
import pandas as pd
from playwright.sync_api import sync_playwright

def clean_deadline_text(text, start_date):
    """
    Standardized cleaner for both Courses and Congresses.
    Handles '48 hours before', bracketed text, and noise words.
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # 1. Handle the standard Course rule: 48 hours before start
    if "48 hours before" in text_lower and start_date:
        return start_date - pd.Timedelta(days=2)

    # 2. Clean the string for specific date mentions
    clean_text = text.replace("[", "").replace("]", "")
    
    noise_words = [
        "registration is open and",
        "late registration deadline", 
        "early bird deadline", 
        "deadline", 
        "until"
    ]
    
    for word in noise_words:
        clean_text = clean_text.lower().replace(word, "").strip()

    if ":" in clean_text:
        clean_text = clean_text.split(":")[-1].strip()

    # 3. Convert to Datetime
    return pd.to_datetime(clean_text, dayfirst=True, errors='coerce')

def scrape_estro_courses():
    url = "https://www.estro.org/Courses"
    all_data = []

    with sync_playwright() as p:
        print(f"--- Starting ESTRO Courses Scraper ---")
        browser = p.chromium.launch(channel="msedge", headless=False) 
        page = browser.new_page()
        
        print(f"Connecting to: {url}")
        page.goto(url, wait_until="networkidle", timeout=60000)

        try:
            page.wait_for_selector(".text-block", timeout=15000)
            print("✅ Found courses, processing...")
        except:
            print("❌ Error: Could not find course blocks.")
            browser.close()
            return []

        # Scroll to load all dynamic content
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(2000)

        blocks = page.query_selector_all(".text-block")
        print(f"DEBUG: Found {len(blocks)} courses.")

        for block in blocks:
            # --- NAME & URL ---
            title_link = block.query_selector("h2.title a")
            if not title_link:
                continue
                
            name = title_link.inner_text().strip()
            raw_href = title_link.get_attribute("href") or ""
            full_url = raw_href if raw_href.startswith("http") else f"https://www.estro.org{raw_href}"
            
            # --- DATE PROCESSING ---
            date_el = block.query_selector("time")
            date_text = date_el.inner_text().strip() if date_el else ""
            
            start_date = None
            end_date = None

            if date_text:
                parts = date_text.replace("–", "-").split("-")
                try:
                    start_date = pd.to_datetime(parts[0].strip(), dayfirst=True, errors='coerce')
                    if len(parts) > 1:
                        end_date = pd.to_datetime(parts[1].strip(), dayfirst=True, errors='coerce')
                    else:
                        end_date = start_date
                except:
                    pass

            # --- DEADLINE PROCESSING ---
            summary_items = block.query_selector_all(".summary .item")
            summary_text = " ".join([i.inner_text().strip() for i in summary_items])
            
            # Use the shared cleaning function
            deadline_date = clean_deadline_text(summary_text, start_date)

            # --- LOCATION ---
            loc_el = block.query_selector(".location")
            location_text = loc_el.inner_text().strip() if loc_el else "Online / TBD"

            all_data.append({
                "Event Name": name,
                "Start Date": start_date,
                "End Date": end_date,
                "Deadline Date": deadline_date,
                "Registration Info": summary_text,
                "Original Date Range": date_text,
                "Location": location_text,
                "URL": full_url,
                "Organisation": "ESTRO",
                "Type": "Course",
                "Scraped On": pd.Timestamp.now().strftime('%Y-%m-%d')
            })

        browser.close()
    return all_data

if __name__ == "__main__":
    results = scrape_estro_courses()
    
    if results:
        df = pd.DataFrame(results)
        
        # Cleanup
        df = df.drop_duplicates(subset=['Event Name', 'Start Date'])
        
        # Convert to Date objects for CSV
        date_cols = ["Start Date", "End Date", "Deadline Date"]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col]).dt.date
        
        filename = "ESTRO_courses.csv"
        df.to_csv(filename, index=False, encoding="utf-8")
        
        print("\n" + "="*40)
        print(f"SUCCESS: {len(df)} courses saved to {filename}!")
        print("="*40)
    else:
        print("\n❌ FAILED to extract data.")