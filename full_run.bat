@echo off
cd /D "%~d0%~p0"
IF %ERRORLEVEL%==0 GOTO PATH_IS_OK
exit
:PATH_IS_OK

rem del /s /q .index_hash.yaml
fs_struct_to_yaml.py ./
fs_struct_merge_to_once_yaml.py ./ --file=index_hash_all.yaml --not-add-date
fs_struct_comparison.py --old index_hash_all_old.yaml --new index_hash_all.yaml
pause
