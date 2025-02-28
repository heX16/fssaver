




# About (rus)

File struct saver. `fssaver`. Программа для сохранения структуры файлов в файл.

## Описание

Программа "fssaver" (File Structure Saver) — это набор скриптов для сохранения и управления структурой файловой системы.

**Позволяет:**

- **Сохранять структуру файловой** системы в один "fss-файл", содержащий всю структуру выбранного каталога (и подкаталогов).
- **Сравнивать два "fss-файла"**, и определять добавленные, удалённые, изменённые или перемещённые файлы между двумя структурами.

Такой подход позволяет:

- Отслеживать изменения в файловой системе.
- Синхронизировать данные между разными хранилищами.
- Проверять целостность файлов.
- Выполнять резервное копирование на основе сохранённых структур.

Фичи:

- **кэширование** - программа создаёт "fss-файлы" в каждом каталоге, что ускоряет её работу при повторном запуске.
- **YAML-файлы** - простой формат, удобный для редактирования.
- **простые скрипты** - удобно для изменения работы программы.


## `fss_save.py`
Сохраняет структуру файловой системы в виде YAML-файлов.
Файл с структурой директории, создается в самой директории (в текущей директории).
Программа рекурсивно обходит директории и создает файлы с структурой (в каждой директории по одному файлу).
Имя файлов всегда ".index_hash.yaml".

Также скрипт может обновлять информацию содержащуюся в уже созданных файлах ".index_hash.yaml". Например их хеши и временные метки, или добавлять в структуру новые файлы (или удалять их).

## `fss_merge.py`
Этот скрипт объединяет структуры файлов из различных директорий в один YAML-файл.
Скрипт рекурсивно обходит директории, собирая информацию из файлов ".index_hash.yaml" и сохраняет эту информацию в один большой YAML-файл.

## `fss_compare.py`
Сравнивает две структуры файлов, представленные в виде YAML-файлов.
Скрипт определяет изменения, такие как перемещение, удаление, изменение или добавление файлов, и выводит результаты сравнения.

## `fss_yaml_clean.py`
Этот скрипт удаляет указанные атрибуты из элементов YAML-файла, опционально фильтруя элементы по их типу. Это полезно для очистки данных и удаления ненужной информации из структуры файлов.

## `fss_to_diskdir.py`
Этот скрипт преобразует структуру файлов из YAML-файла в текстовый формат, совместимый с плагинами DiskDir для файловых менеджеров, таких как Double Commander или Total Commander.

## `fss_utils.py`
Этот модуль содержит вспомогательные функции для работы с YAML-файлами, такие как загрузка и сохранение данных, а также другие утилиты для обработки файловой системы. Он используется другими скриптами для унификации и упрощения работы с данными.




# About english

File Structure Saver. `fssaver`. A program for saving file structures to a file.

## `fss_save.py`
Saves the file system structure as YAML files. A file with the directory structure is created in the directory itself (in the current directory). The program recursively traverses directories and creates structure files (one file per directory). The file names are always ".index_hash.yaml".

The script can also update the information contained in the already created ".index_hash.yaml" files, such as their hashes and timestamps, or add new files to the structure (or remove them).

## `fss_merge.py`
This script merges file structures from various directories into a single YAML file. The script recursively traverses directories, collecting information from ".index_hash.yaml" files and saving this information into one large YAML file.

## `fss_compare.py`
Compares two file structures presented as YAML files. The script identifies changes such as moving, deleting, modifying, or adding files and outputs the comparison results.

## `fss_yaml_clean.py`
This script removes specified attributes from elements in a YAML file, optionally filtering elements by their type. This is useful for cleaning data and removing unnecessary information from the file structure.

## `fss_to_diskdir.py`
This script converts the file structure from a YAML file into a text format compatible with DiskDir plugins for file managers like Double Commander or Total Commander.

## `fss_utils.py`
This module contains utility functions for working with YAML files, such as loading and saving data, as well as other utilities for file system processing. It is used by other scripts to unify and simplify data handling.


