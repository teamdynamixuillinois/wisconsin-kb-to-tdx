#!/usr/bin/python

import http.client
import urllib
import json
import re
import time

tdxCategoryID  = 27

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
    
    for articleID in mia:
        #print("Adding KB article " + str(articleID))

        articleURL = "/uic/api/v1/private/articles/" + str(articleID)
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
        asdfConnection.request("POST", "/TDWebApi/api/37/knowledgebase", jsonData, tdxHeaders)
        response = asdfConnection.getresponse()

        if response.status == 403:
            print("Denied!")

        if response.status != 201:
            responseData = response.read()
            serverReply = json.loads(responseData)
            print(response.status)
           
            #exit()

        print("Added old KB article " + str(articleID))
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

mia = [
  108735,109007,108678,108753,108745,108675,109005,
  109012,109008,109006,109014,109016,109017,109018,
  109019,109021,109023,109025,109041,108776,108757,
  108756,108752,109026,109020,108746,109010,109004,
  108988,108750,108749,108748,108755,108754,108348,
  108347,108331,108968,108339,108962,108716,108718,
  108719,108720,108721,108739,108722,108723,108725,
  108726,108727,108729,108730,108731,108732,108733,
  108736,108737,108738,108802,108821,108803,108680,
  108724,108734,108810,108806,108800,108798,108325,
  108863,108819,108818,108816,108815,108814,108811,
  108801,108728,108714,108717,107579,107378,108320,
  108747,108751,107648,107580,107573,107273,107560,
  107377,108338,108335,108330,108328,108319
]


if __name__ == "__main__":
    main()
