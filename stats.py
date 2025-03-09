
def main():
  user_list={}
  with open('logs/audit.log', 'r') as file:
      data = file.readlines()
  for line in data:
        content_lst=line.split("-")
        if len(content_lst) >= 5:
          user=content_lst[-1].strip()
          question=content_lst[-2].strip()
        else:
          user='unknown'
          question=content_lst[-1].strip()
        if user not in user_list.keys():
           user_list[user]=[question]
        else:
           user_list[user].append(question)

  sum=0
  for user,content in user_list.items():
      if  user != "leeli4":
          print(f'{user} - {len(content)}')
          sum=sum+len(content)
  print()
  print("Total Query Count:" + str(sum))

if __name__=="__main__":
    main()
