import concurrent.futures
import os
import requests
from requests.auth import HTTPBasicAuth

URL = 'https://service-manager-okntin33tq-uc.a.run.app/'

SECRET = os.environ['BA_PASSWORD']

def tryUrl(uniqueId):
    url = URL + 'service/order-up'

    params = {'unique_chal_id': str(uniqueId)}

    basic = HTTPBasicAuth('private', SECRET)

    print(url, uniqueId)
    response = requests.post(url, params=params, auth=basic)
    print(response.status_code, response.text)

NUM_INSTANCES=5
NUM_CLIENT_THREADS=10

workload = []
for id in range(0,NUM_INSTANCES):
    workload.append('a' + str(id))

with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_CLIENT_THREADS) as executor:
    executor.map(tryUrl, workload)

# tryUrl(1)
# url = URL + 'service/order-up'
# basic = HTTPBasicAuth('private', SECRET)
# print(url)
# response = requests.get(url, auth=basic)
# print(response.status_code, response.text)
