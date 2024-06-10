import logging
import random
import re
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, urldefrag
import pickle  # Para persistencia del estado

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Colores ANSI
GREEN = '\033[92m'
RESET = '\033[0m'

# Agentes de usuario para rotación
USER_AGENTS = [
    'ControllerSEO/1.0 (compatible; controllerSEO/1.0; +https://controllerseo.com/)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15'
]

class WebCrawler:
    def __init__(self, start_url, max_workers=3, state_file='crawler_state.pkl'):
        self.start_url = start_url
        self.base_domain = urlparse(start_url).netloc
        self.visited = set()
        self.urls_to_visit = deque([start_url])
        self.headers = {'User-Agent': random.choice(USER_AGENTS)}
        self.unique_url_counter = 0
        self.max_workers = max_workers
        self.state_file = state_file

        # Configurar Selenium
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument(f"user-agent={self.headers['User-Agent']}")
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)

        self.load_state()

    def __del__(self):
        self.driver.quit()

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

    def visit_url(self, url):
        try:
            normalized_url = self.normalize_url(url)
            if normalized_url not in self.visited:
                self.unique_url_counter += 1
                self.visited.add(normalized_url)
                print(f"{GREEN}ID: {self.unique_url_counter} - URL: {normalized_url}{RESET}")

                self.driver.get(url)
                WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                time.sleep(2)

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                elements = soup.find_all(['a', 'img', 'link', 'script'])
                for element in elements:
                    href = None
                    if element.name == 'a' and element.get('href'):
                        href = urljoin(url, element['href'])
                    elif element.name == 'img' and element.get('src'):
                        href = urljoin(url, element.get('src'))
                    elif element.name == 'link' and element.get('href'):
                        if element.get('type') == 'application/rss+xml':
                            continue
                        rel = element.get('rel', [])
                        if any(rel_value in ['canonical', 'prev', 'next', 'stylesheet', 'alternate', 'icon'] for rel_value in rel):
                            href = urljoin(url, element['href'])
                        else:
                            continue
                    elif element.name == 'script' and element.get('src'):
                        href = urljoin(url, element.get('src'))

                    if href:
                        href = self.clean_url(href)
                        normalized_href = self.normalize_url(href)
                        if self.is_valid_url(normalized_href) and self.is_internal_url(normalized_href) and normalized_href not in self.visited:
                            self.urls_to_visit.append(href)
        except Exception as e:
            logging.error(f"Error visiting {url}: {e}")

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
                        logging.error(f"Error during crawl: {e}")
                    futures.remove(future)

                # Rotar agente de usuario para cada nuevo lote de URLs
                self.headers['User-Agent'] = random.choice(USER_AGENTS)
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.headers['User-Agent']})

                # Política de retardo avanzada
                time.sleep(random.uniform(1, 3))  # Retardo aleatorio entre 1 y 3 segundos

            logging.info("Crawling completado. URLs encontradas:")
            for visited_url in self.visited:
                logging.info(visited_url)

            # Guardar las URLs únicas en un fichero
            with open("urls_encontradas.txt", "w") as file:
                for url in self.visited:
                    file.write(url + "\n")

            self.save_state()
            print(f"Todas las URLs únicas se han guardado en urls_encontradas.txt")

    def save_state(self):
        state = {
            'visited': self.visited,
            'urls_to_visit': list(self.urls_to_visit),
            'unique_url_counter': self.unique_url_counter
        }
        with open(self.state_file, 'wb') as f:
            pickle.dump(state, f)
        logging.info("Estado guardado.")

    def load_state(self):
        try:
            with open(self.state_file, 'rb') as f:
                state = pickle.load(f)
                self.visited = state.get('visited', set())
                self.urls_to_visit = deque(state.get('urls_to_visit', []))
                self.unique_url_counter = state.get('unique_url_counter', 0)
            logging.info("Estado cargado.")
        except FileNotFoundError:
            logging.info("No se encontró un estado previo, iniciando nuevo rastreo.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python crawler.py <start_url>")
        sys.exit(1)

    start_url = sys.argv[1]
    crawler = WebCrawler(start_url)
    crawler.crawl()

