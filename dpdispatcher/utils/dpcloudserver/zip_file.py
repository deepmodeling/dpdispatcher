"""Create and extract ZIP archives for cloud file transfer."""

from collections.abc import Iterable
from zipfile import ZipFile

from dpdispatcher.file_manager import ArchiveBuilder
from dpdispatcher.utils.archive import safe_extract_zip

# def zip_file_list(root_path, zip_filename, file_list=[]):
#     shutil.make_archive(base_name=zip_filename,
#         root_dir=root_path,)


def zip_file_list(
    root_path: str,
    zip_filename: str,
    file_list: Iterable[str] | None = None,
) -> str:
    """Create a ZIP archive from paths and glob patterns below a root."""
    patterns = list(file_list) if file_list is not None else []
    return str(ArchiveBuilder(root_path).build_zip(zip_filename, patterns))


# def zip_files(root_path, out_file, selected=[]):
#     obj = ZipFile(out_file, "w")
#     # change /xxx/ to /xxx or xxx to /xxx and pop ''
#     for i in range(len(selected)):
#         if not selected[i]:
#             selected.pop(i)
#             continue

#         selected[i] = selected[i].strip()
#         if selected[i].endswith('/'):
#             selected[i] = selected[i][:-1]
#         if not selected[i].startswith('/'):
#             selected[i] = '/{}'.format(selected[i])

#     for root, dirs, files in os.walk(root_path):
#         for item in files:
#             filename = os.path.join(root, item)
#             arcname = filename.replace(root_path,'')
#             if not is_selected(arcname, selected):
#                 continue

#             obj.write(filename, arcname)
#     if not obj.filelist:
#         return

#     obj.close()


# def is_selected(arcname, selected):
#     if not selected:
#         return True

#     arcdir = os.path.dirname(arcname)
#     for s in selected:
#         if arcname == s:
#             return True

#         if arcdir == s:
#             return True

#         if arcname.startswith(s + '/'):
#             return True

#     return False


def unzip_file(zip_file: str, out_dir: str = "./") -> set[str]:
    """Extract a ZIP archive into a local directory."""
    with ZipFile(zip_file, "r") as obj:
        return safe_extract_zip(obj, out_dir)
