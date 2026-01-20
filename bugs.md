

# warn во время merge
```
FSS MERGE:

H:\Pyt\fssaver>python fss_merge.py "Q:\struct\Natasha" --file=index_hash.yaml
WARN: folder not found:  2024-03-08 _______\.index_hash.yaml
WARN: folder not found:  2024-04-05 ______ _____\.index_hash.yaml
```

# почемуто не правильно работает рекурсия при сохранении

```
Me
- 2022
- 2023
```

надо хотябы пропускать и продолжать работу, но лучше разобраться что пошло не так

Traceback (most recent call last):
  File "H:\Pyt\fssaver\fss_save.py", line 251, in <module>
    main()
    ~~~~^^
  File "H:\Pyt\fssaver\fss_save.py", line 245, in main
    create_file_structure(start_path, no_update_md5=no_update_md5, recursion=recursion, retries=retries, retries_pause=retries_pause)
    ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "H:\Pyt\fssaver\fss_save.py", line 183, in create_file_structure
    create_file_structure(dir_path, no_update_md5=no_update_md5, recursion=recursion,
    ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        retries=retries, retries_pause=retries_pause)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "H:\Pyt\fssaver\fss_save.py", line 183, in create_file_structure
    create_file_structure(dir_path, no_update_md5=no_update_md5, recursion=recursion,
    ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        retries=retries, retries_pause=retries_pause)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "H:\Pyt\fssaver\fss_save.py", line 136, in create_file_structure
    for item in dir_path.iterdir():
                ~~~~~~~~~~~~~~~~^^
  File "C:\Program Files\Python313\Lib\pathlib\_local.py", line 575, in iterdir
    with os.scandir(root_dir) as scandir_it:
         ~~~~~~~~~~^^^^^^^^^^
FileNotFoundError: [WinError 3] The system cannot find the path specified: 'q:\\Me\\2022\\2023'


# hidden = read only

не может писать в файлы с флагом hidden под windows. (WTF??)

# KeyError: 'type'

```
WARN: folder not found:  H:\System Volume Information\.index_hash.yaml
Traceback (most recent call last):
  File "H:\Pyt\my_utils\PySync\fs_struct_merge_to_once_yaml.py", line 83, in <module>
    main()
  File "H:\Pyt\my_utils\PySync\fs_struct_merge_to_once_yaml.py", line 58, in main
    merged_structure = merge_contents(start_directory / g_yaml_name, retries, retries_pause)
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "H:\Pyt\my_utils\PySync\fs_struct_merge_to_once_yaml.py", line 43, in merge_contents
    recursion_indexes = merge_contents(Path(path_to_index_hash).parent / file_name / g_yaml_name, retries, retries_pause)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "H:\Pyt\my_utils\PySync\fs_struct_merge_to_once_yaml.py", line 42, in merge_contents
    if file_data['type'] == 'dir' or (file_data['type'] == 'directory'):
       ~~~~~~~~~^^^^^^^^
KeyError: 'type'


```

# [Errno 13] Permission denied 2


```
SAVE NEW: H:\$501CF898640A4859BE86C8EC01B59432\F6D55A26BFB549EBACAAB9576265398C\.index_hash.yaml
add: S-1-5-21-3685602089-3605761628-1792558038-15672
SAVE NEW: H:\$RECYCLE.BIN\.index_hash.yaml
Traceback (most recent call last):
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 207, in <module>
    main()
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 201, in main
    create_file_structure(start_path, recursion=recursion, retries=retries, retries_pause=retries_pause)
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 150, in create_file_structure
    create_file_structure(dir_path, recursion=recursion, retries=retries, retries_pause=retries_pause)
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 142, in create_file_structure
    save_to_yaml(file_structure, yaml_path)
  File "H:\Pyt\my_utils\PySync\fs_struct_utils.py", line 19, in save_to_yaml
    with open(output_file, 'w', encoding=encoding) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 13] Permission denied: 'H:\\$RECYCLE.BIN\\.index_hash.yaml'
```

# [Errno 13] Permission denied

```
add: ----.jpg
Traceback (most recent call last):
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 199, in <module>
    main()
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 193, in main
    create_file_structure(start_path)
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 147, in create_file_structure
    create_file_structure(dir_path)
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 147, in create_file_structure
    create_file_structure(dir_path)
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 124, in create_file_structure
    file_structure[item.name] = update_record({}, item)
                                ^^^^^^^^^^^^^^^^^^^^^^^
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 68, in update_record
    r['md5'] = calculate_md5(data)
               ^^^^^^^^^^^^^^^^^^^
  File "H:\Pyt\my_utils\PySync\fs_struct_to_yaml.py", line 153, in calculate_md5
    with open(file_path, "rb") as f:
         ^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 13] Permission denied: '----.jpg'

H:\Pyt\my_utils\PySync>python fs_struct_to_yaml.py q:\
ERROR: I/O error(13): Permission denied
```

