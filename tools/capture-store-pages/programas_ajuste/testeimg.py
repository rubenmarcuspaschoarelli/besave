from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import os
import requests
import re


# Função para baixar as imagens
def download_image(img_url, filename):
    try:
        img_data = requests.get(img_url, timeout=30).content
        with open(filename, 'wb') as file:
            file.write(img_data)
        print(f"Imagem salva: {filename}")
    except Exception as e:
        print(f"Erro ao salvar a imagem {filename}: {e}")


def get_amazon_images(page, folder_path):
    # Cria o diretório para salvar as imagens
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    thumbs = page.locator('#altImages ul').locator('li')

    img_counter = 0
    for index in range(thumbs.count()):
        thumb = thumbs.nth(index)
        try:
            button = thumb.locator('input').first
            button.click()

            try:
                # ":visible" ignora o <ul> template oculto (main-image-container
                # tem 2 <ul>: um template escondido e o visivel com as imagens)
                container = page.locator('#main-image-container > ul:visible').first
                container.wait_for(state='visible', timeout=20000)

                images = container.locator('img')
                for j in range(images.count()):
                    img_url = images.nth(j).get_attribute('src')
                    if not img_url:
                        continue
                    clean_url = img_url.split('?')[0]
                    img_extension = clean_url.split('.')[-1]
                    img_counter += 1
                    filename = os.path.join(folder_path, f"img_{img_counter}.{img_extension}")
                    download_image(img_url, filename)

            except PlaywrightTimeoutError:
                print('nao encontrou a imagem')

        except Exception:
            print('nao encontrou o botao')


folder_path = "amazon_1234"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-gpu", "--no-sandbox"],
    )
    page = browser.new_page()
    page.set_default_timeout(15000)

    # Acessando a Amazon
    page.goto("https://www.amazon.com.br/dp/B07DYXRVLK?psc=1&ref=ppx_yo2ov_dt_b_product_details")

    get_amazon_images(page, folder_path)

    browser.close()
