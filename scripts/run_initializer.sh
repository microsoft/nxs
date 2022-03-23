#!/bin/bash

exit_if_failed()
{
    rc=$1
    if [ $rc -ne 0 ];
    then
        exit 1
    fi
}

for file in assets/w4extras/*
do
    filename=`basename $file`
    az storage blob upload --connection-string $BLOBSTORE_CONN_STR \
                            --container-name $BLOBSTORE_CONTAINER \
                            --file $file \
                            --name w4extras/$filename
    exit_if_failed $?
done

for file in assets/w4postprocessing/*
do
    filename=`basename $file`
    az storage blob upload --connection-string $BLOBSTORE_CONN_STR \
                            --container-name $BLOBSTORE_CONTAINER \
                            --file $file \
                            --name w4postprocessing/$filename
    exit_if_failed $?
done

for file in assets/w4preprocessing/*
do
    filename=`basename $file`
    az storage blob upload --connection-string $BLOBSTORE_CONN_STR \
                            --container-name $BLOBSTORE_CONTAINER \
                            --file $file \
                            --name w4preprocessing/$filename
    exit_if_failed $?
done

# register public models
for file in assets/*.py
do
    python3 $file
done