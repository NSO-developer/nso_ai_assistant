# curl -L \
#   -X POST \
#   -H "Accept: application/vnd.github+json" \
#   -H "Authorization: Bearer <YOUR-TOKEN>" \
#   -H "X-GitHub-Api-Version: 2022-11-28" \
#   https://api.github.com/repos/OWNER/REPO/issues \
#   -d '{"title":"Found a bug","body":"I'\''m having a problem with this.","assignees":["octocat"],"milestone":1,"labels":["bug"]}'


import requests
import json
import urllib.parse
from webex_api import *




def load_config():
  with open('config.json', 'r') as file:
      data = json.load(file)
  return data

def creat_issue(query,answer,cec):
    comment="What%20do%20you%20want%20to%20see%20and%20how%20should%20it%20be%20improved."
    url_msg=urllib.parse.quote_plus(query)
    url_response=urllib.parse.quote_plus(answer)
    msg={ 
    "type": "AdaptiveCard",
    "body": [
        {
            "type": "TextBlock",
            "weight": "Bolder",
            "text": f"Answer to '{query}'",
            "horizontalAlignment": "Left",
            "wrap": True,
            "color": "Light",
            "size": "Large",
            "spacing": "Small"
        },
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"{answer}",
                            "wrap": True
                        }
                    ]
                }
            ]
        },
        {
            "type": "ColumnSet",
            "columns": [
                {
                    "type": "Column",
                    "width": "auto",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "Answer is not accurate?",
                            "wrap": True
                        },
                        {
                            "type": "TextBlock",
                            "text": f"[Let me Know on Github](https://github.com/NSO-developer/nso_ai_assistant/issues/new?title=Inaccurate%20Answer%20from%20AI&body=**Question**%0A{url_msg}%0A%0A**Answer%20from%20AI**%0A{url_response}%0A%0A**Expected%20Answer(Optional)**%0A{comment}.&labels[]=bug) ",
                            "horizontalAlignment": "Left",
                            "size": "Small"
                        }
                    ],
                    "verticalContentAlignment": "Center",
                    "horizontalAlignment": "Left",
                    "spacing": "Small"
                }
            ]
        }
    ],
    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    "version": "1.3"
    }

    send_attach("test",msg,cec)

if __name__=="__main__":
    creat_issue("what is turbo-xml-mode","blahblahblah the blah","leeli4")
