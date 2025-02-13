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
from readability import Document
import threading


chrome_options = Options()
chrome_options.add_argument("--headless=new") # for Chrome >= 109

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
            parsed_html=(r.content)
    else:
        
        parsed_html=cache

    doc = Document(parsed_html)
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
        if s.name == 'p' or s.name=='ol' or s.name=='ul':
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
            print("Unknow element")
            print(s.name)
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


def get_content(url_list,dataset,top_result=2):
    out=""
    #top_result=1
    #print(url_list)
    url_list=url_list[:top_result]

    #print(url_list)
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

    for (data,skip) in dataset:
        #print("data: "+data)
        #print("skip: "+str(skip))

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
                    out=out+"\n\n"
            if not skip:
                out=out+ str(data)  +"\n\n"
        else:
             out=out+ str(data)  +"\n\n"
    #print(out)
    return out

def search(query,top_result=2):
    query=query.lower()
    dataset_conf=[]
    #print(query)
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
        #print("northbound searching sequence - "+conf_ph)
        #print("conf_ph:"+ conf_ph)
        get_conf_context(conf_ph,cache,dataset_conf,"bypass")
    #print("dataset_conf: "+str(dataset_conf))
    url_list=get_url(query)
    content=get_content(url_list,dataset_conf,top_result)
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
