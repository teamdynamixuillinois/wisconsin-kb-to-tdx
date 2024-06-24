#!/usr/bin/python

import http.client
import urllib
import json
import re
import time

tdxCategoryID   = 17

def main():
    wisconsinConnection = http.client.HTTPSConnection('kb.wisc.edu')
    oldKBConnection     = http.client.HTTPSConnection('answers.uillinois.edu')
    tdxConnection       = http.client.HTTPSConnection('help.uillinois.edu')

    wisconsinHeaders = {'Content-type': 'application/json'}
    oldKBHeaders     = {'Accept':       'application/json'}
    tdxHeaders       = {'Content-type': 'application/json'}

    wisconsinCredentials = {
        'username':   'richwolf',
        'client_id':  'richwolf_client',
        'grant_type': 'password',
        'password':   'xxxxxxxxxxxx',
        'scope':      'group:178;site:all;user:richwolf@uic.edu'
    }
    tdxCredentials = {
        'username': 'techsolapi@uic.edu',
        'password': 'xxxxxxxxxxx'
    }

    wisconsinLoginData = json.dumps(wisconsinCredentials)
    tdxLoginData       = json.dumps(tdxCredentials)

    wisconsinConnection.request('POST', '/api/v1/oauth', wisconsinLoginData, wisconsinHeaders)
    wisconsinResponse = wisconsinConnection.getresponse()
    if wisconsinResponse.status != 200:
        exit()
    wisconsinTokenData = wisconsinResponse.read()
    wisconsinTokenRecord = json.loads(wisconsinTokenData)
    wisconsinBearerToken = wisconsinTokenRecord['access_token']
    wisconsinConnection  = http.client.HTTPSConnection('answers.uillinois.edu')
    wisconsinHeaders = {
        'Accept':        'application/json',
        'Authorization': 'Bearer ' + wisconsinBearerToken
    }

    allArticles = getOldKBArticles(wisconsinConnection, wisconsinHeaders, False)
    print("All: " + str(len(allArticles)))

    blahKBConnection = http.client.HTTPSConnection('answers.uillinois.edu')
    publicArticles = getOldKBArticles(blahKBConnection, oldKBHeaders, True)
    print("Public: " + str(len(publicArticles)))

    tdxConnection.request('POST', '/SBTDWebApi/api/auth', tdxLoginData, tdxHeaders)
    tdxLoginResponse = tdxConnection.getresponse()
    if tdxLoginResponse.status != 200:
        exit()
    tdxBearerToken = tdxLoginResponse.read()
    tdxHeaders['Authorization'] = 'Bearer ' + tdxBearerToken
    
    publicArticleIDs = [article["id"] for article in publicArticles]
    
    privateArticles = [d for d in allArticles if d['id'] not in publicArticleIDs]

    print("Private: " + str(len(privateArticles)))
    
    for article in privateArticles:
        articleID = article['id']

        print("Adding old KB article " + str(articleID))

        articleURL = "/uic/api/v1/private/articles/" + articleID
        wisconsinConnection.request("GET", articleURL, None, wisconsinHeaders)
        articleResponse = wisconsinConnection.getresponse()
        if articleResponse.status != 200:
            exit()
        articleData = articleResponse.read().decode('utf-8', errors="ignore")
        blah = re.sub(r'style\s*?=\s*?".*?"', r'', articleData)
        articleObject = json.loads(articleData)
        
        tdxKBArticle = constructTDXKBArticle(articleObject, articleID, tdxHeaders)

        jsonData = json.dumps(tdxKBArticle)

        asdfConnection   = http.client.HTTPSConnection("help.uillinois.edu")
        asdfConnection.request("POST", "/SBTDWebApi/api/37/knowledgebase", jsonData, tdxHeaders)
        response = asdfConnection.getresponse()

        if response.status == 403:
            print("Denied!")

        if response.status != 201:
            responseData = response.read()
            serverReply = json.loads(responseData)
            print(response.status)
            #exit()

        #print("Added old KB article " + str(articleID))
        time.sleep(1)
        #break
        
#p = re.compile(r'<.*style\s*=\s*.*>')

def constructTDXKBArticle(oldKBArticle, oldKBArticleID, tdxHeaders):
    subject = oldKBArticle['title']
    summary = oldKBArticle['summary']
    body = oldKBArticle["body"]

    body = summary + "\n\n<br>\n<br>\n\n" + body
    body = re.sub(r'style\s*?=\s*?".*?"', r'', body)
    body = re.sub(r'class\s*?=\s*?".*?"', r'', body)

    BL_YES = 676
    BL_NO = 677
    brokenLinks = BL_NO
    if re.search(r'<.*?(?<!src="https://)answers\.uillinois\.edu', body):
        brokenLinks = BL_YES
    elif re.search(r'<.*?(?<!src=)"https://.*?accc\.uic\.edu', body):
        brokenLinks = BL_YES

    IL_YES = 689
    IL_NO = 690
    imageLinks = IL_NO
    if re.search(r'<img(?=.*answers\.uillinois\.edu).*>', body):
        imageLinks = IL_YES
    elif re.search(r'<img(?=.*accc\.uic\.edu).*>', body):
        imageLinks = IL_YES


    approvedStatus = 3  ## 3 == 'approved'

    answersArticleAttr         = 2014
    brokenLinksAttr            = 2110
    imageLinksAttr             = 2114
    relatedAnswersArticlesAttr = 2015

    if "seeAlso" in oldKBArticle.keys(): 
        oldKBRelatedArticleIDs = oldKBArticle["seeAlso"]
    else:
        oldKBRelatedArticleIDs = ""

    expiration = oldKBArticle['expiration']
    reviewDateUTC = expiration.split(' ')[0]    + 'T00:00:00Z'

    ownerUUID = findOwnerUUID(oldKBArticle["owner"][0]["userQualified"], tdxHeaders)
    keywordString = oldKBArticle['keywords']
    keywords = keywordString.split(',')
    tags = [keyword.strip() for keyword in keywords]

    return {
        'Subject':            subject,
        'Summary':            summary,
        'Body':               body,
        'CategoryID':         tdxCategoryID,
        'Status':             approvedStatus,
        'Attributes':         [{'ID': answersArticleAttr,         'Value': oldKBArticleID},
                               {'ID': brokenLinksAttr,            'Value': brokenLinks},
                               {'ID': imageLinksAttr,             'Value': imageLinks},
                               {'ID': relatedAnswersArticlesAttr, 'Value': oldKBRelatedArticleIDs}],
        'ReviewDateUTC':      reviewDateUTC,
        'Order':              1.0,
        'IsPublished':        True,
        'IsPublic':           True,
        'WhitelistGroups':    False,
        'InheritPermissions': True,
        'NotifyOwner':        True,
        'OwnerUID':           ownerUUID,
        'OwningGroupID':      None,
        'Tags':               tags
    }


def getOldKBArticles(conn, headers, publicOnly = True):
    articles = []
    nextPage = "/uic/api/v1/articles"
    if publicOnly == False:
        nextPage = "/uic/api/v1/private/articles"
    while True:
      conn.request("GET", nextPage, headers = headers)
      response = conn.getresponse()
      if response.status != 200:
        blah = response.read()
        print(blah)
        exit()
      responseData = response.read().decode('ascii', errors="ignore")
      responseObject = json.loads(responseData)
      thisPage = responseObject['_links']['self']['href']
      lastPage = responseObject['_links']['last']['href']
      articles += responseObject['_embedded']['article']
      if thisPage == lastPage:
        break
      nextPage = responseObject['_links']['next']['href']

    return articles

def findOwnerUUID(owner, tdxHeaders):
    email = "amarino@uic.edu"
    parts = owner.split("@")
    if (len(parts) == 2):
        ownerDomain = parts[1]
        if not(ownerDomain == "uic.edu"):
            email = "fredy@uic.edu"
        else:
            email = owner
    if email == "ddd@uic.edu":
        email = "ddang1@uic.edu"

    lookupConnection = http.client.HTTPSConnection("help.uillinois.edu")
    lookupConnection.request("GET",
        "/SBTDWebApi/api/people/lookup?searchText=" + email, None, tdxHeaders)
    lookupResponse = lookupConnection.getresponse()
    lookupData = lookupResponse.read()
    users = json.loads(lookupData)
    for index, user in enumerate(users):
        if user["PrimaryEmail"] == email:
            return user["UID"]
    return None

if __name__ == "__main__":
    main()
