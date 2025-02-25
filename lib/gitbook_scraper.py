try: 
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup
import requests
#from requests_html import HTMLSession
from selenium import webdriver
import time
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import re
from readability import Document as R_Document
import threading
import json
import logging
from .langchain_loader import *
import traceback


chrome_options = Options()
chrome_options.add_argument("--headless=new") # for Chrome >= 109


handler = logging.FileHandler("logs/gitbook_scraper.log")  
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('gitbook_scraper')
logger.setLevel(logging.INFO)
logger.addHandler(handler)


def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data

config=load_config()


def get_html(query):
    #print(query)
    query_str=query.replace(" ", "+")
    url="https://cisco-tailf.gitbook.io/nso-docs/guides?q="+query_str+"&global=true"
    #print(url)""
    service = Service(executable_path='/usr/lib/chromium-browser/chromedriver')
    try:
        driver = webdriver.Chrome(service=service,options=chrome_options)
    except:
         driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(3)
    driver.implicitly_wait(30)
    #p_element = driver.find_element_by_id(id_='intro-text')

    #session = HTMLSession()
    #r = session.get(url)
    #r.html.render()
    return driver.page_source
    #if r.status_code >=200 and r.status_code <300:
    #    print(r.html)
    #    return r.html
    #else: 
    #    raise requests.exceptions.HTTPError


def get_url(query):
    html = get_html(query) 
    #print(html)
    parsed_html = BeautifulSoup(html, "html.parser")
    search_result=parsed_html.find('div', attrs={'data-testid':"search-results"})
    url_list=[]
    m_list=[]
    for a in search_result.find_all('a', href=True):
        if "https" in a['href']:
            if "#" in a['href'] and "?q=" not in a['href']:
                url_hash=a['href']
                m_elem=url_hash.split("#")[0]
                url_list.append((url_hash,"#"))
                if (m_elem,"m") in url_list:
                    url_list.remove((m_elem,"m"))
            else:
                url_m=a['href']
                m_list.append(url_m)
                url_list.append((url_m,"m"))
    #print(url_list)
    return url_list



def parse_content(url,mode,dataset,query=None,cache=None,first=True):
    #print("url: "+url)
    parsed_html=None
    if not cache:
        r=requests.get(url)
        #print()
        if r.status_code <200 and r.status_code >300:
            raise requests.exceptions.HTTPError
        else:
            parsed_html=r.content
    else:
        parsed_html=cache
    #print(parsed_html)
    doc = R_Document(parsed_html)
    summary=doc.summary()

    soup = BeautifulSoup(summary, features="html.parser")


    search_result=None
    if mode == "#":
        lvl=2
        target_lvl=5
        while (not search_result) and lvl < target_lvl:
            search_result=soup.find('h'+str(lvl), id=url.split("#")[1])
            lvl+=1
        if lvl >=5:
            text=""
        else:
            text=iterate_html(search_result,lvl-1,"",search_query=query)
    else:
        search_result=soup.find('p')
        intro_first=search_result.get_text()
        text=iterate_html(search_result,2,"",search_query=query)
        text=intro_first+text

    if first:
        text="source: "+url+"\nresult: "+text
    else:
        text=text 
    
    if first== "bypass":
        dataset.append((text,None))
    elif "section5" in url:
        dataset.append((text,True))
    else:
        dataset.append((text,False))
    return dataset

def iterate_html(search_result,lvl,text,search_query=None):
    #print("h"+str(lvl))
    i=0
    all_cont=search_result.find_next_siblings()
    for s in all_cont: 
        content=""
        #print(s.name)
        if s.name == 'p' or s.name=='ol' or s.name=='ul' or s.name=='summary':
            #print("p")
            #print(s.get_text())
            if s.name=='ul':
                for sub in s.find_all('li', recursive=False):
                    content=sub.get_text()
                    text=text+content+"\n"
            else:
                content=s.get_text()
                text=text+content+"\n" 
        elif  s.name == 'h'+str(lvl+1):
            #print('h'+str(lvl+1))
            content=s.get_text()
            text=text+content+"\n" 
            text=iterate_html(s,lvl+1,text,search_query=search_query)
        elif  s.name == 'div' :
            #print("div" + str(s))
            content=s.get_text()
            text=text+content +"\n"
            #text=iterate_html(s,lvl,text)
        elif s.name == 'blockquote':
            content=s.find('p').text
            text=text+content +"\n"
        elif s.name == 'h'+str(lvl) or s.name == 'h'+str(lvl-1):
            #print("RETURN")
            break
        else:
            logger.error("Unknow element")
            logger.error(s.name)
            break
        if search_query:
            if " " in search_query:
                key_lst=search_query.split(" ")
                #print(key_lst)
                con_result=""
                for key in key_lst:
                    if len(key) >1:
                        #print("key: "+key)
                        result=query_search(key,content,all_cont,i)
                        if result:
                            con_result=con_result+result
                if len(con_result) > 0:
                    return con_result
            else:
                result=query_search(search_query,content,all_cont,i)
                if result:
                    return result
        i+=1
    return text

def query_search(search_query,content,all_cont,i):
    if search_query in content:
        next_conent=all_cont[i+1].get_text()
        result=content+"\n"+next_conent +"\n"
        return result
    else:
        return None

def del_skip(dataset):
    for (_data,skip) in dataset:
        if skip:
            dataset.remove((_data,skip))
    return dataset


def get_content(url_list_org,dataset,top_result=2):
    out=""
    #top_result=1
    for (url,mode) in url_list_org:
        if "http://" not in url and "https://" not in url:
            logger.info("removing "+str(url))
            url_list_org.remove((url,mode))
    url_list=url_list_org[:top_result]

    thread_pool=[]
    #print(url_list)
    for (url,mode) in url_list:
        t=threading.Thread(target=parse_content, args=(url,mode,dataset,))
        thread_pool.append(t)
        #parse_content(url,dataset)
    for t in thread_pool:
        t.start()
    for t in thread_pool:
        t.join()
        #print("t.join()")
    cache=None
    #print(dataset)
    for (data,skip) in dataset:
        #print((data,skip))
        if skip != None:
            if ("ncs.conf" or "ncs-config" in data)  and not skip:
                #print(data)
                if not cache:
                    r=requests.get("https://cisco-tailf.gitbook.io/nso-docs/guides/resources/index/section5#ncs.conf")
                    if r.status_code <200 and r.status_code >300:
                        raise requests.exceptions.HTTPError
                    else:
                        cache=r.content

                res=re.findall(r'\b(ncs\-config)(/[a-z,A-Z,\-]+)+\b',data)
                if res:
                    dataset_conf=[]
                    counter=0
                    for _k,leaf in res:  
                        #print(leaf)
                        if counter >0:
                            first=False
                        else:
                            first=True
                        #print("Looking for ncs.conf content")
                        get_conf_context(leaf,cache,dataset_conf,first)
                        #print(config_text)
                        if leaf !="/api":
                            counter+=1
                    for (data_conf,_skip) in dataset_conf:
                        out=out+ str(data_conf)
                        #print(leaf)
                    #print(data)
                    out=out+"\n\n"

            if not skip:
                out=out+ str(data)  +"\n\n"
                #print((data,skip))
        else:
             out=out+ str(data)  +"\n\n"
    #print(out)
    return out


def gitbook_query(query,top_result,url_override=[]):
    dataset_conf=[]
    if "upgrade" in query and "nso" not in query:
            query="nso "+query
    elif ("northbound" in query or "ncs.conf" in  query):
        r=requests.get("https://cisco-tailf.gitbook.io/nso-docs/guides/resources/index/section5#ncs.conf")
        if r.status_code <200 and r.status_code >300:
            raise requests.exceptions.HTTPError
        else:
            cache=r.content  
        conf_ph=query.replace("northbound","")   
        conf_ph=conf_ph.replace("ncs.conf","")   
        conf_ph=conf_ph.replace("config","")  
        conf_ph=conf_ph.replace("configuration","")
        conf_ph=conf_ph.replace("set","")
        conf_ph=conf_ph.replace("\"","")
        get_conf_context(conf_ph,cache,dataset_conf,"bypass")
    if len(url_override)>0:
        url_list=url_override
        top_result
    else:
        url_list=get_url(query)
    if len(url_list) == 0:
        raise Exception("No result return from the Gitbook")
    backup_url=url_list.copy()
    content=get_content(url_list,dataset_conf,top_result)

    while len(content)==0 and len(backup_url) > 0 and len(url_list) > 0:
        logger.info("content empty in get_content for urls - "+str(backup_url)+". Try the next round of URL")
        url_list=backup_url[top_result:]
        content=get_content(url_list,dataset_conf,top_result,query=query)
    return content

def query_filter(query):
    if "site:" in query:
        out=""
        data_lst=query.split(" ")
        for data in data_lst:
            if  "site:" not in data:
                out=out+data
    else:
        out=query
    return out

def search(query,top_result=2,q=None):
    query=query.lower()
    top_result_i=top_result//2

    if top_result_i*2 != top_result:
        top_result_rag=top_result_i+1
        top_result_gitbook=top_result_i
    else:
        top_result_gitbook=top_result_i
        top_result_rag=top_result_i
    query=query_filter(query)
    content=""
    if config["get_content_type"] == "gitbook_search":
        content=gitbook_query(query,top_result)
    elif config["get_content_type"] == "langchain_rag":
        if q:
            input_data=q
        else:
            input_data=query
        content=query_vdb(input_data,top_result=top_result+1)
    elif config["get_content_type"] == "hybrid":
        try:
            content=gitbook_query(query,top_result=top_result_gitbook)
            logger.info("gitbook_query Get Content - SUCCESS")
        except:
            logger.info("gitbook_query Get Content - FAILED")
            logger.info("Fallback to Langchain")
            logger.error(traceback.format_exc())
            top_result_rag=top_result+1
        #print(content)
        if q:
            input_data=q
        else:
            input_data=query
        content=content+query_vdb(input_data,top_result=top_result_rag)
        #print(content)
        logger.info("query_vdb Get Content - SUCCESS")
    else:
        logger.error("Wrong get_content_type")
    #print("dataset_conf after: "+str(dataset_conf))
    #print("content after: "+str(content))
    return content
    
def get_conf_context(query,cache,dataset_conf,first,iterate_search=""):
    if query !="/api":
        #print(first)
        #print("Search for: "+query)
        parse_content("https://cisco-tailf.gitbook.io/nso-docs/guides/resources/index/section5#ncs.conf","#",dataset_conf,query=query,cache=cache,first=first)
        return dataset_conf   
    else:
        return ""
    

if __name__=="__main__":
    dataset_conf=[]
    query="CDB"
    cache=None
    first= True
    get_conf_context("absolute-timeout",cache,dataset_conf,True)
    print(dataset_conf)
