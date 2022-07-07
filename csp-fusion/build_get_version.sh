#!/bin/sh

PROD_DEPLOYMENT_FILE=$(ls deploy/k8s/prod/*cronjob*.yml)
DOCKER_IMAGE_VERSION=$(grep image: ${PROD_DEPLOYMENT_FILE} | cut -d ":" -f4)
echo "${DOCKER_IMAGE_VERSION}"
