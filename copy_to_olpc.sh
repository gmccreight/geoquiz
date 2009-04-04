#!/bin/sh

#------------------------------------------------------------------------
# Allow for editing files on Windows and sending them to the olpc

for i in {1..100000}; do
    
    sleep 1

    if [ `nice find ../Geoquiz -cnewer ../Geoquiz_copy_timestamp | wc -l` -gt 0 ]; then
        touch ../Geoquiz_copy_timestamp
        ssh olpc@192.168.168.113 "rm -r ~/Activities/Geoquiz.activity"
        scp -r ../Geoquiz olpc@192.168.168.113:~/Activities/Geoquiz.activity
        ssh olpc@192.168.168.113 "rm -r ~/Activities/Geoquiz.activity/.git"
    fi
done