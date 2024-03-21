Defines an image to manage google cloud run services.

Designed to be used by the "private_challenges" CTFd custom plugin.

# Running Locally

Assuming you have gcloud installed an auth'd, you can just do:
```
python3 app.py
```

To run inside docker, see `build-and-run-locally.sh`
Note: This docker container will NOT be auth'd so it won't work, but it useful for some forms of testing.


# Deploying to gcloud

See details in `build-and-deploy-to-gcloud.sh`

## Selecting a security password

The REST API exposed by this service manager is protected by a password.

Please choose a long/random password.

Set it like this before running the `build-and-deploy-to-gcloud.sh` script:
```
export BA_PASSWORD=<your-password-here>
```

Beware special shell characters like quotes, dollar signs, etc.. that might affect your export statement.


The username is: `private`

After the service manager starts, click the link it gives you and confirm you can login to the root page with these credentials:

username: private
password: from $BA_PASSWORD at the time `build-and-deploy-to-gcloud.sh` was run



## Setting up a suitable Service Account

As mentioned in the above script, this requires creation of a special "service account" with the OWNER role.

This is needed in order to create and destroy other services.

The easiest way to do this is:

1. Go to the your Cloud Run service page. e.g. https://console.cloud.google.com/run/create?project=wolvctf-2024
2. Click Create Service
3. Expand the Container(s), Volumes, Networking, Security panel
4. Click on Security
5. Click on the "Service account" input field
6. In the panel that is shown, click CREATE NEW SERVICE ACCOUNT
7. In "Service account name", enter your desired account name
8. Click CREATE
9. Open the "Select a role" dropdown
10. Select Owner on the right side
11. Click Done


Note: At least once, I got an error when trying to select the role in the steps above.
In that case, I went to the main IAM page and clicked GRANT ACCESS and then searched
for the account name I used earlier inside the "New principals" field.  Then I could
add the Owner role.


You should now be able to use this service account in the `build-and-deploy-to-gcloud.sh` script.

You want to delete the account you just created, goto here:

https://console.cloud.google.com/iam-admin/iam?project=wolvctf-2024


## Testing the service using curl

Create a new service:

```
curl -u private -v -X POST https://service-manager-q2sldmbtwa-ul.a.run.app/service/order-up?unique_chal_id=111
```

expect response like:

```
{"message":"service started","secondsToLive":3600,"serviceUrl":"https://dyn-svc-order-up-111-q2sldmbtwa-ue.a.run.app"}
```

Check the status of an existing service:

```
curl -u private -v https://service-manager-q2sldmbtwa-ul.a.run.app/service/order-up?unique_chal_id=111
```

output like:

```
{"message":"service instance is running","secondsToLive":3452,"serviceInstanceRunning":true,"serviceUrl":"https://dyn-svc-order-up-111-q2sldmbtwa-ue.a.run.app"}
```

## GCLOUD Quota Limits to increase

- Instance limit per region for us-east5
  Default is 100. Ask for 2000. This will allow for 1000 containers for that region.

- Write requests per minute per region for us-east5
  Default is 60.  Ask for 200.  Too low as value and we cannot spin up services as fast
  as we want.

One easy hedge against these limits is to deploy to MULTIPLE regions.
see the REGIONS[] list in app.py for how we can do this.

Go here:  https://console.cloud.google.com/iam-admin/quotas?project=wolvctf-2024

The find the quota you want to change, select it and click EDIT QUOTAS.  You'll have to fill out
some request info.  When I did this in Dec, my requests were granted within a few hours. (but YMMV)




