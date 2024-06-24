#!/usr/bin/python

# Communication and Collaboration
#   Answers KB category ID = 7275
#   TDX side category ID = 8

# Desktop and Mobile Computing
#   Answers KB category ID = 7276
#   TDX category ID = 9

# Information Security
#   Answers KB = 7277
#   TDX = 10

# Infrastructure
#   Answers KB = 7278
#   TDX = 11

# Professional Services
#   Answers KB = 7280
#   TDX = 12

# Research
#   Answers KB = 7279
#   TDX = 13

# Teaching and Learning
#   Answers KB = 7272
#   TDX = 14

# Technology Solutions Service Costs
#   Answers KB = 8620
#   TDX = 15

#    should be set to Yes if the string "answers.uillinois.edu" or "accc.uic.edu" is found
#    is found in either the Summary or the Body text*
#    ignore anything within an image tag

# <(?!img).*src\s*=\s*".*.anwers\.uillinois\.edu.*>
# <(?!img).*src\s*=\s*".*.accc\.uic\.edu.*>

# And sandbox side is same name, ID 2114; yes = 689, no = 690
# And the new category for teaching and learning is ID 16

import http.client
import urllib
import json
import re
import time

oldKBCategoryID = str(7272)
tdxCategoryID   = 16

def main():
    oldKBConnection = http.client.HTTPSConnection("answers.uillinois.edu")
    tdxConnection   = http.client.HTTPSConnection("help.uillinois.edu")

    oldKBHeaders = {'Accept': 'application/json'}
    tdxHeaders   = {'Content-type': 'application/json'}

    tdxCredentials = {'username': 'techsolapi@uic.edu', 'password': 'xxxxxxxxxxx'}
    tdxLoginData = json.dumps(tdxCredentials)

    tdxConnection.request("POST", "/SBTDWebApi/api/auth", tdxLoginData, tdxHeaders)
    tdxLoginResponse = tdxConnection.getresponse()
    if tdxLoginResponse.status != 200:
        exit()
    tdxBearerToken = tdxLoginResponse.read()
    tdxHeaders['Authorization'] = "Bearer " + tdxBearerToken

    oldKBArticles = getOldKBArticlesForCategory(oldKBConnection, oldKBHeaders, oldKBCategoryID)

    for article in oldKBArticles:
        articleID = article['id']
        #if articleID == '91238':
        #    continue
        #if articleID == '92088':
        #    continue
        print("Adding old KB article " + str(articleID))

        articleURL = "https://answers.uillinois.edu/uic/api/v1/articles/" + articleID
        oldKBConnection.request("GET", articleURL, None, oldKBHeaders)
        articleResponse = oldKBConnection.getresponse()
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

        #if response.status 200:
        #    responseData = response.read()
        #    serverReply = json.loads(responseData)
        #    print(serverReply)
        #    exit()

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

    ownerUUID = findOwnerUUID(oldKBArticle["owner"], tdxHeaders)
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


def getOldKBArticlesForCategory(conn, headers, category):
    articles = []
    nextPage = "/uic/api/v1/articles?catId=" + category
    while True:
      conn.request("GET", nextPage, headers = headers)
      response = conn.getresponse()
      if response.status != 200:
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

def findOwnerUUID(name, tdxHeaders):
    if name in owners.keys(): 
        email = owners[name]
    else:
        email = "amarino@uic.edu"
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

owners = {
    "Alice W.":     "abw@uic.edu",
    "Alvin T.":     "ataylor@uic.edu",
    "Anany M.":     "anmaini@uic.edu",
    "Andrew H.":    "herbie@uic.edu",
    "Angel Q.":     "angelq@uic.edu",
    "Anthe M.":     "amitra2@uic.edu",
    "Anthony M.":   "amarino@uic.edu",
    "Barry G.":     "goldbar@uic.edu",
    "Brian L.":     "brianl@uic.edu",
    "Bryan M.":     "mainvill@uic.edu",
    "Charles N.":   "nutallc@uic.edu",
    "Chase L.":     "clee231@uic.edu",
    "Cheryl M.":    "hitosis@uic.edu",
    "Crystal O.":   "crystalo@uic.edu",
    "Cynthia H.":   "cynthiar@uic.edu",
    "Dave U.":      "uher@uic.edu",
    "Dean D.":      "ddd@uic.edu",
    "Derek O.":     "dortiz27@uic.edu",
    "Ed Z.":        "edz@uic.edu",
    "Eddie C.":     "ecampb5@uic.edu",
    "Eduardo R.":   "erodri80@uic.edu",
    "Elizabeth R.": "elromero@uic.edu",
    "Esteban P.":   "esteban@uic.edu",
    "Frank F.":     "fferna2@uic.edu",
    "Fredy A.":     "fredy@uic.edu",
    "Gary M.":      "morrigr@uic.edu",
    "Greg C.":      "crn1@uic.edu",
    "Heather O.":   "heather@uic.edu",
    "Himanshu S.":  "himanshu@uic.edu",
    "Hussain Z.":   "hzaidi@uic.edu",
    "Isaias H.":    "isaias@uic.edu",
    "James O.":     "joleary@uic.edu",
    "Janet S.":     "janet@uic.edu",
    "Jason M.":     "jasonm@uic.edu",
    "Jason R.":     "jcrochon@uic.edu",
    "Jelene C.":    "jelene@uic.edu",
    "Jemma K.":     "jku@uic.edu",
    "Jim M.":       "montanez@uic.edu",
    "John M.":      "jmcderm1@uic.edu",
    "Joshua F.":    "joshua@uic.edu",
    "Landen D.":    "lydixon@uic.edu",
    "Margaret B.":  "mbird@uic.edu",
    "Marius H.":    "marius@uic.edu",
    "Mark G.":      "mgoedert@uic.edu",
    "Mat W.":       "mat@uic.edu",
    "Matt A.":      "mander6@uic.edu",
    "Matthew P.":   "mpatte2@uic.edu",
    "Michael L.":   "mlarue4@uic.edu",
    "Mike K.":      "mkirda@uic.edu",
    "Nia E.":       "ne7@uic.edu",
    "Nilton G.":    "njgarcia@uic.edu",
    "Paul N.":      "pauln@uic.edu",
    "Qeshawnda H.": "ghaynes@uic.edu",
    "Radhika R.":   "rsreddy@uic.edu",
    "Raul M.":      "mendieta@uic.edu",
    "Richard W.":   "richwolf@uic.edu",
    "Roberto U.":   "rullfig@uic.edu",
    "Roger D.":     "rogerd@uic.edu",
    "Ryan S.":      "szymkie1@uic.edu",
    "Scheneka E.":  "edward@uic.edu",
    "Scott R.":     "sorobert@uic.edu",
    "Sherri R.":    "sherrir@uic.edu",
    "Sidney H.":    "shood@uic.edu",
    "Steve J.":     "stevej@uic.edu",
    "Steve S.":     "ssabo@uic.edu",
    "Szymon M.":    "szymonm@uic.edu",
    "Teresa B.":    "tboc@uic.edu",
    "Thomas O.":    "tjokon@uic.edu",
    "Tom W.":       "twiese@uic.edu",
    "Will M.":      "wbm1@uic.edu",
    "William C.":   "wchan21@uic.edu",
    "William L.":   "wlim@uic.edu",
    "William M.":   "wmehilos@uic.edu",
    "William S.":   "wsull@uic.edu",
    "Yan X.":       "yanxuan@uic.edu",
    "Zack V.":      "zrvirgo@uic.edu"
}

if __name__ == "__main__":
    main()
