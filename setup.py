#! /usr/bin/env python3
from setuptools import setup
import re

package_name = 'md2pdf_webserver'
filename = package_name + '.py'

def get_version():
    with open(filename) as f:
        for line in f:
            version = re.search("__version__\s?=\s?\"(\d+\.\d+\.\d+)\"", line)
            if version:
                return version.group(1)

    # Return 0.0.0 if version not found
    return label.replace("0.0.0")


def get_long_description():
    try:
        with open('README.md', 'r') as f:
            return f.read()
    except IOError:
        return ''


setup(
    name=package_name,
    version=get_version(),
    author='Sean Lanigan',
    author_email='sean.lanigan@exteltechnologies.com',
    description='md2pdf server package, to render Markdown text from clients into a pretty PDF',
    url='https://github.com/seanlano/md2pdf-webserver',
    long_description='''
md2pdf is a little project that aims to make it easy to produce
professional-looking PDF documents from Markdown files via a LaTeX template and
the help of Pandoc.

With with an appropriate template, LaTeX PDF output is undeniably the prettiest-
looking way to create documents. But, learning LaTeX is hard. Markdown
is much easier to use, and when used with Pandoc can still produce superb PDF
documents. md2pdf makes it simple to manage having the right LaTeX templates and
configuration across a whole team, by using a central server to do the PDF
generation and then share the result with those who need it.

This is the server application - it might take some substatial configuration \
to get running correctly. See https://github.com/seanlano/md2pdf-webserver \
for more information.
        ''',
    py_modules=[package_name],
    entry_points={
        'console_scripts': [
            'md2pdf_webserver = md2pdf_webserver:main'
        ]
    },
    include_package_data=True,
    license='GNU Affero General Public License v3 or later',
)
