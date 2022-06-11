#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import path
import setuptools, datetime

readme_file = path.join(path.dirname(path.abspath(__file__)), 'README.md')
NAME="dpdispatcher"
SHORT_CMD="dpdisp"

try:
    from m2r import parse_from_file
    readme = parse_from_file(readme_file)
except ImportError:
    with open(readme_file) as f:
        readme = f.read()

today = datetime.date.today().strftime("%b-%d-%Y")
with open(path.join(NAME, '_date.py'), 'w') as fp :
    fp.write('date = \'%s\'' % today)

install_requires=['paramiko', 'dargs>=0.2.9', 'requests', 'tqdm']

setuptools.setup(
    name=NAME,
    use_scm_version={'write_to': 'dpdispatcher/_version.py'},
    setup_requires=['setuptools_scm'],
    author="Deep Modeling",
    author_email="",
    description="Python Dispatcher",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="",
    python_requires="~=3.6",
    packages=['dpdispatcher', 'dpdispatcher/dpcloudserver'],
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
    ],
    keywords='deep potential generator active learning deepmd-kit',
    install_requires=install_requires,    
    extras_require={
        'docs': ['sphinx', 'myst-parser', 'sphinx_rtd_theme>=1.0.0rc1', 'numpydoc', 'deepmodeling_sphinx', 'dargs>=0.3.1'],
        "cloudserver": ["oss2", "tqdm"],
        ":python_version<'3.7'": ["typing_extensions"],
    },
        entry_points={
          'console_scripts': [
              SHORT_CMD+'= dpdispatcher.dpdisp:main']
   }
)
