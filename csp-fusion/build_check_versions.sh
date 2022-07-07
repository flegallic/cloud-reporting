#!/bin/sh

TARGET_VERSION=$1

DOCKER_IMAGE_VERSION=$(./build_get_version.sh)
echo "Version to deploy: ${DOCKER_IMAGE_VERSION}"

CHANGELOG_FILENAME=CHANGELOG.md
VERSION_CHANGELOG=$(grep Version ${CHANGELOG_FILENAME} | awk 'NR==1 { print $2 }')
echo "ChangeLog version: ${VERSION_CHANGELOG}"

if test "${DOCKER_IMAGE_VERSION}" != "${TARGET_VERSION}"; then
    echo "The image version \"${DOCKER_IMAGE_VERSION}\" in K8s does not match expected \"${TARGET_VERSION}\" ! ";
    exit 3;
fi

if git ls-remote --tags origin | cut -d / -f 3 | grep "${DOCKER_IMAGE_VERSION}"; then
		echo "The tag ${DOCKER_IMAGE_VERSION} already exists !";
		exit 1;
elif test "${VERSION_CHANGELOG}" != "${DOCKER_IMAGE_VERSION}"; then
    echo "The file ${CHANGELOG_FILENAME} does not match with version ${DOCKER_IMAGE_VERSION} ! ";
    exit 2;
else
    echo "All versions file are OK. \nLet's continue :)"
fi
