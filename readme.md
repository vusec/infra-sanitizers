# Introduction

This repository provides the configuration for building and benchmarking various
sanitizers as an extension of the [instrumentation
infrastructure](https://github.com/vusec/instrumentation-infra) framework. This
includes sanitizers from recent publications, both VUSec and non-VUSec. Using
this allows for easy comparison of a new sanitizers to existing ones. This
repository can be used standalone, or configuration files can be copied over to
another project using the infra, in case you are developing your own sanitizer.

Note that, while we tried our best to build and run the included sanitizers
properly and fairly, some errors may have occurred during the integration into
the framework. In case of any discrepancies, we recommend verifying the observed
behavior with the original release of the sanitizer in question. Additionally,
we encourage opening an issue or submitting a pull request.

# Dependencies

We have verified all included sanitizers work on Ubuntu 18.04. While we try to
include as many dependencies in the framework as possible, issues may occur on
different environments.
The infrastructure is dependent on Python 3.6 (or higher). On a clean Ubuntu
18.04 installation, this is what you need:

```
$ sudo apt-get install bison build-essential gettext git pkg-config python ssh subversion
```

For python the following package is needed in some cases:
```
$ pip3 install psutil
```

For nicer command-line usage, install the following python packages (optional):
```
$ pip3 install --user coloredlogs argcomplete
```

argcomplete enables command-line argument completion, but it needs to be
activated first (optional):
```
$ eval "$(register-python-argcomplete --complete-arguments -o nospace -o default -- setup.py)"
```

# Usage

To use this repository standalone, first you need to clone the instrumentation
infrastructure:

```
$ git submodule add -b master git@github.com:vusec/instrumentation-infra.git infra
```

The infrastructure supports multiple benchmarking suites, like SPEC
CPU2006/2017, Nginx, Apache Httpd, Lighttpd, and Juliet. For additional
information on how to use them see the
[documentation](https://instrumentation-infra.readthedocs.io/en/master/targets.html).

For example, to run SPEC CPU2006, you will need to provide your own copy of the
source. After configuring the `setup.py`, you can build and run the benchmark
suite as follows:

```
$ ./setup.py run --build spec2006 <sanitizer_name>
```

For a complete list of run options, consult:
```
$ ./setup.py run --help
$ ./setup.py run spec2006 --help
```
