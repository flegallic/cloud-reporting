#!/bin/bash

# Files to modify
CHANGELOG_FILENAME=CHANGELOG.md
PRP_DEPLOYMENT_FILE=$(ls deploy/k8s/prp/*cronjob-billing.yml)
PROD_DEPLOYMENT_FILE=$(ls deploy/k8s/prod/*cronjob-billing.yml)
DOCKER_IMAGE_NAME="xxxxxxxxxxxxxxxxxxxxxxxxxxxxx\/dd_cloud_reporting\/csp-az-billing"

# Current version (changelog)
VERSION_CHANGELOG=$(grep Version ${CHANGELOG_FILENAME} | awk 'NR==1 { print $2 }')

# New version
version="$VERSION_CHANGELOG"
major=0
minor=0
build=0

# break down the version number into it's components
regex="([0-9]+).([0-9]+).([0-9]+)"
if [[ $version =~ $regex ]]; then
  major="${BASH_REMATCH[1]}"
  minor="${BASH_REMATCH[2]}"
  build="${BASH_REMATCH[3]}"
fi

# check paramater to see which number to increment
if [[ "$1" == "feature" ]]; then
  minor=$(echo $minor + 1 | bc)
  build=0
elif [[ "$1" == "bug" ]]; then
  build=$(echo $build + 1 | bc)
elif [[ "$1" == "major" ]]; then
  major=$(echo $major+1 | bc)
  minor=0
  build=0
else
  echo "Usage: $0 <level> [description]"
  echo "level=major|feature|bug"
  exit 1
fi

# echo the new version number
VERSION_TO_SET="${major}.${minor}.${build}"

# Updating Changelog
VERSION_DATE=$(date +'%d/%m/%Y')

if [ $# -eq 2 ]; then
  VERSION_DESCRIPTION=$2
else
  VERSION_DESCRIPTION="Please fill out description here"
fi

sed -i "/==========/a \\\nVersion ${VERSION_TO_SET} (${VERSION_DATE})\\n--------------------------\\n* ${VERSION_DESCRIPTION}" ${CHANGELOG_FILENAME}

# Updating Deployment files
sed -i "s/image: $DOCKER_IMAGE_NAME:$VERSION_CHANGELOG/image: $DOCKER_IMAGE_NAME:$VERSION_TO_SET/" ${PRP_DEPLOYMENT_FILE}
sed -i "s/image: $DOCKER_IMAGE_NAME:$VERSION_CHANGELOG/image: $DOCKER_IMAGE_NAME:$VERSION_TO_SET/" ${PROD_DEPLOYMENT_FILE}

# It's done announce
echo "Version in files updated from: ${VERSION_CHANGELOG} to: ${VERSION_TO_SET}"
