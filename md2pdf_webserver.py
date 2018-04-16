#!/usr/bin/env python3
'''
md2pdf_webserver: A web service for rendering Markdown files sent from a client
application into a PDF via a Pandoc and LaTeX.
Copyright (C) 2018  Sean Lanigan, Extel Technologies
https://github.com/seanlano/md2pdf-webserver

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

global __version__
__version__ = "0.0.1"


import argparse
import os
import stat
import shutil
import sys
import cherrypy
import string
import random
import hashlib
import logging
import threading
import time
import zipfile
import subprocess
from ruamel.yaml import YAML

yaml = YAML()

## TODO:
#   - Spruce up index.html

# Dependencies (Ubuntu 16.04 packages):
#   - librsvg2-bin
#   - texlive-base
#   - texlive-extra-utils
#   - texlive-generic-extra
# Tested and working with Pandoc 2.1.2 and Pandoc-crossref 0.3.0.1

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)-7s: %(message)s'
                    )

def main():
    ## Declare some global vars
    global def_tempdir
    global def_latex_static
    global def_template
    global config_dict
    config_dict = {}
    global static_path
    global launch_path
    global chroot_path
    global running_as_snap


    ## Define the mapping between command line options and config file syntax
    config_dict["listen"] = "listen_address"
    config_dict["tempdir"] = "temp_path"
    config_dict["port"] = "listen_port"


    ## Hard-coded defaults, used if no config file exists
    def_port = 9090
    def_listen = "127.0.0.1"
    def_tempdir = "/tmp"
    def_latex_static = (
            "example.latex",
            "gear.eps",
            "building.eps"
            )
    def_template = "example.latex"


    ## Check if the process is being run as root - there will likely be issues if not
    if os.geteuid() is not 0:
        logging.error("You don't seem to be running as root - try with sudo if this fails")

    ## Store the original directory
    launch_path = os.getcwd()

    ## Read the config file, or create it if it doesn't exist
    # Try and see if we are running as an Ubuntu Snap package
    config_name = "md2pdf_webserver_config.yaml"
    running_as_snap = False
    try:
        config_path = os.environ["SNAP_COMMON"]
        chroot_path = os.path.join(config_path, "texlive-chroot")
        config_path = os.path.join(config_path, config_name)
        running_as_snap = True
    except (KeyError):
        # This would fail on a 'normal' Linux install, so use /usr instead
        config_path = "/usr/local/share"
        chroot_path = os.path.join(config_path, "texlive-chroot")
        config_path = os.path.join(config_path, config_name)

    # If running as a Snap, check the static content has been copied in place
    if running_as_snap:
        install_path = os.environ["SNAP"]
        install_path = os.path.join(install_path, "snap")
        install_path = os.path.join(install_path, "example-static")
        for static in def_latex_static:
            static_path = os.environ["SNAP_COMMON"]
            static_path = os.path.join(static_path, "static")
            static_path = os.path.join(static_path, static)
            if not os.path.isfile(static_path):
                copy_from = os.path.join(install_path, static)
                logging.info("Did not find example static file %s, will copy it from %s", static_path, copy_from)
                os.makedirs(os.path.dirname(static_path), exist_ok=True)
                shutil.copy(copy_from, static_path)

    ## Define the relative path for static content
    try:
        static_path = os.environ["SNAP_COMMON"]
        static_path = os.path.join(static_path, "static")
    except (KeyError):
        # This would fail on a 'normal' Linux install, so use /usr instead
        static_path = "/usr/local/share/md2pdf_static"

    # Try to open the file, if it exists
    have_config = False
    try:
        config_file = open(config_path, 'rt', encoding="utf-8")
        have_config = True
    except (FileNotFoundError):
        logging.warning("Config file not found at '%s', will create one with defaults", config_path)

    if not have_config:
        # Create a file with default values in it
        config_file = open(config_path, 'wt', encoding="utf-8")
        conf = {}
        conf[config_dict["port"]] = def_port
        conf[config_dict["listen"]] = def_listen
        conf[config_dict["tempdir"]] = def_tempdir
        conf["static_content"] = def_latex_static
        conf["default_template"] = def_template

        yaml.dump(conf, config_file)
        # Write out the file, then read from it again
        config_file.close()
        config_file = open(config_path, 'rt', encoding="utf-8")

    # Read from the config file
    conf = yaml.load(config_file)
    try:
        def_port = int(conf[config_dict["port"]])
        def_listen = conf[config_dict["listen"]]
        def_tempdir = conf[config_dict["tempdir"]]
        def_latex_static = conf["static_content"]
        def_template = conf["default_template"]
    except KeyError as e:
        logging.critical("Config item %s could not be read from config file at '%s'", e, config_path)
        sys.exit()

    logging.debug("Successfully read config from file at '%s'", config_path)
    config_file.close()


    ## Parse the command-line arguments
    parser = argparse.ArgumentParser(description='md2pdf webserver - A web service for rendering Markdown files into a PDF via Pandoc and LaTeX')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run', action="store_true", help="Start the web service (will continue running in the foreground). Can be combined with other options, or will use stored default values")
    group.add_argument('--check', action="store_true", help="Prints out the location of the config file, and parses and validates it if it exists")
    group.add_argument('--install', action="store_true", help="Performs the initial installation of TeX Live, using the latest CTAN installer")
    parser.add_argument('-p', '--port', metavar="PORT", type=int, help="Port to listen on (overrides value set in config file)", default=def_port)
    parser.add_argument('-l', '--listen', metavar="ADDRESS", help="Local IP address to listen on (overrides value set in config file)", default=def_listen)
    parser.add_argument('-t', '--tempdir', metavar="DIRECTORY", help="Temporary directory to use for storing received and rendered files (overrides value set in config file)", default=def_tempdir)

    args = parser.parse_args()


    if args.run:
        ## Check that static content files are available
        static_content_error = False
        for content in def_latex_static:
            static_file = os.path.join(static_path, content)
            path_valid = False
            if not os.path.isfile(static_file):
                static_content_error = True
                logging.error("Static content '%s' was not found in '%s', this might cause Pandoc to fail", content, static_path)
        if static_content_error and running_as_snap:
            logging.error("Note that md2md2pdf_webserver is running as a Snap package - it might be confined and unable to access absolute paths")

        ## Start the CherryPy server
        def_listen = args.listen
        def_port = args.port
        cherry_config = {
            'global' : {
                'server.socket_host' : def_listen,
                'server.socket_port' : def_port,
                'server.thread_pool' : 16,
                'server.max_request_body_size' : 0,
                'server.socket_timeout' : 60,
                'log.screen': False
            }
        }
        def_tempdir = args.tempdir
        cherrypy.quickstart(App(), '/', cherry_config)
    elif args.check:
        ## Parse and validate config options
        logging.info("Config file is located at: %s", config_path)
        logging.info("Config options loaded from file: ")
        yaml.dump(conf, sys.stdout)
        logging.info("Static files can either be absolute paths, or relative to '%s'", static_path)
        sys.exit()
    elif args.install:
        ## Install TeX Live into a chroot
        logging.info("Will install TeX Live into '%s', using latest installer from CTAN", chroot_path)

        # TODO: Prompt and remove existing installation

        os.makedirs(chroot_path, exist_ok=True)
        os.chdir(chroot_path)
        make_dirs = {"bin", "usr", "dev", "etc", "lib", "tmp", "usr/bin", "usr/sbin", "usr/share", "usr/lib", "usr/local", "usr/local/bin"}
        for make_dir in make_dirs:
            os.makedirs(make_dir, exist_ok=True)
        os.chmod("tmp", stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)

        # Copy binaries from /usr/bin
        usr_bin_dir_copies = {"wget", "uniq", "sort", "tty", "env", "gpg2", "objdump", "locale", "clear", "tr", "basename", "dirname", "fc-cache", "fc-cat", "fc-list", "fc-match", "fc-pattern", "fc-query", "fc-scan", "fc-validate", "perl"}
        if running_as_snap:
            usr_bin_dir = os.environ["SNAP"]
            usr_bin_dir = os.path.join(usr_bin_dir, "usr/bin")
        else:
            usr_bin_dir = "/usr/bin"
        dest = os.path.join(chroot_path, "usr/bin")
        for copy in usr_bin_dir_copies:
            shutil.copy2(os.path.join(usr_bin_dir, copy), dest)

        # Copy binaries from /bin
        bin_dir_copies = {"cp", "tar", "bunzip2", "bzcat", "bzip2", "cat", "chgrp", "chmod", "chown", "dash", "date", "dd", "df", "dir", "echo", "egrep", "false", "fgrep", "grep", "gunzip", "gzip", "hostname", "kill", "ln", "ls", "mkdir", "mknod", "mktemp", "mv", "rm", "rmdir", "sed", "sh", "sleep", "stty", "sync", "touch", "true", "uname", "vdir"}
        if running_as_snap:
            bin_dir = os.environ["SNAP"]
            bin_dir = os.path.join(bin_dir, "bin")
        else:
            bin_dir = "/bin"
        dest = os.path.join(chroot_path, "bin")
        for copy in bin_dir_copies:
            shutil.copy2(os.path.join(bin_dir, copy), dest)


    else:
        # Should not be able to get here
        logging.critical("Did not receive a command line flag")
        sys.exit()

# END main()


class DeleteTimerThread(threading.Thread):
    def __init__(self, folder):
        # Initialise the threading.Thread parent
        super().__init__()
        # Store the passed objects
        self.folder = folder

    def run(self):
        # Delete the folder after a 2 minute wait, to save disk space
        logging.debug("Will remove '%s' in 2 minutes", self.folder)
        time.sleep(120)
        logging.info("Removing folder '%s'", self.folder)
        try:
            shutil.rmtree(self.folder)
        except Exception as e:
            logging.error("An error occurred while removing '%s': %s", self.folder, e)


class PdfWorkerThread(threading.Thread):
    def __init__(self, md, template):
        # Initialise the threading.Thread parent
        super().__init__()
        # Store the passed objects
        self.md_file = md
        self.latex_template = template

    def run(self):
        basename = os.path.basename(self.md_file)
        dirname = os.path.dirname(self.md_file)
        arg = "pandoc --filter pandoc-crossref --pdf-engine=xelatex --template="
        arg += self.latex_template
        arg += " -M figPrefix=Figure -M tblPrefix=Table -M secPrefix=Section -M autoSectionLabels=true --highlight-style=tango '"
        arg += basename
        arg += "' -o '"
        arg += basename.replace("md", "pdf") + "'"

        logging.debug(arg)

        os.chdir(dirname)

        # Open a log file for the subprocess call
        with open(basename.replace("md", "log"), 'wt', encoding="utf-8") as log_file:
            # Run the shell call, and wait for it to end
            p = subprocess.Popen(arg, shell=True, stdout=log_file, stderr=log_file)
            p.wait()

        # Spawn a new thread, which will delete the folder after 2 minutes
        thread = DeleteTimerThread(dirname)
        thread.start()


class App:
    @cherrypy.expose
    def index(self):
        # cd back to the launch path, in case cwd has been set elsewhere
        os.chdir(launch_path)
        return open('index.html')

    @cherrypy.expose
    def style(self):
        # cd back to the launch path, in case cwd has been set elsewhere
        os.chdir(launch_path)
        return open('style.css')

    @cherrypy.expose
    def upload(self, ufile):
        # cd back to the launch path, in case cwd has been set elsewhere
        os.chdir(launch_path)

        upload_path = os.path.normpath(def_tempdir)
        upload_rand_name = ''.join(random.sample(string.hexdigits, 16))
        upload_file = os.path.join(upload_path, upload_rand_name)
        size = 0

        ## Check that the client has set the "x-method" header
        x_method = cherrypy.request.headers.get('x-method')
        good_req = False
        if isinstance(x_method, str):
            if x_method == "MD-to-PDF":
                good_req = True
        if not good_req:
            raise cherrypy.HTTPError(405, "This server only supports Markdown to PDF rendering, please check your request")

        ## Check if the client has set the 'template' header
        try:
            x_template = cherrypy.request.headers.get('x-latex-template')
        except:
            pass
        if isinstance(x_template, str):
            template = x_template
        else:
            template = def_template

        ## Accept the upload file and write it to disk with a temporary name
        with open(upload_file, 'wb') as out:
            while True:
                data = ufile.file.read(8192)
                if not data:
                    break
                out.write(data)
                size += len(data)

        ## Calculate the SHA256 hash of the file, to use as a reference
        try:
            input_hash = hashlib.new('sha256')
            with open(upload_file, 'rb') as input_file:
                buf = input_file.read()
                input_hash.update(buf)
            logging.debug("Hash for file '%s' is %s", upload_file, input_hash.hexdigest())

            new_name = os.path.join(upload_path, (input_hash.hexdigest() + ".zip"))
            os.rename(upload_file, new_name)
        except:
            logging.critical("File '%s' could not be processed", full_path)
            raise cherrypy.HTTPError(500)

        ## Move the temporary file to use the SHA256 hash as a filename
        path_exists = False
        try:
            output_path = os.path.join(upload_path, input_hash.hexdigest())
            os.mkdir(output_path)
        except(FileExistsError):
            logging.info("Path already exists: %s", output_path)
            path_exists = True

        report_string = ""
        ## Extract the ZIP archive into a temporary folder
        if not path_exists:
            try:
                in_zip = zipfile.ZipFile(new_name, 'r')
                in_zip.extractall(output_path)
            except Exception as e:
                logging.error("Error in zip extraction: %s", e)

            ## Make symbolic links to required static content for PDF creation
            for static in def_latex_static:
                logging.debug("Making copy of static content '%s'", static)
                try:
                    # First try static content as a relative path
                    static_file = os.path.join(static_path, static)
                    path_valid = False
                    if os.path.isfile(static_file):
                        path_valid = True
                    else:
                        # If not, try it as an absolute path
                        logging.debug("File '%s' does not seem to be a relative path, trying as absolute", static_file)
                        static_file = static
                        if os.path.isfile(static_file):
                            path_valid = True
                    if not path_valid:
                        logging.critical("Static file '%s' is not accessible")
                    else:
                        shutil.copy(static_file, output_path)

                except Exception as e:
                    logging.critical("Unable to make link for file: %s. Error: ", static, e.msg)

            ## Delete any existing PDF and log files
            for file in os.listdir(output_path):
                if file.endswith(".log") or file.endswith(".pdf"):
                    del_path = os.path.join(output_path, file)
                    logging.info("Deleting file: %s", del_path)
                    os.remove(del_path)

            report_string = "File is being processed into a PDF, request it using the hash value"
        else:
            report_string = "File has already been submitted, request the PDF using the hash value"

        ## Look for a MarkDown file in the extracted directory, and spawn a subprocess to render it
        md_path = False
        for file in os.listdir(output_path):
            if file.endswith(".md"):
                md_path = os.path.join(output_path, file)
                logging.info("Found MD file: %s", md_path)
                break
        if md_path:
            md_basename = os.path.basename(md_path)
            logging.debug("Basename is '%s'", md_basename)
            # Spawn PdfWorkerThread with necessary options
            thread = PdfWorkerThread(md=md_path, template=template)
            thread.start()
        else:
            report_string = "MD file not found in submitted archive"

        ## Put the hash value in a cookie to send back to the client
        cookie = cherrypy.response.cookie
        cookie['hashsum'] = input_hash.hexdigest()
        ## Create a short message to send back to the client
        out = '''
File received
length: {}
filename: {}
hash: {}
{}
''' .format(size, ufile.filename, input_hash.hexdigest(), report_string, data)
        ## Finally, actually send the response
        return out


    ## Provide a handler for fetching a compiled PDF
    @cherrypy.expose
    def fetch(self, hashsum=""):
        # cd back to the launch path, in case cwd has been set elsewhere
        os.chdir(launch_path)

        req_path = os.path.join(def_tempdir, hashsum)

        # By default, assume the PDF was not found
        pdf_path = False
        # Attempt to find a PDF for the given hash
        try:
            for file in os.listdir(req_path):
                if file.endswith(".pdf"):
                    pdf_path = os.path.join(req_path, file)
                    logging.info("Found PDF file: %s", pdf_path)
        except(FileNotFoundError):
            # Raise a 404 error if we cannot find the given path
            logging.critical("File not found for hash: %s", hashsum)
            raise cherrypy.HTTPError(404, ("No file was found for the given hashsum: " + hashsum))
        except Exception as e:
            # Raise a 500 error if any other exception occurs
            logging.critical("Other error: %s", e.msg)
            raise cherrypy.HTTPError(500)

        # If we have found the PDF, serve it to the client
        if pdf_path:
            return cherrypy.lib.static.serve_file(pdf_path, disposition='attachment', name=os.path.basename(pdf_path))
        # If we did not find it, try to serve the error log instead
        else:
            try:
                err_path = False
                for file in os.listdir(req_path):
                    if file.endswith(".log"):
                        err_path = os.path.join(req_path, file)
                        logging.info("Found error logfile: %s", err_path)
            except Exception as e:
                # Raise a 500 error if something unknown goes wrong
                logging.critical("Other error: %s", e.msg)
                raise cherrypy.HTTPError(500)

            if err_path:
                return cherrypy.lib.static.serve_file(err_path, disposition='attachment', name=os.path.basename(err_path))

        # If we get to this point, we could not find a PDF or an error log
        raise cherrypy.HTTPError(404, ("No file was found for the given hashsum: " + hashsum))


if __name__ == '__main__':
    main()
