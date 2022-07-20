import os
from typing import Optional
import infra
from infra.packages.cmake import CMake
from infra.packages.gnu import AutoMake, Bash, BinUtils, CoreUtils, LibTool, Make
from infra.packages.gperftools import LibUnwind
from infra.packages.ninja import Ninja
from util import git_fetch


class TypeSanSource(infra.Package):

    def __init__(self, commit='master'):
        self.commit = commit
        self.binutils = BinUtils('2.30')
        self.libunwind = LibUnwind('1.2-rc1')

    def ident(self):
        return 'typesan-' + self.commit

    def dependencies(self):
        yield Bash('4.3')
        yield Make('4.3')
        yield AutoMake.default()
        yield LibTool('2.4.6')
        yield CMake('3.4.1')
        yield CoreUtils('8.22')
        yield Ninja('1.8.2')
        yield self.libunwind
        yield self.binutils

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        # Get typesan
        git_fetch(ctx, 'https://github.com/vusec/typesan.git', self.commit)

        # Get gperftools
        os.chdir('src')
        gperftools_commit = 'c46eb1f3d2f7a2bdc54a52ff7cf5e7392f5aa668'
        gperftools_dir = 'gperftools-metalloc'
        git_fetch(ctx, 'https://github.com/gperftools/gperftools.git',
                  gperftools_commit, gperftools_dir)

        # Patch gperftools
        os.chdir(gperftools_dir)
        infra.util.apply_patch(ctx, self.path(
            ctx, 'src', 'patches', 'GPERFTOOLS_TYPESAN.patch'), 1)
        infra.util.apply_patch(ctx, self.path(
            ctx, 'src', 'patches', 'GPERFTOOLS_SPEEDUP.patch'), 1)

        os.chdir(self.path(ctx,'src/llvm/projects'))
        infra.util.apply_patch(ctx, os.path.join(
            ctx.paths.root, 'patches/compiler-rt-fix.patch'), 0)

    def is_built(self, ctx):
        return (os.path.exists('obj/llvm/bin/clang') and
                os.path.exists('obj/gperftools/.libs') and
                os.path.exists('src/metapagetable/.libs'))

    def _build_llvm(self, ctx, libwind_incl_dir):
        os.chdir(self.path(ctx))
        os.makedirs('obj/llvm', exist_ok=True)
        os.chdir('obj/llvm')

        infra.util.run(ctx, [
            'cmake',
            '-G', 'Ninja',
            '-DLLVM_BINUTILS_INCDIR=' +
            self.binutils.path(ctx, 'install/include'),
            '-DCMAKE_BUILD_TYPE=Release',
            '-DLLVM_ENABLE_ASSERTIONS=ON',
            '-DLLVM_BUILD_TESTS=OFF',
            '-DLLVM_BUILD_EXAMPLES=OFF ',
            '-DLLVM_INCLUDE_TESTS=OFF',
            '-DLLVM_INCLUDE_EXAMPLES=OFF',
            '-DLLVM_TARGETS_TO_BUILD=X86;CppBackend',
            '-DCMAKE_C_FLAGS=-I' + libwind_incl_dir,
            '-DCMAKE_CXX_FLAGS=-I' + libwind_incl_dir,
            '-DCMAKE_INSTALL_PREFIX=' + self.path(ctx, 'install'),
            '../../src/llvm'
        ])
        infra.util.run(ctx, 'cmake --build . -- -j %d' % ctx.jobs)

    def _build_metapagetable(self, ctx):
        os.chdir(self.path(ctx))
        os.chdir(self.path(ctx, 'src/metapagetable'))

        ctx.runenv.METALLOC_OPTIONS = (
            '-DFIXEDCOMPRESSION=false '
            '-DMETADATABYTES=16 '
            '-DDEEPMETADATA=false'
        )
        infra.util.run(ctx, ['make', 'config'])
        infra.util.run(ctx, ['make', '-j' + str(ctx.jobs)])

    def _build_gperftools(self, ctx, libwind_incl_dir, libwind_lib_dir):
        os.chdir(self.path(ctx, 'src/gperftools-metalloc'))
        infra.util.run(ctx, 'autoreconf -vfi')

        os.chdir(self.path(ctx, 'obj'))
        os.makedirs('gperftools', exist_ok=True)
        os.chdir('gperftools')

        infra.util.run(ctx, [
            '../../src/gperftools-metalloc/configure',
            'CPPFLAGS=-I' + libwind_incl_dir,
            'CFLAGS=-I' + libwind_incl_dir,
            'LDFLAGS=-L' + libwind_lib_dir,
            '--prefix=' + self.path(ctx, 'install')
        ])
        infra.util.run(ctx, ['make', '-j%d' % ctx.jobs])

    def build(self, ctx):
        libwind_incl_dir = self.libunwind.path(ctx, 'install/include')
        libwind_lib_dir = self.libunwind.path(ctx, 'install/lib')

        self._build_llvm(ctx, libwind_incl_dir)
        self._build_metapagetable(ctx)
        self._build_gperftools(ctx, libwind_incl_dir, libwind_lib_dir)

    def is_installed(self, ctx):
        return (os.path.exists('install/bin/pprof') and
                os.path.exists('install/bin/clang++'))

    def install(self, ctx):
        os.chdir('obj/gperftools')
        infra.util.run(ctx, 'make install')

        os.chdir(self.path(ctx, 'obj/llvm'))
        infra.util.run(ctx, 'cmake --build . --target install')

    def configure(self, ctx):
        self.libunwind.configure(ctx)
        flags = ['-I',
                 self.path(ctx, 'install/include/gperftools')]
        ctx.cxxflags += flags
        ctx.ldflags += ['-L' + self.path(ctx, 'install/lib'),
                        '-ltcmalloc', '-lpthread']


class TypeSanBaseline(infra.Instance):
    name = 'typesan-baseline'
    source = TypeSanSource()

    def dependencies(self):
        yield self.source

    def configure(self, ctx):
        self.source.configure(ctx)
        ctx.cxx = 'clang++'
        ctx.cxxflags += ['-O2']


class TypeSan(infra.Instance):
    """
    TypeSan instance. Adds ``-fsanitize=typesan`` at compile time and link time.

    To run TypeSan with SPEC CPU2006 you need to use the ignorelist provided.

    :name: typesan
    :param ignorelist_path: absolute path to ignorelist if needed (defaults to None)
    """
    name = 'typesan'

    def __init__(self, ignorelist_path: Optional[str] = None):
        self.ignorelist_path = ignorelist_path
        self.source = TypeSanSource()

    def dependencies(self):
        yield self.source

    def configure(self, ctx):
        self.source.configure(ctx)

        ctx.cxx = 'clang++'
        ctx.cxxflags += ['-fsanitize=typesan', '-O2']
        if self.ignorelist_path:
            ctx.cxxflags += ['-fsanitize-blacklist=' + self.ignorelist_path]
        ctx.ldflags += ['-fsanitize=typesan']
