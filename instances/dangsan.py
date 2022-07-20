import os
import shutil
import infra
from infra.packages.cmake import CMake
from infra.packages.gnu import (
    M4, AutoConf, AutoMake, Bash, BinUtils, CoreUtils, LibTool, Make
)
from infra.packages.gperftools import LibUnwind
from util import add_env_var, git_fetch


class DangSanSource(infra.Package):

    def __init__(self, commit='master'):
        self.commit = commit
        self.binutils = BinUtils('2.30')
        self.libunwind = LibUnwind('1.2-rc1')

    def ident(self):
        return 'dangsan-' + self.commit

    def dependencies(self):
        yield Bash('4.3')
        yield Make('4.3')
        yield AutoMake('1.15.1', AutoConf('2.68', M4('1.4.18')), LibTool('2.4.6'))
        yield CMake('3.4.1')
        yield CoreUtils('8.22')
        yield self.libunwind
        yield self.binutils

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        git_fetch(ctx, 'https://github.com/vusec/dangsan.git', self.commit)

        os.chdir('src')
        git_fetch(ctx, 'git@github.com:llvm/llvm-project.git',
                  '43dff0c03324', 'llvm-project')

        # Apply LLVM patches
        os.chdir('llvm-project/llvm')
        infra.util.apply_patch(ctx, self.path(
            ctx, 'src', 'patches', 'LLVM-gold-plugins-3.8.diff'), 0)

        infra.util.apply_patch(ctx, self.path(
            ctx, 'src', 'patches', 'LLVM-safestack-3.8.diff'), 0)

        os.chdir(self.path(ctx, 'src/llvm-project/compiler-rt'))
        infra.util.apply_patch(ctx, self.path(
            ctx, 'src', 'patches', 'COMPILERRT-safestack-3.8.diff'), 0)

        os.chdir(self.path(ctx, 'src/llvm-project'))
        infra.util.apply_patch(ctx, os.path.join(
            ctx.paths.root, 'patches/compiler-rt-fix.patch'), 0)

        shutil.copytree('compiler-rt', 'llvm/projects/compiler-rt')
        shutil.copytree('clang', 'llvm/tools/clang')


    def is_built(self, ctx):
        objects_paths = ['llvm/bin/clang', 'gperftools/.libs',
                         'llvm-plugins/libplugins.so', 'metapagetable/.libs',
                         'staticlib/libmetadata.a']
        return all(os.path.exists(os.path.join('obj', path)) for path in objects_paths)

    def build(self, ctx):
        metapagetable_obj_dir = self.path(ctx, 'obj', 'metapagetable')

        self._build_llvm(ctx)
        self._build_metapagetable(ctx, metapagetable_obj_dir)
        self._build_gperftools(ctx, metapagetable_obj_dir)

        # Add the newly clang to path (needed for static lib)
        add_env_var(ctx, 'PATH', self.path(ctx, 'install/bin'))
        add_env_var(ctx, 'LD_LIBRARY_PATH', self.path(ctx, 'install/lib'))

        self._build_staticlib(ctx, metapagetable_obj_dir)
        self._build_llvm_plugins(ctx)

    def _build_llvm(self, ctx):
        os.chdir(self.path(ctx))
        os.makedirs('obj/llvm', exist_ok=True)
        os.chdir('obj/llvm')

        infra.util.run(ctx, [
            'cmake',
            '-DCMAKE_C_COMPILER=gcc',
            '-DCMAKE_CXX_COMPILER=g++',
            '-DCMAKE_BUILD_TYPE=Release',
            '-DLLVM_ENABLE_ASSERTIONS=ON',
            '-DLLVM_BINUTILS_INCDIR=' +
            self.binutils.path(ctx, 'install/include'),
            '-DCMAKE_INSTALL_PREFIX=' + self.path(ctx, 'install'),
            '../../src/llvm-project/llvm'
        ])
        infra.util.run(ctx, 'make -j %d' % ctx.jobs)
        infra.util.run(ctx, 'make install')

    def _build_metapagetable(self, ctx, metapagetable_obj_dir):
        os.chdir(self.path(ctx))
        os.makedirs(metapagetable_obj_dir, exist_ok=True)
        os.chdir(self.path(ctx, 'src', 'metapagetable'))

        ctx.runenv.METALLOC_OPTIONS = (
            '-DFIXEDCOMPRESSION=false '
            '-DMETADATABYTES=8 '
            '-DDEEPMETADATA=false '
            '-DALLOC_SIZE_HOOK=dang_alloc_size_hook'
        )
        infra.util.run(ctx, [
            'make',
            'OBJDIR=' + metapagetable_obj_dir,
            'config'
        ])
        infra.util.run(ctx, [
            'make',
            'OBJDIR=' + metapagetable_obj_dir,
            '-j' + str(ctx.jobs)
        ])

    def _build_gperftools(self, ctx, metapagetable_obj_dir):
        libwind_incl_dir = self.libunwind.path(ctx, 'install/include')
        libwind_lib_dir = self.libunwind.path(ctx, 'install/lib')

        os.chdir(self.path(ctx, 'src/gperftools-metalloc'))
        infra.util.run(ctx, 'autoreconf -fi')

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
        infra.util.run(ctx, [
            'make',
            'METAPAGETABLEDIR=' + metapagetable_obj_dir,
            '-j%d' % ctx.jobs
        ])

    def _build_staticlib(self, ctx, metapagetable_obj_dir):
        staticlib_obj_dir = self.path(ctx, 'obj', 'staticlib')
        os.makedirs(staticlib_obj_dir, exist_ok=True)
        os.chdir(self.path(ctx, 'src/staticlib'))
        infra.util.run(ctx, [
            'make',
            'CC=' + self.path(ctx, 'install/bin/clang'),
            'OBJDIR=' + staticlib_obj_dir,
            'METAPAGETABLEDIR=' + metapagetable_obj_dir,
            '-j' + str(ctx.jobs)
        ])

    def _build_llvm_plugins(self, ctx):
        os.chdir(self.path(ctx, 'src/llvm-plugins'))
        infra.util.run(ctx, [
            'make',
            'GOLDINSTDIR=' + self.path(ctx, 'install'),
            'TARGETDIR=' + self.path(ctx, 'obj', 'llvm-plugins'),
            '-j' + str(ctx.jobs)
        ])

    def is_installed(self, ctx):
        return os.path.exists('install/bin/pprof')

    def install(self, ctx):
        os.chdir('obj/gperftools')
        infra.util.run(ctx, [
            'make',
            'install',
            'METAPAGETABLEDIR=' + self.path(ctx, 'obj', 'metapagetable')
        ])

    def configure(self, ctx):
        self.libunwind.configure(ctx)
        flags = ['-fno-builtin-' + fn
                 for fn in ('malloc', 'calloc', 'realloc', 'free')]
        flags += ['-I',
                  self.path(ctx, 'install/include/gperftools')]
        ctx.cflags = flags
        ctx.cxxflags = flags
        ctx.ldflags += [
            '-L' + self.path(ctx, 'install/lib'),
            '-ltcmalloc',
            '-lpthread',
        ]


class DangSan(infra.Instance):
    """
    DangSan instance.

    :name: dangsan
    """
    name = 'dangsan'

    def __init__(self):
        self.source = DangSanSource()

    def dependencies(self):
        yield self.source

    def configure(self, ctx):
        self.source.configure(ctx)

        ctx.cc = 'clang'
        ctx.cxx = 'clang++'

        flags = ['-flto', '-fsanitize=safe-stack', '-O2']
        ldflags = [
            '-flto',
            '-fsanitize=safe-stack',
            '-Wl,-plugin-opt=-load=' + self.source.path(
                ctx, 'obj/llvm-plugins/libplugins.so'),
            '-Wl,-plugin-opt=-mergedstack=false',
            '-Wl,-plugin-opt=-largestack=false',
            '-Wl,-plugin-opt=-stacktracker',
            '-Wl,-plugin-opt=-stats',
            '-Wl,-plugin-opt=-byvalhandler',
            '-Wl,-plugin-opt=-globaltracker',
            '-Wl,-plugin-opt=-pointertracker',
            '-Wl,-plugin-opt=-FreeSentryLoop',
            '-Wl,-plugin-opt=-custominline',
            '-Wl,-whole-archive,-l:libmetadata.a,-no-whole-archive',
            '@' + self.source.path(
                ctx, 'obj/metapagetable/linker-options'),
            '-ldl',
            '-L' + self.source.path(ctx, 'obj', 'staticlib'),
            '-umetaget_8',
            '-umetaset_8',
            '-umetacheck_8',
            '-umetaset_alignment_safe_8',
            '-uinitialize_global_metadata'
        ]

        ctx.cflags += flags
        ctx.cxxflags += flags + ['-DSOPLEX_DANGSAN_MASK']
        ctx.ldflags += ldflags
        ctx.lib_ldflags += ['-flto']

    def prepare_run(self, ctx):
        ctx.runenv.SAFESTACK_OPTIONS = 'largestack=true'


class DangSanBaseline(infra.Instance):
    name = 'dangsan-baseline'
    source = DangSanSource()

    def dependencies(self):
        yield self.source

    def configure(self, ctx):
        self.source.configure(ctx)

        ctx.cc = 'clang'
        ctx.cxx = 'clang++'

        flags = ['-flto', '-O2']
        ctx.cflags += flags
        ctx.cxxflags += flags
        ctx.ldflags += ['-flto']
        ctx.lib_ldflags += ['-flto']
