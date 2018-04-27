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



## Installation

### Snap package

`md2pdf-webserver` is available as an Ubuntu Snap package. This has two main benefits: 

1. All dependencies are automatically included, making `md2pdf` independent of your system setup. This is important, because TeX in particular can be very picky about how it is configured, and to have consistent PDF output it helps to reduce changes to TeX's environment. 
2. `md2pdf-webserver` is isolated and confined with AppArmor. Especially during early stages of development (this is still a beta grade product), having the environment confined from the rest of the system should reduce the risk of exploits. 

Currently, it is only available for the `x86_64` architecture. `armhf` support is planned but not available yet. 

To install the Snap package, the command is simply: 

```
sudo snap install --beta md2pdf-webserver
```

The `--beta` flag will install a testing version of the application - it has not been release to stable yet. 

Of course this will only work on systems that support Snappy, i.e. any recent Ubuntu version, as well as other Linuxes - [see here](https://docs.snapcraft.io/core/install) for more information. 

### Manual install

If not installing the Snap package, various dependencies will need to be
installed.

**TO DO**

Once dependencies are in place, it can be run as a Python script:

```
python3 md2pdf_webserver.py --run
```

## Setting up

### Installing LaTeX

After installing the `md2pdf-webserver` package (either as a Snap, or manually), you will need to run the LaTeX installer. This will download the latest TeX Live distribution and configure a chroot environment for it to run in. By using a chroot, the TeX Live setup can remain unchanged, and even be backed-up and copied between servers, preserving the exact configuration - which should result in consistent PDF output. 

Note that installing TeX Live will download around 800 MB, which may take quite some time. You will only have to do this once - updates to `md2pdf-webserver` will use the same chroot for LaTeX. 

```
$ sudo md2pdf-webserver --install

DEBUG  : Setting chroot path to '/var/snap/md2pdf-webserver/common/texlive-chroot'
DEBUG  : Setting temp path to '/var/snap/md2pdf-webserver/common/texlive-chroot/tmp'
DEBUG  : Successfully read config from file at '/var/snap/md2pdf-webserver/common/md2pdf_webserver_config.yaml'
INFO   : Will install TeX Live into '/var/snap/md2pdf-webserver/common/texlive-chroot', using latest installer from CTAN
Setting up chroot in /var/snap/md2pdf-webserver/common/texlive-chroot
SNAP_NAME is 'md2pdf-webserver'
Creating basic folder structure
Copying binaries and libraries

...

Installing TeX Live 2017 from: http://mirror.aarnet.edu.au/pub/CTAN/systems/texlive/tlnet (verified)
Platform: x86_64-linux => 'GNU/Linux on x86_64'
Distribution: net  (downloading)
Using URL: http://mirror.aarnet.edu.au/pub/CTAN/systems/texlive/tlnet
Directory for temporary files: /tmp/IKO3xZJxEo
Installing to: /usr/local/texlive
Installing [0001/1095, time/total: ??:??/??:??]: 12many [3k]
Installing [0002/1095, time/total: 00:00/00:00]: FAQ-en [1k]
Installing [0003/1095, time/total: 00:01/19:51:53]: MemoirChapStyles [1k]
Installing [0004/1095, time/total: 00:01/16:09:09]: SIstyle [4k]
Installing [0005/1095, time/total: 00:01/07:40:38]: SIunits [6k]

...

```

**TIP:** If you are installing `md2pdf-webserver` on a headless server machine, or a VM, you may find that it hangs for quite a while at the point of "Setting up a small amount of entropy". This is reading from `/dev/random`, to provide a small amount of entropy for any cryptographic operations needed in the chroot (because the chroot can't access the 'real' `/dev/random`). If it is taking too long, try opening several other SSH connections to the machine and doing various tasks that generate disk access. Or, take a look at [setting up `rng-tools`](https://linux.die.net/man/8/rngd). 


### Configuration file

After installation, you can see some helpful information with the `--check` flag: 

```
$ sudo md2pdf-webserver --check

DEBUG  : Setting chroot path to '/var/snap/md2pdf-webserver/common/texlive-chroot'
DEBUG  : Setting temp path to '/var/snap/md2pdf-webserver/common/texlive-chroot/tmp'
INFO   : Did not find example static file /var/snap/md2pdf-webserver/common/static/example.latex, will copy it from /snap/md2pdf-webserver/3/snap/example-static/example.latex
INFO   : Did not find example static file /var/snap/md2pdf-webserver/common/static/gear.eps, will copy it from /snap/md2pdf-webserver/3/snap/example-static/gear.eps
INFO   : Did not find example static file /var/snap/md2pdf-webserver/common/static/building.eps, will copy it from /snap/md2pdf-webserver/3/snap/example-static/building.eps
WARNING: Config file not found at '/var/snap/md2pdf-webserver/common/md2pdf_webserver_config.yaml', will create one with defaults
DEBUG  : Successfully read config from file at '/var/snap/md2pdf-webserver/common/md2pdf_webserver_config.yaml'
INFO   : Config file is located at: /var/snap/md2pdf-webserver/common/md2pdf_webserver_config.yaml
INFO   : Config options loaded from file: 
listen_address: 127.0.0.1
default_template: example.latex
listen_port: 9090
static_content:
- example.latex
- gear.eps
- building.eps
INFO   : Static files can either be absolute paths, or relative to '/var/snap/md2pdf-webserver/common/static'
```

Here we can see that `md2pdf-webserver` could not find any configuration file, and so it has created a new one with defaults. It also comes with some default static files, which are used in creating PDFs. 

`md2pdf-webserver` uses a YAML file for storing configuration. From the `--check` command, the path of the file can be discovered, i.e. `Successfully read config from file at '/var/snap/md2pdf-webserver/common/md2pdf_webserver_config.yaml'` Using your preferred editor, edit this file as desired. In particular, the default is to only listen on the loopback interface - unless you are using something like nginx or Apache to proxy to `md2pdf-webserver`, you will likely want to change this to `0.0.0.0` to listen on any interface and allow clients over the network. 

**Note:** `md2pdf-webserver` does not provide any kind of access control - if you don't want just anyone to generate PDFs on your server, you'll need to configure an external firewall accordingly. This is highly recommended, or else it could be fairly easy to launch a Denial-of-Service attack against your server by causing it to generate lots and lots of PDF files. 

### Starting the server

For now, while still heavily in development, the server must be started and run manually. In the future this will become an automatic starting service. 

Start the server with: 

```
$ sudo md2pdf-webserver --run

DEBUG  : Setting chroot path to '/var/snap/md2pdf-webserver/common/texlive-chroot'
DEBUG  : Setting temp path to '/var/snap/md2pdf-webserver/common/texlive-chroot/tmp'
DEBUG  : Successfully read config from file at '/var/snap/md2pdf-webserver/common/md2pdf_webserver_config.yaml'
INFO   : [24/Apr/2018:23:21:32] ENGINE Listening for SIGTERM.
INFO   : [24/Apr/2018:23:21:32] ENGINE Listening for SIGHUP.
INFO   : [24/Apr/2018:23:21:32] ENGINE Listening for SIGUSR1.
INFO   : [24/Apr/2018:23:21:32] ENGINE Bus STARTING
INFO   : [24/Apr/2018:23:21:32] ENGINE Started monitor thread 'Autoreloader'.
INFO   : [24/Apr/2018:23:21:32] ENGINE Serving on http://0.0.0.0:9090
INFO   : [24/Apr/2018:23:21:32] ENGINE Bus STARTED
```

The process will run in the foreground. 

### Connecting

If the installation has gone well, the listen address has been changed to `0.0.0.0`, and the server is running; clients with `md2pdf-client` should now be able to connect and generate PDFs. They will need to run the command `md2pdf-client --set-default server <hostname or ip>:9090` to set the correct endpoint - and then they can simply "Open With" on a Markdown file and select "md2pdf Client". 

## License

This project is released under the terms of the GNU Affero GPL version 3 (or
later). Please see [LICENSE](LICENSE) for details.

## Thanks

The base of my (very crappy) icon is from the standard [GNOME icons](https://commons.wikimedia.org/wiki/GNOME_Desktop_icons). These are GPL licensed.
