
# Introduction
This reporsitory provides the source code for building and benchmarking various sanitizers as an extension of the [instrumentation infrastructure](https://github.com/vusec/instrumentation-infra) framework.

# Dependencies
The infrastructure is dependent on Python 3.6 (or higher). On a clean Ubuntu 18.04 installation, this is what you need:

```
$ sudo apt-get install bison build-essential gettext git pkg-config python ssh subversion
```

For python the following package is needed:
```
$ pip3 install psutil
```

For nicer command-line usage, install the following python packages (optional):
```
$ pip3 install --user coloredlogs argcomplete
```

argcomplete enables command-line argument completion, but it needs to be activated first (optional):
```
$ eval "$(register-python-argcomplete --complete-arguments -o nospace -o default -- setup.py)"
```

# Usage
To use this repository, first you need to clone the instrumentation infrastructure:

```
git submodule add -b master git@github.com:vusec/instrumentation-infra.git infra
```

The infrastructure supports multiple benchmarking suites, like SPEC CPU2006/2017, Nginx, ApacheHttpd, Lighttpd, Juliet. For additional information on how to use them see the [documentation](https://instrumentation-infra.readthedocs.io/en/master/targets.html).

For example, to run SPEC-CPU2006, you will need to provide your own copy of the source. After configuring the `setup.py`, you can build and run the benchmark suite as follows:

```
$ ./setup.py run --build spec2006 <sanitizer_name>
```

For a complete list of run options, consult:
```
$ ./setup.py run --help
$ ./setup.py run spec2006 --help
```