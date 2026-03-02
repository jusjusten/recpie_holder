from bs4 import BeautifulSoup
import requests

url = input("Enter a url with a recipe: ")
#print(url)

page = requests.get(url)
soup = BeautifulSoup(page.text, 'html')

print(soup)
soup.find_all('div')

#<div class="mv-create-ingredients">
