import os
import shutil
from pathlib import Path
import infra
from infra.packages.llvm import LLVM
from util import git_fetch


class FFMallocAlloc(infra.Package):
    lib = 'libffmallocnpmt.so'

    def ident(self):
        return 'ffmalloc-alloc'

    def is_fetched(self, ctx):
        return Path('src').exists()

    def fetch(self, ctx):
        git_fetch(ctx, 'https://github.com/bwickman97/ffmalloc.git')

    def is_built(self, ctx):
        pkgdir = Path(self.path(ctx))
        return (pkgdir / 'src' / 'libffmallocnpmt.so').exists()

    def build(self, ctx):
        pkgdir = Path(self.path(ctx))
        srcdir = pkgdir / 'src'

        os.chdir(srcdir)
        infra.util.run(ctx, 'make -j%d' % ctx.jobs)

    def is_installed(self, ctx):
        return Path(self.libpath(ctx)).exists()

    def install(self, ctx):
        pkgdir = Path(self.path(ctx))
        os.makedirs(pkgdir / 'install' / 'lib', exist_ok=True)
        shutil.copy(pkgdir / 'src' / self.lib, self.libpath(ctx))

    def set_env(self, ctx):
        ctx.runenv.LD_PRELOAD = self.libpath(ctx)

    def libpath(self, ctx):
        return self.path(ctx, 'install', 'lib', self.lib)


class FFMalloc(infra.Instance):
    """
    FFMalloc instance. Adds the ffmalloc allocator to ``LD_PRELOAD``.

    :name: ffmalloc
    :param llvm: optionally use LLVM as compiler
    """
    name = 'ffmalloc'
    allocator = FFMallocAlloc()

    def __init__(self, llvm: LLVM = None):
        self.llvm = llvm

    def dependencies(self):
        if self.llvm:
            yield self.llvm
        yield self.allocator

    def configure(self, ctx):
        if self.llvm:
            ctx.cc = 'clang'
            ctx.cxx = 'clang++'
        ctx.cflags += ['-O2']
        ctx.cxxflags += ['-O2']

    def prepare_run(self, ctx):
        self.allocator.set_env(ctx)
