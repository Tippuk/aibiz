@echo off
echo Running git init... > log.txt 2>&1
git init >> log.txt 2>&1
echo Adding files... >> log.txt 2>&1
git add . >> log.txt 2>&1
echo Committing... >> log.txt 2>&1
git commit -m "Initial commit" >> log.txt 2>&1
echo Checking gh auth... >> log.txt 2>&1
gh auth status >> log.txt 2>&1
echo Creating repo... >> log.txt 2>&1
gh repo create aibiz --public --source=. --remote=origin --push >> log.txt 2>&1
echo Done. >> log.txt 2>&1
