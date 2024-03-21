#!/bin/bash

if [[ -z "${BA_PASSWORD}" ]]
then
  echo "Must define BA_PASSWORD before running, this will be used to talk to the service in gcloud"
  exit 1
fi

docker compose build

IMAGE_AND_TAG=service-manager:1.0
# Our CTFd instance will be in us-central1 and it will be talking to this service
# so make this in the same region.
GCLOUD_REGION=us-central1
GCLOUD_PROJECT=wolvctf-2024
GCLOUD_ARTIFACT_REPOSITORY=locker
GCLOUD_TAG=us-east5-docker.pkg.dev/$GCLOUD_PROJECT/$GCLOUD_ARTIFACT_REPOSITORY/$IMAGE_AND_TAG

docker tag $IMAGE_AND_TAG $GCLOUD_TAG

docker push $GCLOUD_TAG


# You must create a service account that has the OWNER role so that it can
# start/stop other services.
GCLOUD_SERVICE_ACCOUNT=google-cloud-cli@wolvctf-2024.iam.gserviceaccount.com


# avoid accumulation of unused "revisions"
gcloud run services delete --region=$GCLOUD_REGION -q service-manager &> /dev/null

# The --no-cpu-throttling option is needed since we reclaim expired services in a background thread.
gcloud run deploy service-manager --image=$GCLOUD_TAG --set-env-vars="BA_PASSWORD=$BA_PASSWORD" --allow-unauthenticated --port=5000 --service-account=$GCLOUD_SERVICE_ACCOUNT --min-instances=1 --max-instances=5 --concurrency=10 --cpu=2 --memory=2Gi --region=$GCLOUD_REGION --project=$GCLOUD_PROJECT --no-cpu-throttling
