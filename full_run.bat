@echo off
cd /D "%~d0%~p0"
IF %ERRORLEVEL%==0 GOTO PATH_IS_OK
exit
:PATH_IS_OK

fss_save.py ./
fss_merge.py ./ --file=index_hash_all.yaml --not-add-date
fss_compare.py --old index_hash_all_old.yaml --new index_hash_all.yaml
pause
