import os
from zipfile import ZipFile

def zip_file_list(root_path, zip_filename, file_list=[]):
    out_zip_file = os.path.join(root_path, zip_filename)
    zip_obj = ZipFile(out_zip_file, 'w')
    for file in file_list:
        filename = os.path.join(root_path, file)
        acrname = os.path.relpath(filename, start=root_path)
        zip_obj.write(filename, acrname)
    zip_obj.close()
    return out_zip_file

def zip_files(root_path, out_file, selected=[]):
    obj = ZipFile(out_file, "w")
    # change /xxx/ to /xxx or xxx to /xxx and pop ''
    for i in range(len(selected)):
        if not selected[i]:
            selected.pop(i)
            continue

        selected[i] = selected[i].strip()
        if selected[i].endswith('/'):
            selected[i] = selected[i][:-1]
        if not selected[i].startswith('/'):
            selected[i] = '/{}'.format(selected[i])

    for root, dirs, files in os.walk(root_path):
        for item in files:
            filename = os.path.join(root, item)
            arcname = filename.replace(root_path,'')
            if not is_selected(arcname, selected):
                continue

            obj.write(filename, arcname)
    if not obj.filelist:
        return

    obj.close()


def is_selected(arcname, selected):
    if not selected:
        return True

    arcdir = os.path.dirname(arcname)
    for s in selected:
        if arcname == s:
            return True

        if arcdir == s:
            return True

        if arcname.startswith(s + '/'):
            return True

    return False


def unzip_file(zip_file, out_dir='./'):
    obj = ZipFile(zip_file, "r")
    for item in obj.namelist():
        obj.extract(item, out_dir)