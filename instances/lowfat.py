import os
import infra
from infra import Instance, Package
from infra.packages import Bash, CoreUtils, Make, AutoMake, CMake
from infra.util import param_attrs
from util import git_fetch


class LowFatSource(Package):

    def __init__(self, commit='master'):
        self.commit = commit

    def ident(self):
        return 'lowfat-' + self.commit

    def dependencies(self):
        yield Bash('4.3')
        yield CoreUtils('8.22')
        yield Make('4.1')
        yield AutoMake.default()
        yield CMake('3.8.2')

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        git_fetch(ctx, 'https://github.com/GJDuck/LowFat.git', self.commit)

    def is_built(self, ctx):
        return os.path.exists('src/build/bin/clang')

    def build(self, ctx):
        os.chdir('src')
        infra.util.run(ctx, 'bash build.sh')

    def is_installed(self, ctx):
        return os.path.exists('install/bin/')

    def install(self, ctx):
        os.makedirs('install', exist_ok=True)
        os.chdir('install')
        os.symlink(self.path(ctx, 'src/build/bin'), 'bin', True)
        os.symlink(self.path(ctx, 'src/build/lib'), 'lib', True)
        os.symlink(self.path(ctx, 'src/build/include'), 'include', True)
        os.symlink(self.path(ctx, 'src/build/libexec'), 'libexec', True)
        os.symlink(self.path(ctx, 'src/build/share'), 'share', True)


class LowFatBaseline(Instance):
    name = 'lowfat-baseline'

    def dependencies(self):
        yield LowFatSource()
    
    def configure(self, ctx):
        ctx.cc = 'clang'
        ctx.cxx = 'clang++'
        ctx.cflags += ['-O2']
        ctx.cxxflags += ['-O2']


class LowFat(Instance):
    """
    LowFat Pointers instance. Adds -fsanitize=lowfat plus any
    configuration options at compile time and link time.

    Note: To run SPEC CPU2006 you need to use the ignorelist provided.

    :name: lowfat
    :param fowfat_flags: list of command line options for LowFat Pointers
    :param ignorelist_path: absolute path to ignorelist (default: None)
    :param debug: toggle debugging options
    :param abort: toggle program abortion if an OOB memory error occurs
    :param paper: builds LowFat Pointers with the initial version of the tool
    """
    name = 'lowfat'

    @param_attrs
    def __init__(self, lowfat_flags=[], ignorelist_path: str = None,
                 debug=False, abort=True, paper=False):
        commit = '5811fab760b3c4780372362e20bfa9b55f942f1c' if paper else 'master'
        self.source = LowFatSource(commit=commit)

    def dependencies(self):
        yield self.source

    def configure(self, ctx):
        flags = ['-fsanitize=lowfat', '-O2']
        for f in self.lowfat_flags:
            flags += ['-mllvm', f]

        if self.ignorelist_path:
            flags += ['-mllvm', '-lowfat-no-check-blacklist=' +
                      self.ignorelist_path]

        if not self.abort:
            flags += ['-mllvm', '-lowfat-no-abort']

        if self.debug:
            flags += ['-g', '-fno-inline-functions']

        ctx.cc = 'clang'
        ctx.cxx = 'clang++'
        ctx.cflags += flags
        ctx.cxxflags += flags
        ctx.ldflags += ['-fsanitize=lowfat']
