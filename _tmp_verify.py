import requests
s = requests.Session()
base = 'http://127.0.0.1:9099'
# login
r = s.post(base + '/api/auth/login', json={'username':'pscly','password':'cly123'})
r.raise_for_status()
print('login ok', r.json().get('username'))
# create key -> creates crawler
r = s.post(base + '/api/keys', json={'name':'pw-key-1'})
r.raise_for_status()
key = r.json()
print('key id', key['id'], 'crawler_id', key.get('crawler_id'))
# list crawlers
r = s.get(base + '/pa/api/me')
r.raise_for_status()
clist = r.json()
assert clist, 'no crawlers'
cid = clist[0]['id']
print('crawler id', cid)
# set crawler public
r = s.patch(base + f'/pa/api/me/{cid}', json={'is_public': True})
r.raise_for_status()
cr = r.json()
slug = cr.get('public_slug')
print('public slug', slug)
# fetch public api
r = s.get(base + f'/pa/{slug}/api')
r.raise_for_status()
print('public api ok type=', r.json().get('type'))
# fetch public page
r = s.get(base + f'/pa/{slug}')
r.raise_for_status()
print('public page ok, len=', len(r.text))
# heartbeats endpoint
r = s.get(base + f'/pa/api/me/{cid}/heartbeats?limit=10')
r.raise_for_status()
print('heartbeats count', len(r.json()))
