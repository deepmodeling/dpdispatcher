import os, glob
from posixpath import realpath
from zipfile import ZipFile
import shutil

# def zip_file_list(root_path, zip_filename, file_list=[]):
#     shutil.make_archive(base_name=zip_filename,
#         root_dir=root_path,)

def zip_file_list(root_path, zip_filename, file_list=[]):
    out_zip_file = os.path.join(root_path, zip_filename)
    # print('debug: file_list', file_list)
    zip_obj = ZipFile(out_zip_file, 'w')
    for f in file_list:
        matched_files = os.path.join(root_path, f)
        for ii in glob.glob(matched_files):
            # print('debug: matched_files:ii', ii)
            if os.path.isdir(ii):
                arcname = os.path.relpath(ii, start=root_path)
                zip_obj.write(ii, arcname)
                for root, dirs, files in os.walk(ii):
                    for file in files:
                        filename = os.path.join(root, file)
                        arcname = os.path.relpath(filename, start=root_path)
                        # print('debug: filename:arcname:root_path', filename, arcname, root_path)
                        zip_obj.write(filename, arcname)
            else:
                arcname = os.path.relpath(ii, start=root_path)
                zip_obj.write(ii, arcname)
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
