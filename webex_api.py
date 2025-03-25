import requests
import os
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
token = os.getenv('ai_bot_token') # You can get it on https://developer.webex.com/endpoint-messages-post.html

def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data

def send(message,cec):
    if cec != "api":
        get_rooms_url = "https://webexapis.com/v1/messages/"
        requests.packages.urllib3.disable_warnings() #removing SSL warnings
        message_data=message
        message_markdown_data=message_data
        payload={
                    "toPersonEmail": str(cec)+"@cisco.com",
                    "text": message_data,
                    "markdown":message_markdown_data
            }

        header = {"Authorization": "Bearer %s" % token, "content-type": "application/json"}
        api_response = requests.post(get_rooms_url, json=payload, headers=header, verify=False) 
        if api_response.status_code != 200:
            print ('Message Rply Error !')
            print ("[ERROR] Response Code: "+str(api_response.status_code))
            print ("[ERROR] Response Json: "+str(api_response.text))
    else:
        return message
def send_attach(message,attach,cec):
    get_rooms_url = "https://webexapis.com/v1/messages/"
    requests.packages.urllib3.disable_warnings() #removing SSL warnings
    payload={
                  "toPersonEmail": str(cec)+"@cisco.com",
                  "markdown":message,
                  "attachments": [
                      {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": attach
                      }
                      ]
          }

    header = {"Authorization": "Bearer %s" % token, "content-type": "application/json"}
    api_response = requests.post(get_rooms_url, json=payload, headers=header, verify=False) 
    if api_response.status_code != 200:
        print ('Message Rply Error !')
        print ("[ERROR] Response Code: "+str(api_response.status_code))
        print ("[ERROR] Response Json: "+str(api_response.text))

def webhook_reg(public_url):
    # Registering Webhook
    header = {"Authorization": "Bearer %s" % token, "content-type": "application/json"}
    requests.packages.urllib3.disable_warnings() #removing SSL warnings
    post_message_url = "https://webexapis.com/v1/webhooks"
    # Preparing the payload to register. We are only interested in messages here, but feel free to change it
    payload = {
        "name": "Ask NSO Anything",
        "targetUrl": public_url,
        "resource": "messages",
        "event": "created"
        }
    api_response = requests.post(post_message_url, json=payload, headers=header, verify=False) #Registering webhook
    if api_response.status_code <200 and api_response.status_code >=300:
        print ('Webhook registration Error !')
        print ("[ERROR] Response Code: "+str(api_response.status_code))
        print ("[ERROR] Response Json: "+str(api_response.text))
    else:
        webhook_id=api_response.json()["id"]
        verify_url="https://webexapis.com/v1/webhooks/"+webhook_id
        api_response = requests.get(verify_url, headers=header, verify=False)
        if api_response.status_code >=200 and api_response.status_code <300:
            print("Webhook register successful")
        else:
            print("Webhook register failed")

