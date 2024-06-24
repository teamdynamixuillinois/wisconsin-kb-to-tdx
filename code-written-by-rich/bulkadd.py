#!/usr/bin/python

#  Remember to:
#    chmod 755 bulkadd.py
#  if running this from Unix-y systems

#  We need these, they are part of standard Python
import http.client
import urllib
import json
import re

#  Create a connection object and set its target to answers.uillinois.edu
conn = http.client.HTTPSConnection("answers.uillinois.edu")

#  answers.uillinois.edu insists that we say we're okay to handle JSON replies
headers = {'Accept': 'application/json'}
category = "8620"
articles = []

#  Okay, make the API request to answers.uillinois.edu and ask for 
#  a category
nextPage = "/uic/api/v1/articles?catId=" + category
while True:
  conn.request("GET", nextPage, headers = headers)
  response = conn.getresponse()
  if response.status != 200:
    exit()
  responseData = response.read()
  responseObject = json.loads(responseData)
  thisPage = responseObject['_links']['self']['href']
  lastPage = responseObject['_links']['last']['href']
  articles += responseObject['_embedded']['article']
  if thisPage == lastPage:
    break
  nextPage = responseObject['_links']['next']['href']

completeArticles = []
i = 0
for article in articles:
  #print("-- Article " + str(i) + " ----------")
  articleID = article['id']
  articleURL = "https://answers.uillinois.edu/uic/api/v1/articles/" + articleID
  conn.request("GET", articleURL, None, headers)
  articleResponse = conn.getresponse()
  if articleResponse.status != 200:
    exit()
  articleData = articleResponse.read().decode('utf-8', errors="ignore")
  articleObject = json.loads(articleData)
  articleBody = articleObject["body"]
  articleBody = re.sub('style=".*"', '', articleBody)



  print(articleBody)
  print("-----  " + str(i) + "  -----")
  i += 1

  if i > 100:
    exit()
  #print(articleData + ",")
  #completeArticles.append(articleData)
  #break

  #articleData = articleData.encode("utf-8")
  #thingy = json.loads(articleData)

  #completeArticles.append(thingy)

#print(completeArticles)
