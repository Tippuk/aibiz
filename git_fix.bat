@echo off
echo --- Git Fix Log --- > log_fix.txt 2>&1
echo Current branch: >> log_fix.txt 2>&1
git branch >> log_fix.txt 2>&1
echo Status before: >> log_fix.txt 2>&1
git status >> log_fix.txt 2>&1
echo Adding all files... >> log_fix.txt 2>&1
git add . >> log_fix.txt 2>&1
echo Committing changes... >> log_fix.txt 2>&1
git commit -m "Fix: Force add README, requirements and confirm all scripts" >> log_fix.txt 2>&1
echo Pushing to master... >> log_fix.txt 2>&1
git push origin master >> log_fix.txt 2>&1
echo Pushing to main (if exists)... >> log_fix.txt 2>&1
git push origin main >> log_fix.txt 2>&1
echo Status after: >> log_fix.txt 2>&1
git status >> log_fix.txt 2>&1
echo Done. >> log_fix.txt 2>&1
