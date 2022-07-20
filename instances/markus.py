import os.path
from typing import Optional
import infra
from infra.packages import AutoConf, M4, LibTool, Make
from infra.packages.llvm import LLVM
from packages.gnu_tools import AutoGen, Guile
from infra.packages.gnu import AutoMake
from util import git_fetch


class MarkUsAlloc(infra.Package):

    def __init__(self, commit='master'):
        self.commit = commit
        self.libs = ('libgc.so', 'libgccpp.so')

    def ident(self):
        return 'markus-' + self.commit

    def dependencies(self):
        yield AutoGen('5.18.7', Guile('2.0.11'))
        yield AutoMake.default()
        yield AutoConf('2.69', M4('1.4.19'))
        yield LibTool('2.4.6')
        yield Make('4.3')

    def is_fetched(self, ctx):
        return os.path.exists(self.path(ctx, 'src'))

    def fetch(self, ctx):
        git_fetch(
            ctx, 'https://github.com/SamAinsworth/MarkUs-sp2020.git', self.commit)

    def is_built(self, ctx):
        return all(os.path.exists(self.path(ctx, 'obj/.libs', lib))
                   for lib in self.libs)

    def build(self, ctx):
        src_dir = self.path(ctx, 'src', 'bdwgc-markus')
        os.chdir(src_dir)
        infra.util.run(ctx, './autogen.sh')

        os.chdir(self.path(ctx))
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        prefix = self.path(ctx, 'install')
        infra.util.run(ctx, [
            os.path.join(src_dir, 'configure'),
            '--prefix=' + prefix,
            '--enable-redirect-malloc',
            '--enable-threads=posix',
            '--disable-gc-assertions',
            '--enable-thread-local-alloc',
            '--enable-parallel-mark',
            '--disable-munmap',
            '--enable-cplusplus',
            '--enable-large-config',
            '--disable-gc-debug',
        ])
        infra.util.run(ctx, 'make -j%d' % ctx.jobs)

    def is_installed(self, ctx):
        return all(os.path.exists(self.path(ctx, 'install/lib', lib))
                   for lib in self.libs)

    def install(self, ctx):
        os.chdir('obj')
        infra.util.run(ctx, 'make install')

    def install_ldpreload(self, ctx):
        ctx.runenv.LD_PRELOAD = ' '.join(self.path(ctx, 'install', 'lib', lib)
                                         for lib in self.libs)


class MarkUs(infra.Instance):
    """
    MarkUs instance. Adds the markus allocator to ``LD_PRELOAD``.

    :name: markus[-legacy]
    :param legacy: toggles legacy mode (for systems that do not have MADV_FREE)
    :param llvm: optionally use LLVM as compiler
    """
    def __init__(self, legacy=False, llvm: Optional[LLVM] = None):
        self.legacy = legacy
        commit = '7a5c0df4b5c070d5aa6a99ee0bd0ad79d8f2a9b6' if legacy else 'master'
        self.allocator = MarkUsAlloc(commit)
        self.llvm = llvm

    @property
    def name(self):
        ident = 'markus'
        if self.legacy:
            ident += '-legacy'
        return ident

    def dependencies(self):
        if self.llvm:
            yield self.llvm
        yield self.allocator

    def prepare_run(self, ctx):
        self.allocator.install_ldpreload(ctx)

    def configure(self, ctx):
        if self.llvm:
            self.llvm.configure(ctx)
        ctx.cflags += ['-O2']
        ctx.cxxflags += ['-O2']
