#!/bin/bash

if [ -z "$1" ]
  then
    echo "No argument supplied"
    exit 1
fi

git init
find * -size +50M -type f -print >> .gitignore
git add -A
git commit -m "first commit"
git branch -M main
git remote add origin "https://raychorn:$1@github.com/raychorn/svn_Wing_IDE.git"
git push -u origin main
