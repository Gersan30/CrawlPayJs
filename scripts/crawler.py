import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
import time
import sys
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
import re  # Importar el módulo re para expresiones regulares

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Colores ANSI
GREEN = '\033[92m'
RESET = '\033[0m'

# Agentes de usuario para rotación
USER_AGENTS = [
    'ControllerSEO/1.0 (compatible; controllerSEO/1.0; +https://controllerseo.com/)'
]

class WebCrawler:
    def __init__(self, start_url, max_workers=5):
        self.start_url = start_url
        self.base_domain = urlparse(start_url).netloc
        self.visited = set()
        self.urls_to_visit = deque([start_url])
        self.headers = {'User-Agent': random.choice(USER_AGENTS)}
        self.unique_url_counter = 0  # Contador para el ID incremental de URLs únicas
        self.max_workers = max_workers

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc) and bool(parsed.scheme)
        except Exception:
            return False

    def is_internal_url(self, url):
        return urlparse(url).netloc == self.base_domain

    def normalize_url(self, url):
        # Ignorar el fragmento de la URL (parte después de #)
        defragmented_url, _ = urldefrag(url)
        return defragmented_url

    def clean_url(self, url):
        # Eliminar caracteres no imprimibles y espacios en blanco
        url = re.sub(r'[^\x20-\x7E]+', '', url).strip()
        return url

    def visit_url(self, session, url):
        normalized_url = self.normalize_url(url)
        if normalized_url not in self.visited:
            self.unique_url_counter += 1
            #logging.info(f"{self.unique_url_counter}: Visitando URL: {normalized_url}")
            self.visited.add(normalized_url)
            print(f"{GREEN}ID: {self.unique_url_counter} - URL: {normalized_url}{RESET}")

            for _ in range(3):  # Intentar 3 veces
                try:
                    response = session.get(url, headers=self.headers)
                    response.raise_for_status()
                    break  # Salir del loop si la solicitud fue exitosa
                except requests.RequestException as e:
                    #logging.error(f"Falla al visitar {url}: {e}")
                    time.sleep(1)  # Esperar 1 segundo antes de reintentar
            else:
                return  # Si falla después de 3 intentos, salir de la función

            content_type = response.headers.get('Content-Type', '')
            if 'xml' in content_type:
                parser = 'xml'
            else:
                parser = 'html.parser'

            soup = BeautifulSoup(response.text, parser)  # Usar el parser adecuado

            # Extraer URLs de diferentes elementos
            elements = soup.find_all(['a', 'img', 'link'])
            for element in elements:
                if element.name == 'a' and element.get('href'):
                    href = urljoin(url, element['href'])
                elif element.name == 'img' and element.get('src'):
                    href = urljoin(url, element['src'])
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
                    self.urls_to_visit.append(href)

    def crawl(self):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            with requests.Session() as session:
                futures = []
                while self.urls_to_visit or futures:
                    while self.urls_to_visit and len(futures) < self.max_workers:
                        url = self.urls_to_visit.popleft()
                        futures.append(executor.submit(self.visit_url, session, url))

                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            logging.error(f"Error during crawl: {e}")
                        futures.remove(future)

        logging.info("Crawling completado. URLs encontradas:")
        for visited_url in self.visited:
            logging.info(visited_url)

        # Guardar las URLs únicas en un fichero
        with open("urls_encontradas.txt", "w") as file:
            for url in self.visited:
                file.write(url + "\n")

        print(f"Todas las URLs únicas se han guardado en urls_encontradas.txt")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python crawler.py <start_url>")
        sys.exit(1)

    start_url = sys.argv[1]
    crawler = WebCrawler(start_url)
    crawler.crawl()
