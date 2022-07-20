import os
import shutil
import infra
from infra.packages.llvm import LLVM


class InstrumentedLibcxx(infra.Package):
    """
    Builds the libcxx library (libc++ and libc++abi) with a sanitizer 
    instrumentation.

    :identifier: libcxx-<instrumentation>
    :param llvm: an LLVM package with compiler-rt included
    :param instrumentation: specifies the sanitizer instrumentation
    """

    def __init__(self, llvm: LLVM, instrumentation: str):
        assert instrumentation in ('Address', 'Memory', 'MemoryWithOrigins',
                                   'Undefined', 'Thread', 'DataFlow')
        self.llvm = llvm
        self.instrumentation = instrumentation

    def ident(self):
        return 'libcxx-' + self.instrumentation.lower()

    def dependencies(self):
        yield self.llvm

    def is_fetched(self, ctx):
        return (os.path.exists('src/projects/libcxx') and
                os.path.exists('src/projects/libcxxabi'))

    def fetch(self, ctx):
        shutil.copytree(self.llvm.path(ctx, 'src'), 'src')

        libcxx_tar = 'libcxx-%s.src.tar.xz' % self.llvm.version
        infra.util.download(ctx, 'http://releases.llvm.org/%s/%s' %
                            (self.llvm.version, libcxx_tar))
        infra.util.untar(ctx, libcxx_tar, self.path(
            ctx, 'src', 'projects', 'libcxx'))

        libcxxabi_tar = 'libcxxabi-%s.src.tar.xz' % self.llvm.version
        infra.util.download(ctx, 'http://releases.llvm.org/%s/%s' %
                            (self.llvm.version, libcxxabi_tar))
        infra.util.untar(ctx, libcxxabi_tar, self.path(
            ctx, 'src', 'projects', 'libcxxabi'))

    def is_built(self, ctx):
        return os.path.exists('obj')

    def build(self, ctx):
        os.makedirs('obj', exist_ok=True)
        os.makedirs('install', exist_ok=True)
        os.chdir('obj')

        infra.util.run(ctx, [
            'cmake',
            '-G', 'Ninja',
            '-DCMAKE_C_COMPILER=clang',
            '-DCMAKE_CXX_COMPILER=clang++',
            '-DCMAKE_INSTALL_PREFIX=' + self.path(ctx, 'install'),
            '-DCMAKE_BUILD_TYPE=Release',
            '-DLLVM_USE_SANITIZER=' + self.instrumentation,
            self.path(ctx, 'src')
        ])
        infra.util.run(ctx, 'ninja cxx cxxabi')

    def configure(self, ctx):
        libcxx_flags = [
            '-stdlib=libc++',
            '-I%s' % self.path(ctx, 'obj', 'include'),
            '-I%s' % self.path(ctx, 'obj', 'include', 'c++', 'v1')
        ]
        ctx.cxxflags += libcxx_flags
        ctx.ldflags += libcxx_flags
        ctx.ldflags += [
            '-L%s' % self.path(ctx, 'obj', 'lib'),
            '-Wl,-rpath=%s' % self.path(ctx, 'obj', 'lib'),
            '-lc++abi',
        ]

    def is_installed(self, ctx):
        pass

    def install(self, ctx):
        pass
