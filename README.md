# md2pdf Webserver

![md2pdf icon](icon.svg)

## Introduction

md2pdf is a little project that aims to make it easy to produce
professional-looking PDF documents from Markdown files via a LaTeX template and
the help of Pandoc.

There are several motivations for this:

- Word processor software does not work very nicely with version control, plain-text Markdown files do
- Collaborating on a single ODT/DOC file is prone to overwriting others' work
- LibreOffice and Word both suck with automatic figure and table numbering on long files, and with TOCs etc
- It's painful trying to keep everyone using the right font, spacing, formatting, etc. when collaborating with ODT/DOC files
- PDF output from LibreOffice and Word often looks pretty average
- It's distracting having to worry about formatting while writing - Markdown takes away all but the most basic formatting options to focus you on writing


With an appropriate template, LaTeX PDF output is undeniably the prettiest-
looking way to create documents. But, learning LaTeX is hard. Markdown
is much easier to use, and when used with Pandoc can still produce superb PDF
documents. md2pdf makes it simple to manage having the right LaTeX templates and
configuration across a whole team, by using a central server to do the PDF
generation and then share the result with those who need it.


## Server application

This Python application uses CherryPy to present a REST interface for submitting
Markdown files to, and then requesting rendered PDFs from. It is intended to be
used in conjunction with an `md2pdf-client` application, see
[it's GitHub page](https://github.com/seanlano/md2pdf-client) for more
information.


## Usage

`md2pdf-webserver` is intended to be running on a centralised machine, which
will hold all the relevant LaTeX templates, static images (i.e. company logos
used in title pages and headers/footers), and fonts.

Options are available via the `-h` flag:

```
usage: md2pdf_webserver [-h] (--run | --check | --install) [-p PORT]
                        [-l ADDRESS]

md2pdf webserver v0.0.1 - A web service for rendering Markdown files into a
PDF via Pandoc and LaTeX

optional arguments:
  -h, --help            show this help message and exit
  --run                 Start the web service (will continue running in the
                        foreground). Can be combined with other options, or
                        will use stored default values
  --check               Prints out the location of the config file, and parses
                        and validates it if it exists
  --install             Performs the initial installation of TeX Live, using
                        the latest CTAN installer
  -p PORT, --port PORT  Port to listen on (overrides value set in config file)
  -l ADDRESS, --listen ADDRESS
                        Local IP address to listen on (overrides value set in
                        config file)
```

## Configuration file

`md2pdf-webserver` uses a YAML file for storing configuration. 

**Coming soon**

## Installation

### Snap Package

`md2pdf-webserver` will soon be available as an Ubuntu Snap package, _stay tuned!_

### Dependencies

If not installing the Snap package, various dependencies will need to be
installed.

**Coming soon**

### Direct Python script

Once dependencies are in place, it can be run as a Python script:

```
python3 md2pdf_webserver.py --run
```

## License

This project is released under the terms of the GNU Affero GPL version 3 (or
later). Please see [LICENSE](LICENSE) for details.

## Thanks

The base of my (very crappy) icon is from the standard [GNOME icons](https://commons.wikimedia.org/wiki/GNOME_Desktop_icons). These are GPL licensed.
