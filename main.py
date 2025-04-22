import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import pathlib
import zipfile
import io
import datetime
from datetime import timedelta

class GujaratSamacharScraper:
    def __init__(self):
        self.BASE = "https://epaper.gujaratsamachar.com"
        self.EDITION = "ahmedabad"
        self.HEADERS = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }

    def page_url(self, date, pg):
        return f"{self.BASE}/view_article/{self.EDITION}/{date}/{pg}"

    def article_url(self, date, pg, artid):
        return f"{self.BASE}/view_article/{self.EDITION}/{date}/{pg}/{artid}"

    def fetch(self, url, sess):
        r = sess.get(url, allow_redirects=True, timeout=10)
        r.raise_for_status()
        return r

    def first_article_id(self, date, page, sess):
        r = self.fetch(self.page_url(date, page), sess)
        m = re.search(r"/(\d+)$", r.url)
        if not m:
            raise RuntimeError("Cannot determine first article id")
        return int(m.group(1)), r.text

    def parse_images(self, html_text):
        soup = BeautifulSoup(html_text, "lxml")
        for imgtag in soup.select("img"):
            src = imgtag.get("src") or ""
            if src.lower().endswith((".jpg", ".jpeg", ".png")):
                yield src if src.startswith("http") else self.BASE + src

    def scrape_page(self, date, pg, sess, progress_bar=None):
        images = []
        try:
            artid, html_text = self.first_article_id(date, pg, sess)
            consecutive_misses = 0
            while consecutive_misses < 100:
                url = self.article_url(date, pg, artid)
                try:
                    r = self.fetch(url, sess)
                    consecutive_misses = 0
                    for imurl in self.parse_images(r.text):
                        # Download image
                        img_response = self.fetch(imurl, sess)
                        if img_response.status_code == 200:
                            # Create filename with convention: date_pagenumber_articlenumber.jpeg
                            filename = f"{date}_{pg}_{artid}.jpeg"
                            images.append((filename, img_response.content))
                            if progress_bar:
                                progress_bar.progress((artid % 100) / 100)
                except requests.HTTPError as e:
                    if e.response.status_code == 404:
                        consecutive_misses += 1
                    else:
                        raise
                artid += 1
                time.sleep(0.6)
        except Exception as e:
            st.error(f"Error scraping page {pg}: {str(e)}")

        return images

    def create_zip(self, images):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for filename, content in images:
                zip_file.writestr(filename, content)
        return zip_buffer

def main():
    st.title("Gujarat Samachar E-Paper Scraper")

    # Date selector
    min_date = datetime.date.today() - timedelta(days=30)  # Allow selecting up to 30 days back
    max_date = datetime.date.today()
    selected_date = st.date_input(
        "Select Date",
        value=datetime.date.today(),
        min_value=min_date,
        max_value=max_date
    )

    if st.button("Download Images"):
        formatted_date = selected_date.strftime("%d-%m-%Y")

        scraper = GujaratSamacharScraper()
        all_images = []

        with st.spinner("Scraping images... This may take a few minutes."):
            progress_bar = st.progress(0)

            with requests.Session() as sess:
                sess.headers.update(scraper.HEADERS)
                page = 1
                while page <= 30:  # Limit to 30 pages for safety
                    try:
                        st.write(f"Scanning page {page}...")
                        images = scraper.scrape_page(formatted_date, page, sess, progress_bar)
                        if not images:  # If no images found, assume we've reached the end
                            break
                        all_images.extend(images)
                        page += 1
                    except Exception as e:
                        st.error(f"Error on page {page}: {str(e)}")
                        break

        if all_images:
            # Create zip file
            zip_buffer = scraper.create_zip(all_images)

            # Offer download
            st.download_button(
                label="Download ZIP file",
                data=zip_buffer.getvalue(),
                file_name=f"gujarat_samachar_{formatted_date}.zip",
                mime="application/zip"
            )

            st.success(f"Successfully scraped {len(all_images)} images!")
        else:
            st.warning("No images found for the selected date.")

if __name__ == "__main__":
    main()
