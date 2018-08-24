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
__version__ = "0.1.0"


import argparse
import os
import stat
import shutil
import sys
import cherrypy
import string
import re
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
# - Spruce up index.html
# - Add command line flag to run tlmgr install / update (for extra TeX packages)
# - Make debug level configurable on the command line
# - ADD DOCUMENTATION!!!!

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
    global compare_replace
    global static_path
    global html_path
    global chroot_path
    global iso_path
    global running_as_snap


    ## Define the mapping between command line options and config file syntax
    config_dict["listen"] = "listen_address"
    config_dict["tempdir"] = "temp_path"
    config_dict["port"] = "listen_port"


    ## Hard-coded defaults, used if no config file exists
    def_port = 9090
    def_listen = "127.0.0.1"
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
    html_path = os.getcwd()

    ## Read the config file, or create it if it doesn't exist
    # Try and see if we are running as an Ubuntu Snap package
    config_name = "md2pdf_webserver_config.yaml"
    running_as_snap = False
    try:
        config_path = os.environ["SNAP_COMMON"]
        chroot_path = os.path.join(config_path, "texlive-chroot")
        iso_path = os.path.join(config_path, "texlive.iso")
        config_path = os.path.join(config_path, config_name)
        html_path = os.environ["SNAP"]
        html_path = os.path.join(html_path, "snap")
        html_path = os.path.join(html_path, "html")
        running_as_snap = True
    except (KeyError):
        # This would fail on a 'normal' Linux install, so use /usr instead
        config_path = "/usr/local/share"
        chroot_path = os.path.join(config_path, "texlive-chroot")
        config_path = os.path.join(config_path, config_name)

    logging.debug("Setting chroot path to '%s'", chroot_path)

    # Use the chroot as the base for the temporary directory
    def_tempdir = os.path.join(chroot_path, "tmp")
    logging.debug("Setting temp path to '%s'", def_tempdir)

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
        def_latex_static = conf["static_content"]
        def_template = conf["default_template"]
    except KeyError as e:
        logging.critical("Config item %s could not be read from config file at '%s'", e, config_path)
        sys.exit()

    # Read the optional "compare_replace" section from the config file
    try:
        compare_replace = conf["compare_replace"]
        logging.debug("Compare-Replace strings loaded")
    except KeyError:
        # No "compare_replace" config exists, this is OK
        compare_replace = False
        logging.debug("Compare-Replace strings not found in config file")

    logging.debug("Successfully read config from file at '%s'", config_path)
    config_file.close()


    ## Parse the command-line arguments
    parser = argparse.ArgumentParser(description='md2pdf webserver v' + __version__ + ' - A web service for rendering Markdown files into a PDF via Pandoc and LaTeX')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run', action="store_true", help="Start the web service (will continue running in the foreground). Can be combined with other options, or will use stored default values")
    group.add_argument('--check', action="store_true", help="Prints out the location of the config file, and parses and validates it if it exists")
    group.add_argument('--install', action="store_true", help="Performs the initial installation of TeX Live, using the latest CTAN installer")
    parser.add_argument('-p', '--port', metavar="PORT", type=int, help="Port to listen on (overrides value set in config file)", default=def_port)
    parser.add_argument('-l', '--listen', metavar="ADDRESS", help="Local IP address to listen on (overrides value set in config file)", default=def_listen)

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

        ## Remove old temporary files
        logging.info("Deleting files in '" + def_tempdir + "'")
        try:
            shutil.rmtree(def_tempdir)
            os.mkdir(def_tempdir)
        except:
            logging.warning("Unable to delete and re-create temporary directory")
            raise

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
        cherrypy.quickstart(App(), '/', cherry_config)
    elif args.check:
        ## Parse and validate config options
        logging.info("Config file is located at: %s", config_path)
        logging.info("Config options loaded from file: ")
        yaml.dump(conf, sys.stdout)
        logging.info("Static files can either be absolute paths, or relative to '%s'", static_path)
        if not(os.path.exists(iso_path)):
            logging.critical("TeX Live ISO installer was not found!")
            logging.critical("Please download the desired TeX Live ISO to '%s'", iso_path)
        sys.exit()

    elif args.install:
        ## Install TeX Live into a chroot
        logging.info("Will install TeX Live into '%s'", chroot_path)

        if(os.path.exists(iso_path)):
            logging.info("Will use TeX Live ISO located at '%s'", iso_path)
        else:
            logging.critical("TeX Live ISO installer was not found!")
            logging.critical("Please download the desired TeX Live ISO to '%s'", iso_path)
            sys.exit()

        try:
            os.makedirs(chroot_path, exist_ok=False)
        except FileExistsError:
            logging.critical("Path '%s' already exists - installer cannot continue.", chroot_path)
            logging.critical("If you want to re-install, first run `sudo rm -rf %s`", chroot_path)
            sys.exit()

        if running_as_snap:
            snap_base = os.environ["SNAP"]
            script_path = os.path.join(snap_base, "snap")
            script_path = os.path.join(script_path, "setup-chroot.sh")
            arg = "./setup-chroot.sh " + snap_base
            logging.info("This installer is running as a Snap. The 'fuse-control' slot needs to be connected.")
            logging.info("If errors mentioning /dev/fuse are seen below, run `sudo snap connect md2pdf-webserver:fuse-support core:fuse-support`")
        else:
            script_path = "setup-chroot.sh"
            arg = "./setup-chroot.sh"

        shutil.copy2(script_path, chroot_path)
        os.chdir(chroot_path)

        p = subprocess.Popen(arg, shell=True)
        p.wait()

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
        # Delete the folder after a 1 minute wait, to save disk space
        logging.debug("Will remove '%s' in one minute", self.folder)
        time.sleep(60)
        logging.info("Removing folder '%s'", self.folder)
        try:
            shutil.rmtree(self.folder)
        except Exception as e:
            logging.error("An error occurred while removing '%s': %s", self.folder, e)


class PdfWorkerThread(threading.Thread):
    def __init__(self, input_md, template, compare_mode=False, compare_md=""):
        # Initialise the threading.Thread parent
        super().__init__()
        # Store the passed objects
        self.md_file = input_md
        self.latex_template = template
        self.compare_mode = compare_mode
        self.compare_md = compare_md

    def run(self):
        # Get the full path of the input MD file
        dirname = os.path.abspath(os.path.dirname(self.md_file))
        # Make the template name safe if it contains spaces
        template_path = self.latex_template
        # Make the MD name safe if it contains spaces
        md_name = os.path.basename(self.md_file)
        # Get the full path to the MD file, inside the chroot
        md_name_full = os.path.join("/", os.path.relpath(self.md_file, chroot_path))

        # Create a temporary shell script, to call inside the chroot
        shell_name = os.path.join(dirname, "pandoc-wrapper.sh")

        # Get the path of the temporary directory inside the chroot
        chroot_tmp = os.path.join("/", os.path.relpath(dirname, chroot_path))

        if self.compare_mode:
            # Write out the special script for doing the latexdiff operation
            # Set up all the filenames
            name_new_md = os.path.basename(self.md_file)
            name_old_md = os.path.basename(self.compare_md)
            name_new_latex = name_new_md.replace("md", "latex")
            name_old_latex = name_old_md.replace("md", "latex")
            name_diff_latex = name_new_latex.replace(".new","_changes")

            # Create the first-stage script
            with open(shell_name, 'wt', encoding="utf-8") as shell_file:
                arg = "pandoc --filter pandoc-crossref --pdf-engine=xelatex --template=\""
                arg += template_path
                arg += "\" -M figPrefix=Figure -M tblPrefix=Table -M secPrefix=Section -M autoSectionLabels=true --highlight-style=tango \""
                arg += name_new_md
                arg += "\" -o \""
                arg += name_new_latex
                arg += "\""

                shell_file.write("#!/bin/sh\n\n")
                shell_file.write("export LC_ALL=C\n")
                shell_file.write("cd " + chroot_tmp + "\n")
                shell_file.write("export PATH=/usr/local/texlive/bin/x86_64-linux:/usr/local/bin:/usr/sbin:/usr/bin:/bin\n\n")
                shell_file.write(arg + "\n")

                # Replace "new" names with "old", and add to the script
                arg = arg.replace(name_new_md, name_old_md)
                arg = arg.replace(name_new_latex, name_old_latex)
                shell_file.write(arg + "\n")

            # Create the second-stage script
            shell_name_2nd = shell_name.replace("pandoc-wrapper", "latex-wrapper")
            with open(shell_name_2nd, 'wt', encoding="utf-8") as shell_file:
                shell_file.write("#!/bin/sh\n\n")
                shell_file.write("export LC_ALL=C\n")
                shell_file.write("cd " + chroot_tmp + "\n")
                shell_file.write("export PATH=/usr/local/texlive/bin/x86_64-linux:/usr/local/bin:/usr/sbin:/usr/bin:/bin\n\n")

                # Add the calls to latexdiff
                shell_file.write("latexdiff -t CULINECHBAR \"" + name_old_latex + "\" \"" + name_new_latex + "\" > \"" + name_diff_latex + "\"\n")

                # Finally, call xelatex to produce the PDF
                shell_file.write("xelatex -interaction=batchmode \"" + name_diff_latex + "\"")

            # Set script to be executable
            os.chmod(shell_name_2nd, 0o744)

        else:
            # Write out the normal script for generating PDF
            with open(shell_name, 'wt', encoding="utf-8") as shell_file:
                arg = "pandoc --filter pandoc-crossref --pdf-engine=xelatex --template=\""
                arg += template_path
                arg += "\" -M figPrefix=Figure -M tblPrefix=Table -M secPrefix=Section -M autoSectionLabels=true --highlight-style=tango \""
                arg += md_name
                arg += "\" -o \""
                arg += md_name.replace("md", "pdf")
                arg += "\""

                shell_file.write("#!/bin/sh\n\n")
                shell_file.write("export LC_ALL=C\n")
                shell_file.write("cd " + chroot_tmp + "\n")
                shell_file.write("export PATH=/usr/local/texlive/bin/x86_64-linux:/usr/local/bin:/usr/sbin:/usr/bin:/bin\n\n")
                shell_file.write(arg + "\n")

        # Set script to be executable
        os.chmod(shell_name, 0o744)

        # Modify shell_name to now be the path inside the chroot
        shell_name = os.path.join("/", os.path.relpath(shell_name, chroot_path))
        logging.debug("Wrapper script path inside chroot is '%s'", shell_name)

        # Create command to call script inside chroot
        arg = "chroot " + chroot_path + " " + shell_name

        # Run compare_replace
        if self.compare_mode:
            logging.info("Running compare_replace on input files")
            name_new_md = os.path.join(dirname, name_new_md)
            name_new_md_tmp = name_new_md + ".tmp"
            name_old_md = os.path.join(dirname, name_old_md)
            name_old_md_tmp = name_old_md + ".tmp"
            os.rename(name_new_md, name_new_md_tmp)
            os.rename(name_old_md, name_old_md_tmp)

            for input_md in (name_new_md_tmp, name_old_md_tmp):
                # Open each file in turn
                with open(input_md, 'rt', encoding="utf-8") as in_file:
                    output_file = ""
                    # Loop over all the lines in the file
                    for line in in_file:
                        output_line = line
                        # For each line, loop through all the replacement pairs
                        for replace_map in compare_replace:
                            for key in replace_map:
                                output_line = output_line.replace(key, replace_map[key])
                        output_file += output_line
                    # Write out the replaced file
                    with open(input_md.replace(".tmp",""), 'w', encoding="utf-8") as out_file:
                        out_file.write(output_file)

        logging.debug("Will execute command: " + arg)

        os.chdir(dirname)

        # Open a log file for the subprocess call
        log_name = md_name_full.replace("md", "log")
        log_name = os.path.join(chroot_path, os.path.relpath(log_name, "/"))
        logging.debug("Writing log file to '%s'", log_name)
        with open(log_name, 'wt', encoding="utf-8") as log_file:
            # Run the shell call, and wait for it to end
            p = subprocess.Popen(arg, shell=True, stdout=log_file, stderr=log_file)
            p.wait()

            # Run the second-stage, if applicable
            if self.compare_mode:
                logging.info("Running hypertarget fix on input files")
                # name_new_latex = os.path.join(dirname, name_new_latex)
                name_new_latex_tmp = name_new_latex + ".tmp"
                # name_old_latex = os.path.join(dirname, name_old_latex)
                name_old_latex_tmp = name_old_latex + ".tmp"
                os.rename(name_new_latex, name_new_latex_tmp)
                os.rename(name_old_latex, name_old_latex_tmp)

                for input_latex in (name_new_latex_tmp, name_old_latex_tmp):
                    # Define regex patterns
                    logging.debug("Running fix on: %s", input_latex)
                    hypertarget_pattern = re.compile("(\\\\hypertarget{.*?}\\s?{%?}?)")
                    label_end_pattern = re.compile("\\\\label{.*?(}\\s?})")
                    # Open each file in turn
                    output_file = ""
                    with open(input_latex, 'rt', encoding="utf-8") as in_file:
                        line_ctr = 0
                        # Loop over all the lines in the file
                        for line in in_file:
                            output_line = line
                            line_ctr += 1
                            # Run "hypertarget" removal, to fix Pandoc LaTeX source
                            match = hypertarget_pattern.search(output_line)
                            if match:
                                # Completely remove the '\hypertarget' line
                                output_line = output_line.replace(match.group(1), "")
                            match = label_end_pattern.search(output_line)
                            if match:
                                # Fix up the extra bracket on the line end
                                output_line = output_line.replace(match.group(1), "}")
                            output_file += output_line
                    # Write out the replaced file
                    output_latex_name = input_latex.replace(".tmp","")
                    with open(output_latex_name, 'w', encoding="utf-8") as out_file:
                        out_file.write(output_file)
                        logging.debug("Wrote out file: %s", output_latex_name)
                # Run the 2nd stage
                arg = arg.replace("pandoc-wrapper", "latex-wrapper")
                p = subprocess.Popen(arg, shell=True, stdout=log_file, stderr=log_file)
                p.wait()

        # Spawn a new thread, which will delete the folder after one minute
        thread = DeleteTimerThread(dirname)
        thread.start()


class App:
    @cherrypy.expose
    def index(self):
        # cd back to the launch path, in case cwd has been set elsewhere
        os.chdir(html_path)
        return open('index.html')

    @cherrypy.expose
    def style(self):
        # cd back to the launch path, in case cwd has been set elsewhere
        os.chdir(html_path)
        return open('style.css')

    @cherrypy.expose
    def upload(self, ufile):
        logging.debug("Using temporary directory '%s'", def_tempdir)
        upload_path = os.path.normpath(def_tempdir)
        upload_rand_name = ''.join(random.sample(string.hexdigits, 16))
        upload_file = os.path.join(upload_path, upload_rand_name)
        logging.debug("Uploading to file '%s'", upload_file)
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

        ## Check if the client has set the 'compare' header
        try:
            x_compare = cherrypy.request.headers.get('x-latex-compare')
        except:
            pass
        if isinstance(x_compare, str):
            logging.info("Upload has requested 'compare mode'")
            compare_mode = True
        else:
            compare_mode = False

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
        md_path_compare = False
        for file in os.listdir(output_path):
            if file.endswith(".md"):
                tmp_path = os.path.join(output_path, file)
                logging.info("Found MD file: %s", tmp_path)
                if compare_mode:
                    if tmp_path.find("old") > -1:
                        # Store the name of the "old" MD file
                        md_path_compare = tmp_path
                    elif tmp_path.find("new") > -1:
                        # Store the name of the "new" MD file
                        md_path = tmp_path
                else:
                    # Stop at the first found MD file in normal mode
                    md_path = tmp_path
                    break
        if md_path:
            md_basename = os.path.basename(md_path)
            logging.debug("Basename is '%s'", md_basename)
            # Spawn PdfWorkerThread with necessary options
            if compare_mode:
                thread = PdfWorkerThread(input_md=md_path, template=template, compare_mode=True, compare_md=md_path_compare)
                thread.start()
            else:
                thread = PdfWorkerThread(input_md=md_path, template=template)
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
