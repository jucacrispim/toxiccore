#!/bin/bash

rm -rf dist/

python -m build

cd dist

fname=`ls | grep tar`
project_name=toxicbuild-core

curl -F file=@$fname -F prefix=pypi/$project_name $PYPI_UPLOAD_URL -H "Authorization: Key $TUPI_AUTH_KEY"
