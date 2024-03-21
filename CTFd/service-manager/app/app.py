# GCLOUD Quote Limits to increase
#
# - Instance limit per region for us-east5
#     Default is 100. Ask for 2000. This will allow for 1000 containers for that region.
#
# - Write requests per minute per region for us-east5
#     Default is 60.  Ask for 200.  Too low as value and we cannot spin up services as fast
#     as we want.
#
# One easy hedge against these limits is to deploy to MULTIPLE regions.
# see the REGIONS[] list below for how we can do this.

import datetime
import hashlib
from flask import Flask
from flask import Response
from flask import request
from flask_basicauth import BasicAuth
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

app = Flask(__name__)

app.config['BASIC_AUTH_USERNAME'] = 'private'
# if this env var is not defined, this will fail early and not run at all
app.config['BASIC_AUTH_PASSWORD'] = os.environ['BA_PASSWORD']
app.config['BASIC_AUTH_FORCE'] = True

basic_auth = BasicAuth(app)

BACKGROUND_WORK_INTERVAL_SECONDS = 300

# Use this as a prefix when creating any dynamic services.
# Allows us to easily stop them after a given time period.
DYN_SERVICE_PREFIX = "dyn-svc-"
DYN_SERVICE_MAX_LIFETIME_SECONDS = 60*60

# We've requested "instance limit per region" quota increases for these
# regions (from 100 to 1000).
REGIONS = [
    'us-central1',
    'us-east5',
]


SERVICES = {}

# syntax:
# SERVICES[<challenge-name>] = <challenge-service-yaml-filename>
#
# Note: The YAML file MUST contain a placeholder like this:
#       metadata:
#           name: SERVICE-NAME-PLACEHOLDER
#
# This will be replaced by the dynamically-generated service name
SERVICES['order-up'] = 'order-up-gcloud-service.yaml'


@app.route('/')
def root():
    return '<h1>I am Alive</h1>'


ANSI_CMD_REGEX = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')

def trimAnsiTerminalCommands(data):
    return ANSI_CMD_REGEX.sub('', data)


def getRegionFromServiceName(serviceName):
    hash = hashlib.sha256(serviceName.encode('utf8'))
    hashInt = int(hash.hexdigest(), 16)

    return REGIONS[hashInt % len(REGIONS)]


def runCmd(cmd):
    print('------------------------------------------------------------------------------------')
    print('running: ', cmd)
    tokens = cmd.split()
    try:
        result = subprocess.run(tokens, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except: # catch *all* exceptions
        e = str(sys.exc_info()[0])
        msg = 'Error running cmd: ' + cmd + ', ' + e
        print(msg)
        return msg

    rawOutput = result.stdout
    if result.stderr:
        rawOutput += result.stderr

    # print('raw output: ', rawOutput)

    output = rawOutput.decode('utf8')
    output = trimAnsiTerminalCommands(output)
    print('cmd: ', cmd)
    print('output:', output)
    print('------------------------------------------------------------------------------------')

    sys.stdout.flush()
    return output


@app.route('/cmd')
def cmd():
    cmd = request.args.get('cmd')
    if not cmd:
        return 'Something is missing'

    # output = runCmd(cmd)
    output = 'Useful during development, dangerous on PROD'
    return Response(output, mimetype="text/ascii")


def parseOutNewServiceUrl(output):
    match = re.search('(https://\\S+\\.run\\.app)', output)
    return match.group(1) if match else None


@app.route('/service', strict_slashes=False)
def listServicesAvailabeToStart():
    response = list(SERVICES.keys())
    return response


def generateUniqueServiceName(serviceName, uniqueChalId):
    uniqueChalId = str(uniqueChalId)
    NO_SHELL_INJECTION_REGEX = '^[a-z0-9]+$'
    if not re.match(NO_SHELL_INJECTION_REGEX, uniqueChalId):
        return None, "invalid unique_chal_id"

    if len(uniqueChalId) <= 1 or len(uniqueChalId) > 20:
        return None, "invalid length of unique_chal_id"

    uniqueServiceName = f'{DYN_SERVICE_PREFIX}{serviceName}-{uniqueChalId}'
    if len(uniqueServiceName) > 63:
        return None, "generated service name is greater than 63 characters: " + uniqueServiceName

    return uniqueServiceName, None


def getSecondsToLive(line):
    deployTime = getDeployTime(line)
    if not deployTime:
        return 0
    else:
        now = datetime.datetime.now(datetime.timezone.utc)
        secondsSinceDeployment = (now - deployTime).total_seconds()
        secondsToLive = DYN_SERVICE_MAX_LIFETIME_SECONDS - secondsSinceDeployment
        return int(secondsToLive)


def findServiceInstance(uniqueServiceName):
    region = getRegionFromServiceName(uniqueServiceName)
    cmd = f"gcloud run services describe --region={region} --format=json(status.url,status.conditions[0]) {uniqueServiceName}"
    output = runCmd(cmd)

    try:
        data = json.loads(output)
        status = data['status']

        serviceUrl = status['url']
        secondsToLive = getSecondsToLive(status['conditions'][0]['lastTransitionTime'])

        return serviceUrl, secondsToLive

    except:
        return None, 0


@app.route('/service/<serviceName>')
def getServiceInfo(serviceName):
    if serviceName not in SERVICES:
        return {"message": "service is not defined"}, 400

    uniqueChalId = request.args.get('unique_chal_id')
    if not uniqueChalId:
        # they are only asking if this is an available service
        return {"message": "service is available to be started"}, 200

    # here, they are asking about a particular instance of a service
    uniqueServiceName, error = generateUniqueServiceName(serviceName, uniqueChalId)
    if error:
        return {"message": error}, 400

    serviceUrl, secondsToLive = findServiceInstance(uniqueServiceName)
    if serviceUrl:
        message = "service instance is running"
        serviceInstanceRunning = True
    else:
        message = "service instance is not running"
        serviceInstanceRunning = False
    return {"message": message, "serviceInstanceRunning": serviceInstanceRunning, "serviceUrl": serviceUrl, "secondsToLive": secondsToLive}, 200


@app.route('/service/<serviceName>', methods = ['POST'])
def startServiceIntance(serviceName):
    if serviceName not in SERVICES:
        return {"message": "service does not exist"}, 400

    uniqueChalId = request.args.get('unique_chal_id')
    if not uniqueChalId:
        return {"message": "unique_chal_id argument is required"}, 400

    uniqueServiceName, error = generateUniqueServiceName(serviceName, uniqueChalId)
    if error:
        return {"message": error}, 400

    # If the service doesn't exist, this will fail (and we don't care).
    region = getRegionFromServiceName(uniqueServiceName)
    cmd = f'gcloud run services delete {uniqueServiceName} -q --region={region}'
    runCmd(cmd)


    # Create a copy of the base service YAML and replace the service name with our generated name
    sourceServiceYamlFile = os.path.split(__file__)[0] + '/' + SERVICES[serviceName]
    targetServiceYamlFile = f'/tmp/{uniqueServiceName}.yaml'
    shutil.copyfile(sourceServiceYamlFile, targetServiceYamlFile)
    with open(targetServiceYamlFile,'r+') as f:
        data = f.read()
        data = data.replace('SERVICE-NAME-PLACEHOLDER', uniqueServiceName)
        data = data.replace('REGION-PLACEHOLDER', region)
        f.seek(0)
        f.write(data)
        f.truncate()

    cmd = f'gcloud run services replace --region={region} {targetServiceYamlFile}'
    output = runCmd(cmd)

    serviceUrl = parseOutNewServiceUrl(output)
    if not serviceUrl:
        message = 'service failed to start: ' + output
        return {"message": message}, 500

    # Unfortunately, when you create a service using 'replace', to have to be accessible without authentication
    # a separate command is needed.
    cmd = f'gcloud run services add-iam-policy-binding {uniqueServiceName} --region={region} --member=allUsers  --role=roles/run.invoker'
    output = runCmd(cmd)

    message = 'service started'
    if 'Updated' not in output:
        message = message + ', but attempt to make accessible unauthenticated failed: ' + output

    response = {"message": message, "serviceUrl": serviceUrl, "secondsToLive": DYN_SERVICE_MAX_LIFETIME_SECONDS}
    return response, 200



def getDeployTime(line):
    tokens = line.split()
    for token in tokens:
        try:
            deployTime = datetime.datetime.strptime(token, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
            return deployTime
        except:
            pass
    return None


def undeployService(serviceName):
    print('Undeploying: ', serviceName)

    region = getRegionFromServiceName(serviceName)
    cmd = f'gcloud run services delete {serviceName} -q --region={region}'
    runCmd(cmd)


def processOneService(service):
    metadata = service['metadata']
    if metadata:
        serviceName = metadata['name']
        if serviceName and serviceName.startswith(DYN_SERVICE_PREFIX):
            status = service['status']
            secondsToLive = getSecondsToLive(status['conditions'][0]['lastTransitionTime'])
            if secondsToLive <= 0:
                undeployService(serviceName)


def pruneOldDynamicServices():
    cmd = f'gcloud run services list --format=json(status.url,metadata.name,status.conditions[0])'
    output = runCmd(cmd)

    services = json.loads(output)
    for service in services:
        processOneService(service)


def doPeriodicWork():
    pruneOldDynamicServices()


def periodicWorkLoop():
    while True:
        print('doing work at: ', time.ctime())
        try:
            doPeriodicWork()
        except: # catch *all* exceptions
            e = str(sys.exc_info()[0])
            print('Exception in periodic work: ', e)

        sys.stdout.flush()
        time.sleep(BACKGROUND_WORK_INTERVAL_SECONDS)


def setupPeriodicWorkerLoop():
    job_thread = threading.Thread(target=periodicWorkLoop)
    job_thread.start()

setupPeriodicWorkerLoop()

print('fly bird')

if __name__ == "__main__":
    app.run(debug=False)

