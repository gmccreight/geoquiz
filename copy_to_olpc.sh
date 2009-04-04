#!/bin/sh

#------------------------------------------------------------------------
# Allow for editing files on Windows and sending them to the olpc

for i in {1..100000}; do
    
    sleep 1

    if [ `nice find ../Geoquiz -cnewer ../Geoquiz_copy_timestamp | wc -l` -gt 0 ]; then
        touch ../Geoquiz_copy_timestamp
        scp ../Geoquiz/* olpc@192.168.168.113:~/Activities/Geoquiz.activity/
    fi
done