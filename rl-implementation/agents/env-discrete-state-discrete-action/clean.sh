#!/usr/bin/env bash

read -p "Continue (y/n)?" choice
case "$choice" in 
  y|Y ) rm *.csv *.npy *.pickle stress-test/*.bin;;
  n|N ) echo "Aborted";;
  * ) echo "Invalid input";;
esac
