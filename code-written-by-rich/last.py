#!/usr/bin/python

import http.client
import urllib
import json
import re
import time

tdxCategoryID   = 27

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

    #allArticles = getOldKBArticles(wisconsinConnection, wisconsinHeaders, False)
    #print("All: " + str(len(allArticles)))

    blahKBConnection = http.client.HTTPSConnection('answers.uillinois.edu')
    #publicArticles = getOldKBArticles(blahKBConnection, oldKBHeaders, True)
    #print("Public: " + str(len(publicArticles)))

    tdxConnection.request('POST', '/TDWebApi/api/auth', tdxLoginData, tdxHeaders)
    tdxLoginResponse = tdxConnection.getresponse()
    if tdxLoginResponse.status != 200:
        exit()
    tdxBearerToken = tdxLoginResponse.read()
    tdxHeaders['Authorization'] = 'Bearer ' + tdxBearerToken
    
    #publicArticleIDs = [article["id"] for article in publicArticles]
    
    #privateArticles = [d for d in allArticles if d['id'] not in publicArticleIDs]

    #print("Private: " + str(len(privateArticles)))
    
    for update in updates:
        oldID = update['old']
        newID = update['new']

        print("Updating KB article " + str(newID))

        articleURL = "/uic/api/v1/private/articles/" + str(oldID)
        wisconsinConnection.request("GET", articleURL, None, wisconsinHeaders)
        articleResponse = wisconsinConnection.getresponse()
        if articleResponse.status != 200:
            exit()
        articleData = articleResponse.read().decode('utf-8', errors="ignore")
        blah = re.sub(r'style\s*?=\s*?".*?"', r'', articleData)
        articleObject = json.loads(articleData)
        
        tdxKBArticle = constructTDXKBArticle(articleObject, oldID, tdxHeaders)

        jsonData = json.dumps(tdxKBArticle)

        asdfConnection   = http.client.HTTPSConnection("help.uillinois.edu")
        asdfConnection.request("PUT", "/TDWebApi/api/37/knowledgebase/" + str(newID), jsonData, tdxHeaders)
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

    BL_YES = 1802
    BL_NO = 1803
    brokenLinks = BL_NO
    if re.search(r'<.*?(?<!src="https://)answers\.uillinois\.edu', body):
        brokenLinks = BL_YES
    elif re.search(r'<.*?(?<!src=)"https://.*?accc\.uic\.edu', body):
        brokenLinks = BL_YES

    IL_YES = 1804
    IL_NO = 1805
    imageLinks = IL_NO
    if re.search(r'<img(?=.*answers\.uillinois\.edu).*>', body):
        imageLinks = IL_YES
    elif re.search(r'<img(?=.*accc\.uic\.edu).*>', body):
        imageLinks = IL_YES


    approvedStatus = 3  ## 3 == 'approved'

    answersArticleAttr         = 2388
    brokenLinksAttr            = 2389
    imageLinksAttr             = 2390
    relatedAnswersArticlesAttr = 2387

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
        "/TDWebApi/api/people/lookup?searchText=" + email, None, tdxHeaders)
    lookupResponse = lookupConnection.getresponse()
    lookupData = lookupResponse.read()
    users = json.loads(lookupData)
    for index, user in enumerate(users):
        if user["PrimaryEmail"] == email:
            return user["UID"]
    return None

updates = [
  {'old': 65941, 'new': 758},
  {'old': 67796, 'new': 759},
  {'old': 65937, 'new': 763},
  {'old': 65947, 'new': 1631},
  {'old': 65971, 'new': 764},
  {'old': 85687, 'new': 765},
  {'old': 67799, 'new': 766},
  {'old': 65940, 'new': 1533},
  {'old': 67790, 'new': 767},
  {'old': 94588, 'new': 895},
  {'old': 96239, 'new': 900},
  {'old': 75213, 'new': 1664},
  {'old': 67791, 'new': 804},
  {'old': 86292, 'new': 805},
  {'old': 82549, 'new': 1680},
  {'old': 65948, 'new': 812},
  {'old': 91017, 'new': 809},
  {'old': 72159, 'new': 810},
  {'old': 78222, 'new': 1679},
  {'old': 86211, 'new': 811},
  {'old': 87636, 'new': 821},
  {'old': 106861, 'new': 825},
  {'old': 75212, 'new': 842},
  {'old': 82293, 'new': 1601},
  {'old': 75521, 'new': 877},
  {'old': 75029, 'new': 959},
  {'old': 100782, 'new': 1593},
  {'old': 74779, 'new': 1571},
  {'old': 76500, 'new': 1878},
  {'old': 50367, 'new': 1572}
]


if __name__ == "__main__":
    main()
