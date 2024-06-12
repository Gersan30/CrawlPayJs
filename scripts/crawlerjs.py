import logging
import random
import re
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lista de agentes de usuario para rotación
USER_AGENTS = [
    'ControllerSEO/1.0 (compatible; controllerSEO/1.0; +https://controllerseo.com/)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, como Gecko) Version/14.0.3 Safari/605.1.15'
]

# Lista de proxies para rotación
PROXIES = [
    'http://proxy1.com:8080',
    'http://proxy2.com:8080',
    'http://proxy3.com:8080'
]

class WebCrawler:
    def __init__(self, start_url, max_workers=3, dynamic_content=True):
        self.start_url = start_url
        self.base_domain = urlparse(start_url).netloc
        self.visited = set()
        self.urls_to_visit = deque([start_url])
        self.headers = {'User-Agent': random.choice(USER_AGENTS)}
        self.max_workers = max_workers
        self.dynamic_content = dynamic_content

        if dynamic_content:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument(f"user-agent={self.headers['User-Agent']}")
            options.add_argument("--disable-logging")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--blink-settings=imagesEnabled=false")  # No cargar imágenes
            self.driver = webdriver.Chrome(options=options)
            self.driver.implicitly_wait(10)

    def __del__(self):
        if self.dynamic_content:
            try:
                self.driver.quit()
            except Exception as e:
                logging.error(f"Error closing driver: {e}")

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc) and bool(parsed.scheme)
        except Exception:
            return False

    def is_internal_url(self, url):
        return urlparse(url).netloc == self.base_domain

    def normalize_url(self, url):
        defragmented_url, _ = urldefrag(url)
        return defragmented_url

    def clean_url(self, url):
        url = re.sub(r'[^\x20-\x7E]+', '', url).strip()
        return url

    def is_image_url(self, url):
        return re.search(r'\.(jpg|jpeg|png|gif|bmp|webp)$', url, re.IGNORECASE) is not None

    def fetch_static_content(self, url):
        try:
            response = requests.get(url, headers=self.headers, proxies={"http": random.choice(PROXIES)}, timeout=10)
            if response.status_code == 200:
                return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logging.error(f"Error fetching static content: {e}")
        return None

    def visit_url(self, url):
        try:
            soup = None
            if self.dynamic_content:
                self.driver.get(url)
                WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                time.sleep(5)
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            else:
                soup = self.fetch_static_content(url)
            
            if soup:
                elements = soup.find_all(['a', 'link', 'img'])
                for element in elements:
                    href = None
                    if element.name == 'a' and element.get('href'):
                        href = urljoin(url, element['href'])
                    elif element.name == 'link' and element.get('href'):
                        href = urljoin(url, element['href'])
                    elif element.name == 'img' and element.get('src'):
                        href = urljoin(url, element['src'])

                    if href:
                        href = self.clean_url(href)
                        normalized_href = self.normalize_url(href)
                        if self.is_valid_url(normalized_href) and self.is_internal_url(normalized_href):
                            if normalized_href not in self.visited:
                                self.visited.add(normalized_href)
                                logging.info(f"Found URL: {normalized_href}")
                                with open("urls_encontradas.txt", "a") as file:
                                    file.write(f"{normalized_href}\n")
                                if not self.is_image_url(normalized_href):
                                    self.urls_to_visit.append(href)
        except Exception as e:
            logging.error(f"Error visiting URL: {e}")

    def crawl(self):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            while self.urls_to_visit or futures:
                while self.urls_to_visit and len(futures) < self.max_workers:
                    url = self.urls_to_visit.popleft()
                    futures.append(executor.submit(self.visit_url, url))

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logging.error(f"Error in future: {e}")
                    futures.remove(future)

                self.headers['User-Agent'] = random.choice(USER_AGENTS)
                if self.dynamic_content:
                    self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.headers['User-Agent']})

                time.sleep(random.uniform(1, 3))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python crawler.py <start_url>")
        sys.exit(1)

    start_url = sys.argv[1]
    crawler = WebCrawler(start_url)
    crawler.crawl()
