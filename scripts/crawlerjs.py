import logging
import random
import re
import sys
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, urldefrag

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Desactivar logging para mantener la salida de consola limpia
logging.basicConfig(level=logging.CRITICAL)

# Lista de agentes de usuario para rotación
USER_AGENTS = [
    'ControllerSEO/1.0 (compatible; controllerSEO/1.0; +https://controllerseo.com/)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15'
]

class WebCrawler:
    def __init__(self, start_url, max_workers=3):
        self.start_url = start_url
        self.base_domain = urlparse(start_url).netloc
        self.visited = set()  # Conjunto de URLs visitadas
        self.urls_to_visit = deque([start_url])  # Cola de URLs por visitar
        self.headers = {'User-Agent': random.choice(USER_AGENTS)}  # Elegir un agente de usuario al azar
        self.max_workers = max_workers  # Número máximo de trabajadores

        # Configurar Selenium
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument(f"user-agent={self.headers['User-Agent']}")
        options.add_argument("--disable-logging")
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)

    def __del__(self):
        self.driver.quit()  # Asegurarse de cerrar el navegador al finalizar

    def is_valid_url(self, url):
        # Validar si la URL es válida
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc) and bool(parsed.scheme)
        except Exception:
            return False

    def is_internal_url(self, url):
        # Comprobar si la URL es interna (del mismo dominio)
        return urlparse(url).netloc == self.base_domain or url.startswith('/')

    def normalize_url(self, url):
        # Normalizar la URL eliminando fragmentos
        defragmented_url, _ = urldefrag(url)
        return defragmented_url

    def clean_url(self, url):
        # Limpiar la URL eliminando caracteres no imprimibles y espacios en blanco
        url = re.sub(r'[^\x20-\x7E]+', '', url).strip()
        return url

    def visit_url(self, url):
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

            # Esperar a que todo el contenido dinámico se cargue
            time.sleep(5)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Extraer URLs de los elementos <a>, <img>, <link>
            elements = soup.find_all(['a', 'img', 'link'])
            for element in elements:
                href = None
                if element.name == 'a' and element.get('href'):
                    href = urljoin(url, element['href'])
                elif element.name == 'img' and element.get('src'):
                    href = urljoin(url, element.get('src'))
                elif element.name == 'link' and element.get('href'):
                    if element.get('type') == 'application/rss+xml':
                        continue  # Excluir enlaces de tipo "application/rss+xml"
                    rel = element.get('rel', [])
                    if any(rel_value in ['canonical', 'prev', 'next', 'stylesheet', 'alternate', 'icon'] for rel_value in rel):
                        href = urljoin(url, element['href'])
                    else:
                        continue
                else:
                    continue

                href = self.clean_url(href)
                normalized_href = self.normalize_url(href)
                if self.is_valid_url(normalized_href) and self.is_internal_url(normalized_href) and normalized_href not in self.visited:
                    self.visited.add(normalized_href)
                    print(normalized_href)
                    with open("urls_encontradas.txt", "a") as file:
                        file.write(f"{normalized_href}\n")
                    self.urls_to_visit.append(href)
        except Exception as e:
            pass  # Ignorar errores para mantener la salida limpia

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
                        pass  # Ignorar errores para mantener la salida limpia
                    futures.remove(future)

                # Rotar agente de usuario para cada nuevo lote de URLs
                self.headers['User-Agent'] = random.choice(USER_AGENTS)
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.headers['User-Agent']})

                # Política de retardo avanzada
                time.sleep(random.uniform(1, 3))  # Retardo aleatorio entre 1 y 3 segundos

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python crawler.py <start_url>")
        sys.exit(1)

    start_url = sys.argv[1]
    crawler = WebCrawler(start_url)
    crawler.crawl()
