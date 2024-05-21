import io
import pycurl
import time
import base64 as b64
import stem.process
import os
import re
import logging
from stem.util import term
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup

# Configuração do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SOCKS_PORT = 9052
tor_process = None  # Definindo a variável tor_process no escopo global

def query(url):
    """Função para realizar uma consulta HTTP via Tor."""
    output = io.BytesIO()
    query = pycurl.Curl()
    query.setopt(pycurl.URL, url)
    query.setopt(pycurl.PROXY, 'localhost')
    query.setopt(pycurl.PROXYPORT, SOCKS_PORT)
    query.setopt(pycurl.PROXYTYPE, pycurl.PROXYTYPE_SOCKS5_HOSTNAME)
    query.setopt(pycurl.WRITEFUNCTION, output.write)

    try:
        query.perform()
        return output.getvalue()
    except pycurl.error as exc:
        return "Unable to reach %s (%s)" % (url, exc)

def print_bootstrap_lines(line):
    """Função para imprimir as linhas de bootstrap do Tor."""
    if "Bootstrapped " in line:
        logging.info(term.format(line, term.Color.BLUE))

def start_tor():
    """Função para iniciar o Tor."""
    global tor_process
    logging.info(term.format("Starting Tor:\n", term.Attr.BOLD))

    tor_process = stem.process.launch_tor_with_config(
        config={
            'SocksPort': str(SOCKS_PORT),
            'ExitNodes': '{ru}',  # Configurando para usar apenas nós de saída na Rússia
        },
        init_msg_handler=print_bootstrap_lines,
    )

    logging.info(term.format("\nChecking our endpoint:\n", term.Attr.BOLD))
    logging.info(term.format(query("https://api.myip.com"), term.Color.BLUE))

def setup_webdriver():
    """Função para configurar o WebDriver do Selenium para usar o proxy Tor."""
    logging.info(term.format("Initializing WebDriver with Tor proxy...\n", term.Attr.BOLD))
    
    options = Options()
    PROXY_HOST = "127.0.0.1"
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.socks", PROXY_HOST)
    options.set_preference("network.proxy.socks_port", int(SOCKS_PORT))
    options.set_preference('network.proxy.socks_remote_dns', True)

    driver = webdriver.Firefox(options=options)
    return driver

def access_mainpage(driver, url):
    """Função para acessar a página inicial usando o Selenium."""
    logging.info(term.format("Visiting an onion website using Selenium with Tor proxy...\n", term.Attr.BOLD))
    driver.get(url)

def submit_search(driver):
    """Função para submeter uma busca no fórum."""
    keywords_input = driver.find_element(By.NAME, "keywords")
    keywords_input.send_keys("hack")
    submit_button = driver.find_element(By.NAME, "submit")
    submit_button.click()

def check_block_error(driver):
    """Função para verificar se houve erro de bloqueio."""
    page_source = driver.page_source
    if re.search("Sorry, but you can only perform one search every", page_source): 
        return True
    return False

def getting_subjects(driver):
    """Função para extrair tópicos, usuários e links da página."""
    topicos = []
    usuarios = []
    links = []

    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')

    for top in soup.find_all("a", class_="subject_old"):
        topicos.append(top.text.strip())

    for aut in soup.find_all("div", class_="author smalltext"):
        autor = aut.find('a')
        if autor:  # Verifica se autor não é None
            usuarios.append(autor.text.strip())

    for link in soup.find_all("a", class_="subject_old"):
        links.append("http://suprbaydvdcaynfo4dgdzgxb4zuso7rftlil5yg5kqjefnw4wq4ulcad.onion/" + link['href'])

    return topicos, usuarios, links

def acessando_links(driver, links, tps, usr):
    """Função para acessar cada link, extrair e salvar o conteúdo."""
    output_folder = "output"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    subjects = []

    for index, link in enumerate(links):
        logging.info(f"Acessando o link {index + 1} de {len(links)}: {link}")
        driver.get(link)
        time.sleep(2)

        subject = {
            'url': link,
            'title': tps[index],
            'author': usr[index],
            'page_source': '',
            'screenshot_base64': '',
            'posts': []
        }

        while True:
            page_source = driver.page_source
            subject['page_source'] = page_source
            subject['screenshot_base64'] = b64.b64encode(page_source.encode("utf-8")).decode("utf-8")
        
            soup = BeautifulSoup(page_source, 'html.parser')
            conteudo = [cont.text.strip() for cont in soup.find_all('div', class_='post_body scaleimages')]
            usuarios = [user.text.strip() for user in soup.find_all('div', class_='author_information')]
            datas = [dat.text.strip() for dat in soup.find_all('span', class_='post_date')]

            for idx, content in enumerate(conteudo):
                cont = {
                    'usuario': usuarios[idx] if idx < len(usuarios) else '',
                    'data': datas[idx] if idx < len(datas) else '',
                    'conteudo': content
                }
                subject['posts'].append(cont)

            try:
                next_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[@class='pagination_next']")))
                next_button.click()
            except Exception as e:
                logging.warning("Não foi possível encontrar a próxima página")
                break  # Sair do loop se não houver mais botão "Next"

        subjects.append(subject)

    return subjects

if __name__ == "__main__":
    start_tor()
    driver = setup_webdriver()

    # Acessando a página inicial
    access_mainpage(driver, "http://suprbaydvdcaynfo4dgdzgxb4zuso7rftlil5yg5kqjefnw4wq4ulcad.onion")
    submit_search(driver)
    if check_block_error(driver):
        time.sleep(50)
        submit_search(driver)

    i = 1
    topicos = []
    usuarios = []
    links = []

    while True:
        logging.info(f'Pegando os tópicos, usuários e links da página {i}')
        _topicos, _usuarios, _links = getting_subjects(driver)
        topicos += _topicos
        usuarios += _usuarios
        links += _links

        try:
            next_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[@class='pagination_next']")))
            next_button.click()
        except:
            logging.warning("Não foi possível encontrar a próxima página")
            break  # Sair do loop se não houver mais botão "Next"

        i += 1

    subs = acessando_links(driver, links, topicos, usuarios)
    logging.info(subs)

    # Fechar o navegador
    driver.quit()

    # Parar o processo do Tor
    tor_process.kill()
