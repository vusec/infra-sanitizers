import os
import infra
from infra.packages.cmake import CMake
from util import git_fetch


class HexTypeSource(infra.Package):

    def __init__(self, commit='master'):
        self.commit = commit

    def ident(self):
        return 'hextype-' + self.commit

    def dependencies(self):
        yield CMake('3.14.0')

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        git_fetch(ctx, 'https://github.com/HexHive/HexType.git', self.commit)
        
        os.chdir('src')
        infra.util.run(ctx, './scripts/get_llvm_src_tree.sh')
        infra.util.run(ctx, './scripts/install-hextype-files.sh')
        infra.util.apply_patch(ctx, os.path.join(
            ctx.paths.root, 'patches/compiler-rt-fix.patch'), 0)

    def is_built(self, ctx):
        return os.path.exists('obj/bin/llvm-config')

    def build(self, ctx):
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')

        infra.util.run(ctx, [
            'cmake',
            '-DCMAKE_BUILD_TYPE=Debug',
            '-DCMAKE_C_COMPILER=gcc',
            '-DCMAKE_CXX_COMPILER=g++',
            '-DLLVM_ENABLE_ASSERTIONS=ON',
            '-DLLVM_BUILD_TESTS=OFF',
            '-DLLVM_BUILD_EXAMPLES=OFF',
            '-DLLVM_INCLUDE_TESTS=OFF',
            '-DLLVM_INCLUDE_EXAMPLES=OFF',
            '-DBUILD_SHARED_LIBS=ON',
            '-DLLVM_TARGETS_TO_BUILD=X86',
            '-DCMAKE_INSTALL_PREFIX=' + self.path(ctx, 'install'),
            '../src/llvm'
        ])
        infra.util.run(ctx, 'cmake --build . -- -j %d' % ctx.jobs)

    def is_installed(self, ctx):
        return os.path.exists('install/bin/clang++')

    def install(self, ctx):
        os.chdir(self.path(ctx, 'obj'))
        infra.util.run(ctx, 'cmake --build . --target install')


class HexTypeBaseline(infra.Instance):
    name = 'hextype-baseline'

    def dependencies(self):
        yield HexTypeSource()

    def configure(self, ctx):
        ctx.cxx = 'clang++'
        ctx.cxxflags = ['-O2']


class HexType(infra.Instance):
    """
    HexType instance. Adds -fsanitize=hextype plus any
    configuration options at compile time and link time.

    :name: hextype
    :param coverage: toggles additional options for better coverage
    :param optimization: toggles additional options for optimizations
    """
    name = 'hextype'

    def __init__(self, coverage=True, optimization=True):
        self.coverage = coverage
        self.optimization = optimization
        self.source = HexTypeSource()

    def dependencies(self):
        yield self.source

    def configure(self, ctx):
        ctx.cxx = 'clang++'
        ctx.cxxflags += ['-fsanitize=hextype', '-O2']
        ctx.ldflags += ['-fsanitize=hextype']

        extra_flags = ['-create-clang-typeinfo']
        if self.coverage:
            extra_flags += [
                '-handle-reinterpret-cast',
                '-handle-placement-new'
            ]

        if self.optimization:
            extra_flags += [
                '-stack-opt',
                '-safestack-opt',
                '-create-cast-releated-type-list',
                '-cast-obj-opt',
                '-inline-opt',
                '-compile-time-verify-opt',
                '-enhance-dynamic-cast'
            ]

        for flag in extra_flags:
            ctx.cxxflags += ['-mllvm', flag]
