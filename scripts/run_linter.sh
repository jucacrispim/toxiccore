#!/bin/bash

pylint toxiccore/
if [ $? != "0" ]
then
    exit 1;
fi

flake8 toxiccore/

if [ $? != "0" ]
then
    exit 1;
fi

flake8 tests
exit $?;
