#!/usr/bin/python

#  Remember to:
#    chmod 755 kim.py
#  if running this from Unix-y systems

import urllib
import urllib2
import json

query_args = { 'catId' : '8553' }
encoded_args = urllib.urlencode(query_args)

#  answers.uillinois.edu insists that we say we're okay to handle JSON replies
request = urllib2.Request('https://answers.uillinois.edu/uic/api/v1/articles?' + encoded_args)
request.add_header('Accept', 'application/json')

response = urllib2.urlopen(request).read()

responseObject = json.loads(response)
thisPage = responseObject['_links']['self']['href']
lastPage = responseObject['_links']['last']['href']

print(thisPage)
print(lastPage)
