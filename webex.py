import requests
import os
import urllib3
from flask import Flask, request
import sys
from webex_api import *
import logging
from github_feedback import *
from lib.langchain_loader import *
from llama_changelog import changelog_init


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

token = os.getenv('ai_bot_token') # You can get it on https://developer.webex.com/endpoint-messages-post.html
mode = os.getenv('pipline_mode')
app = Flask(__name__)

config=load_config()

if mode == "nso":
    from llama_handler import main,code_gen_cache
elif  mode == "general":
    from ollama_handler import main as ollama_main
else:
    print("ERROR: invalid mode")



handler = logging.FileHandler("logs/webex.log")        
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger('webex')
logger.setLevel(logging.INFO)
logger.addHandler(handler)

@app.route("/api",methods=['POST'])
def api():
    # Get the json data
    auth=str(request.authorization).split(" ")[1]
    if auth not in config["api_token"]:
        return "ACCESS DENINED"
    json = request.json
    print(request.authorization)

    print (request.url, file = sys.stdout)
    id = json["data"]["id"]
    email = json["data"]["personEmail"]
    cec=email.split("@")[0]
    email_previx=email.split("@")[1]
    if (email_previx != "webex.bot") and (email_previx == config["bot_email_prefix"]) :
        header = {"Authorization": "Bearer %s" % token}
        message = json["data"]["query"]
        logger.info("Receive request! - "+str(message)+" from user - "+str(cec))
        if (email_previx != config["bot_email_prefix"]):            
            logger.info("Access Denied from user - "+str(email))
            return "ACCESS DENINED"
        name_url = " https://webexapis.com/v1/people?email=" + cec+"%40"+email_previx
        api_name_response = requests.get(name_url, headers=header, verify=False)
        response_name_json = api_name_response.json()
        name = response_name_json["items"][0]["firstName"]
        if (name):
            if mode == "nso":
                logger.info("NSO Specific Pipeline")
                llama_response=main(message,cec_in="api",name=name)
                logger.info("Sending request! - "+str(llama_response))
                return {"data":{"id":id,"personEmail":email,"response":llama_response}}
                #creat_issue(message,llama_response,cec)
            elif  mode == "general":
                logger.info("General Pipeline from AnythingLLM")
                llama_response=ollama_main(message,cec_in="api")
                logger.info("Sending request! - "+str(llama_response))
                return {"data":{"id":id,"personEmail":email,"response":llama_response}}
                #creat_issue(message,llama_response,cec)
            else:
                print("Internal Error")
                logger.error("invalid mode")
                return "Internal Error"
    else:
        return "IGNORE"



@app.route("/",methods=['POST'])    # all request for localhost:4444/  will reach this method
def recv():
    # Get the json data
    json = request.json
    print (request.url, file = sys.stdout)
    # Retrieving message ID, person ID, email and room ID from message received
    message_id = json["data"]["id"]
    #user_id = json["data"]["personId"]
    email = json["data"]["personEmail"]
    cec=email.split("@")[0]
    #room_id = json["data"]["roomId"]
    #log = datetime.now()
    #print("*****************"+str(log)+"*******************"+"\nMessage ID: "+message_id+"\nUser ID: "+user_id+"\nEmail: "+email+"\nRoom ID: "+room_id+"\n********************END********************\n\n")
    #room_id = room_id_ticket
    email_previx=email.split("@")[1]
    if (email_previx != "webex.bot") and (email_previx == config["bot_email_prefix"]) :
        header = {"Authorization": "Bearer %s" % token}
        get_rooms_url = "https://api.ciscospark.com/v1/messages/" + message_id
        api_response = requests.get(get_rooms_url, headers=header, verify=False)
        response_json = api_response.json()
        message = response_json["text"]
        logger.info("Receive request! - "+str(message)+" from user - "+str(cec))
        if (email_previx != config["bot_email_prefix"]):
            send("Access Denied",cec)
            logger.info("Access Denied from user - "+str(email))
            return "ACCESS DENINED"
       
        name_url = " https://webexapis.com/v1/people?email=" + cec+"%40"+email_previx
        api_name_response = requests.get(name_url, headers=header, verify=False)
        response_name_json = api_name_response.json()
        #print(response_name_json)
        name = response_name_json["items"][0]["firstName"]


        if (name):
            if mode == "nso":
                logger.info("NSO Specific Pipeline")
                llama_response=main(message,cec_in=cec,name=name)
                logger.info("Sending request! - "+str(llama_response))
                send(llama_response,cec)
                creat_issue(message,llama_response,cec)
            elif  mode == "general":
                logger.info("General Pipeline from AnythingLLM")
                llama_response=ollama_main(message,cec_in=cec)
                logger.info("Sending request! - "+str(llama_response))
                send(llama_response,cec)
                creat_issue(message,llama_response,cec)
            else:
                print("Internal Error")
                logger.error("invalid mode")
        return "OK!"
    else:
        return "IGNORE"



if __name__ == '__main__':
        if config["get_content_type"] == "langchain_rag" or config["get_content_type"] == "hybrid":
            logger.info("Initializing Gitbook VDB")
            vdb_init(True)
            logger.info("Initializing Gitbook VDB......Done")
            logger.info("Initializing Changelog Explorer VDB")
            changelog_init()
            logger.info("Initializing Changelog Explorer VDB......Done")

        if len(sys.argv)>2:
            flag=sys.argv[1]
            if flag == "--webhook_reg":
                public_url=sys.argv[2]
                webhook_reg(public_url)
            else:
                print("invalid flag")
        else:
            if not token: 
                print("Webex Token is empty. ")
                print("Than set export ai_bot_token=<webex_bot_token> and try again")
                exit(1)
            else:
                print("Oauth token exist: "+token)
            
            schedule_update()
            logger.info("Initializing.......Done")
            logger.info("Server Up and waiting for request")
            from waitress import serve
            serve(app, host="0.0.0.0", port=7001)
