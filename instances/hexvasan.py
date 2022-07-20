import os
from posixpath import dirname
import infra
import shutil
from infra.packages import LLVM
from infra.packages.gnu import BinUtils
from util import git_fetch


class HexVasanSource(infra.Package):

    config_path = dirname(dirname(os.path.abspath(__file__)))

    def __init__(self, commit='master'):
        self.commit = commit
        self.llvm = LLVM(
            version='3.9.1',
            compiler_rt=True,
            patches=[os.path.join(self.config_path, 'patches/compiler-rt-fix-3.9.1.patch')]
        )
        self.llvm.binutils = BinUtils('2.30')

    def ident(self):
        return 'hexvasan-%s' % self.commit

    def dependencies(self):
        yield self.llvm

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        git_fetch(ctx, 'https://github.com/HexHive/HexVASAN.git', self.commit)

        os.chdir('src')
        shutil.copytree(self.llvm.path(ctx, 'src'), 'llvm')
        
        os.chdir('llvm')
        infra.util.apply_patch(ctx, os.path.join(
            ctx.paths.root, 'patches/compiler-rt-fix-3.9.1.patch'), 1)

        self._link_hexvasan_(ctx)
        self._link_compiler_passes(ctx)
        self._link_runtime_lib(ctx)

        # Patch DiagnosticDriverKinds.td
        os.chdir('tools/clang')
        infra.util.apply_patch(ctx, os.path.join(
            ctx.paths.root, 'patches/hexvasan/clang-diagnostic-fix.patch'), 0)

    def _link_hexvasan_(self, ctx):
        os.remove('tools/clang/lib/Driver/Tools.cpp')
        os.symlink(self.path(ctx, 'src', 'src/Tools.cpp'),
                   'tools/clang/lib/Driver/Tools.cpp')

        os.remove('tools/clang/include/clang/Basic/Sanitizers.def')
        os.symlink(self.path(ctx, 'src', 'src/Sanitizers.def'),
                   'tools/clang/include/clang/Basic/Sanitizers.def')

        os.remove('tools/clang/include/clang/Driver/SanitizerArgs.h')
        os.symlink(self.path(ctx, 'src', 'src/SanitizerArgs.h'),
                   'tools/clang/include/clang/Driver/SanitizerArgs.h')

        os.remove('include/llvm/Transforms/Instrumentation.h')
        os.symlink(self.path(ctx, 'src', 'src/Instrumentation.h'),
                   'include/llvm/Transforms/Instrumentation.h')

        os.remove('include/llvm/InitializePasses.h')
        os.symlink(self.path(ctx, 'src', 'src/InitializePasses.h'),
                   'include/llvm/InitializePasses.h')

        os.remove('tools/clang/lib/CodeGen/BackendUtil.cpp')
        os.symlink(self.path(ctx, 'src', 'src/BackendUtil.cpp'),
                   'tools/clang/lib/CodeGen/BackendUtil.cpp')

        os.remove('lib/Transforms/Instrumentation/CMakeLists.txt')
        os.symlink(self.path(ctx, 'src', 'lib/Transforms/Instrumentation/CMakeLists.txt'),
                   'lib/Transforms/Instrumentation/CMakeLists.txt')

    def _link_compiler_passes(self, ctx):
        os.symlink(self.path(ctx, 'src', 'lib/Transforms/Instrumentation/VASAN.cpp'),
                   'lib/Transforms/Instrumentation/VASAN.cpp')
        os.symlink(self.path(ctx, 'src', 'lib/Transforms/Instrumentation/VASANCaller.cpp'),
                   'lib/Transforms/Instrumentation/VASANCaller.cpp')

    def _link_runtime_lib(self, ctx):
        os.symlink(self.path(ctx, 'src', 'runtime/vasan'),
                   'projects/compiler-rt/lib/vasan')

        with open('projects/compiler-rt/lib/CMakeLists.txt', 'a') as file:
            file.write("add_subdirectory(vasan)")

    def is_built(self, ctx):
        return os.path.exists('obj/bin/llvm-config')

    def build(self, ctx):
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        infra.util.run(ctx, [
            'cmake',
            '-G', 'Ninja',
            '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_C_COMPILER=clang',
            '-DCMAKE_CXX_COMPILER=clang++',
            '-DLLVM_ENABLE_ASSERTIONS=ON',
            '-DLLVM_BUILD_TESTS=OFF',
            '-DLLVM_BUILD_EXAMPLES=OFF',
            '-DLLVM_INCLUDE_TESTS=OFF',
            '-DLLVM_INCLUDE_EXAMPLES=OFF',
            '-DBUILD_SHARED_LIBS=on',
            '-DLLVM_TARGETS_TO_BUILD=X86',
            '-DCMAKE_C_FLAGS=-fstandalone-debug',
            '-DCMAKE_CXX_FLAGS=-fstandalone-debug',
            '-DCMAKE_INSTALL_PREFIX=' + self.path(ctx, 'install'),
            '../src/llvm'
        ])
        infra.util.run(ctx, 'cmake --build . -- -j %d' % ctx.jobs)

    def is_installed(self, ctx):
        return os.path.exists('install/bin/clang++')

    def install(self, ctx):
        os.chdir('obj')
        infra.util.run(ctx, 'cmake --build . --target install')


class HexVasan(infra.Instance):
    """
    HexVasan instance. Adds -fsanitize=vasan plus any
    configuration options at compile time and link time.

    :name: hexvasan
    :param halt_on_error: toggles early termination on error
    :param backtrace: runs vasan with the backtrace option (allows logging)
    :error_log_path: path to the log file (works only if backtrace is enabled)
    """
    name = 'hexvasan'

    def __init__(self, halt_on_error=True, backtrace=False,
                 error_log_path: str = None):
        self.halt_on_error = halt_on_error
        self.backtrace = backtrace
        self.error_log_path = error_log_path

    def dependencies(self):
        yield HexVasanSource()

    def configure(self, ctx):
        ctx.cc = 'clang'
        ctx.cxx = 'clang++'

        sanitize_flag = ('-fsanitize=vasan-backtrace' if self.backtrace
                         else '-fsanitize=vasan')

        ctx.cflags += [sanitize_flag, '-O2']
        ctx.cxxflags += [sanitize_flag, '-O2']
        ctx.ldflags += [sanitize_flag, '-lstdc++']

    def prepare_run(self, ctx):
        if not self.halt_on_error:
            ctx.runenv.VASAN_ERR_LOG_PATH = 1

        if self.backtrace and self.error_log_path:
            ctx.runenv.VASAN_ERR_LOG_PATH = self.error_log_path
