from bs4 import BeautifulSoup 
import requests
from selenium import webdriver
import time
from selenium.webdriver.chrome.options import Options
import threading
#def api_search(url):
from readability import Document
import os
import re



chrome_options = Options()
chrome_options.add_argument("--headless=new") # for Chrome >= 109

def get_html():
    #print(query)
    url="https://developer.cisco.com/docs/nso/api/ncs"
    #print(url)
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(3)
    driver.implicitly_wait(30)

    return driver.page_source

def get_html_java(url):
    #print(query)
    #url="http://66.218.245.39/doc/api/java/com/tailf/"
    r=requests.get(url)
    return r.content

def get_content(url_list,lang):
    out=""
    #top_result=1
    #print(url_list)
    dataset=[]
    thread_pool=[]
    for url in url_list:
        if lang == "python":
            t=threading.Thread(target=parse_content_py, args=(url,dataset,))
        elif lang == "java":
            t=threading.Thread(target=parse_content_java, args=(url,dataset,))
        else:
            raise Exception("Wrong Programming Language")

        thread_pool.append(t)
        #parse_content(url,dataset)
    for t in thread_pool:
        t.start()
    for t in thread_pool:
        t.join()

    for data in dataset:
        out=out+ str(data) +"\n\n"
    #print(out)
    return out


def parse_content_py(url,dataset):
    #print(url)
    r=requests.get(url)
    if r.status_code <200 and r.status_code >300:
        raise requests.exceptions.HTTPError

    doc = Document(r.content)
    summary=doc.summary()
    #print(summary)
    soup = BeautifulSoup(summary, features="html.parser")
    text = os.linesep.join([s for s in soup.get_text().splitlines() if s])
    text=text.replace("def ","\r\ndef ")
    text=text.replace("class ","\r\nclass ")
    text=text.replace("var ","\r\nvar ")
    dataset.append(text)
    return dataset



def parse_content_java(url,dataset):
    #print(url)
    
    r=requests.get(url)
    if r.status_code <200 and r.status_code >300:
        raise requests.exceptions.HTTPError


    soup = BeautifulSoup(r.content, features="html.parser")
    text = os.linesep.join([s for s in soup.get_text().splitlines() if s])
    data=""
    for content in re.split("Method", text)[2:]:
        data=data+"\n"+content

    data=f'''
###################################
Source: {url}
{re.split("Overview", data)[0]}
###################################

    
    '''
    print(data)
    dataset.append(data)

    return dataset

def gen_parser_py():
    response = get_html()
    soup = BeautifulSoup(response, 'html.parser')
    links = soup.find_all('a', href=True)
    nso_api_links = [link['href'] for link in links if link['href'].startswith('/docs/nso/api/')]
    return nso_api_links


def gen_parser_java(url,keyword,slice):
    response = get_html_java(url)
    soup = BeautifulSoup(response, 'html.parser')
    links = soup.find_all('a', href=True)
    nso_api_links = [link['href'] for link in links if keyword in link['href']]
    #print(nso_api_links)
    out=None
    if slice == 0:
        out=nso_api_links
    else:
        out=nso_api_links[slice:]
    return out

def py_api():
    link_list=gen_parser_py()
    py_list=[]
    for link in  link_list:
        if "/docs/nso/api/ncs-" in link and "man" not in link and "childlist" not in link and "ncs-error" not in link and "ncs-events" not in link and "ncs-ha" not in link and "ncs-keypath" not in link and "ncs-ns" not in link and "ncs-tm" not in link:
            py_list.append("https://developer.cisco.com"+link)
    py_list=set(py_list)
    data=get_content(py_list,"python")

    #print(dataset)

            #print("https://developer.cisco.com/docs/nso/api"+link)
        #print("https://developer.cisco.com/docs/nso/api/"+link)

    return data

def java_api():
    link_list=gen_parser_java("http://66.218.245.39/doc/api/java/com/tailf/","/",1)
    java_list=[]
    java_list_l=[]

    for link in  link_list:
        java_list.append("http://66.218.245.39/doc/api/java/com/tailf/"+link)
        #print("http://66.218.245.39/doc/api/java/com/tailf/"+link)
    java_list=set(java_list)
    for url in java_list:
        java_list_sec=gen_parser_java(url,".html",0 )
        for url_sec in java_list_sec:
            data_url=url+url_sec
            java_list_l.append(data_url)
    data=get_content(java_list_l,"java")
    return data

def retrive_database(lang):
    if lang.lower() == "python":
        py_api()
    elif lang.lower() == "java":
        java_api()
    else:
        raise Exception("Wrong Programming Language - "+lang.lower())


if __name__=="__main__":
    dataset=[]
    java_api()
    #parse_content_java("http://66.218.245.39/doc/api/java/com/tailf/cdb/Cdb.html",dataset)
    #out=""
    #for data in dataset:
    #    out=out+ str(data) +"\n\n"
    #print(out)
    #parse_content_java("http://66.218.245.39/doc/api/java/com/tailf/cdb/Cdb.html",dataset)
    #print(java_api())
    #api_search("https://developer.cisco.com/docs/nso/api/")