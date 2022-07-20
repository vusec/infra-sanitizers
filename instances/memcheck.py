import os
from typing import Optional
import infra
from infra.packages.gnu import AutoConf, AutoMake, Bash, LibTool, M4
from infra.packages.llvm import LLVM
from util import git_fetch


class Valgrind(infra.Package):

    def __init__(self, commit='master'):
        self.commit = commit

    def ident(self):
        return 'valgrind-' + self.commit

    def dependencies(self):
        yield AutoMake('1.15.1', AutoConf('2.69', M4('1.4.19')), LibTool('2.4.6'))
        yield Bash('4.3')

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        git_fetch(ctx, 'git://sourceware.org/git/valgrind.git', self.commit)

    def is_built(self, ctx):
        return os.path.exists('obj')

    def build(self, ctx):
        os.chdir('src')
        infra.util.run(ctx, 'bash autogen.sh')

        os.chdir(self.path(ctx))
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        infra.util.run(ctx, ['../src/configure',
                             '--prefix=' + self.path(ctx, 'install')])
        infra.util.run(ctx, 'make -j%d' % ctx.jobs)

    def is_installed(self, ctx):
        return os.path.exists('install/bin/valgrind')

    def install(self, ctx):
        os.chdir('obj')
        infra.util.run(ctx, 'make install')

    def run_wrapper(self, ctx):
        return self.path(ctx, 'install/bin/valgrind')


class Memcheck(infra.Instance):
    """
    Memcheck instance. Requires the Valgrind instrumentation framework,
    and sets the ``target_run_wrapper`` to point at the Valgrind binaries.

    :name: memcheck
    :param llvm: optionally use LLVM as compiler
    """
    name = 'memcheck'

    def __init__(self, llvm: Optional[LLVM] = None):
        self.valgrind = Valgrind()
        self.llvm = llvm

    def dependencies(self):
        if self.llvm:
            yield self.llvm
        yield self.valgrind

    def configure(self, ctx):
        if self.llvm:
            ctx.cc = 'clang'
            ctx.cxx = 'clang++'
        ctx.cflags += ['-O2']
        ctx.cxxflags += ['-O2']

    def prepare_run(self, ctx):
        ctx.target_run_wrapper = self.valgrind.run_wrapper(ctx)
