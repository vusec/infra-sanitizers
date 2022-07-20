from typing import Optional
from infra.instances.clang import Clang
from infra.util import param_attrs
from packages.instr_libcxx import InstrumentedLibcxx


class MSan(Clang):
    """
    MSan instanace. Adds ``-fsanitize=memory`` plus any
    configuration options at compile time and link time.
    In uses an instrumented libcxx library. 

    :name: clang-<llvm.version>-msan
    :param llvm: an LLVM package with compiler-rt included
    :param tail_call_elim: toggle tail call elimination
    :param origin_tracking_level: ogirin tracking level (default: 0)
    :param use_after_dtor: toggle use-after-destruction detection
    :param debug: toggle debugging options
    :param ignorelist_path: absolute path to ignorelist (default: None)
    """
    @param_attrs
    def __init__(self, llvm, tail_call_elim=True, origin_tracking_level=0,
                 use_after_dtor=True, debug=False,
                 ignorelist_path: Optional[str] = None):
        assert llvm.compiler_rt, 'Msan needs LLVM with runtime support'
        assert origin_tracking_level in (
            0, 1, 2), 'origin tracking should be 0, 1 or 2'

        self.llvm = llvm
        self.libcxx = InstrumentedLibcxx(self.llvm, 'Memory')

        opt = 1 if debug else 2
        super().__init__(llvm, optlevel=opt)

    @property
    def name(self):
        return 'clang-%s-msan' % self.llvm.version

    def dependencies(self):
        yield from super().dependencies()
        yield self.libcxx

    def configure(self, ctx):
        super().configure(ctx)

        flags = ['-fsanitize=memory']

        if not self.tail_call_elim:
            flags += ['-fno-optimize-sibling-calls']

        if self.ignorelist_path:
            flags += ['-fsanitize-blacklist=' + self.ignorelist_path]

        if self.origin_tracking_level in (1, 2):
            flags += ['-fsanitize-memory-track-origins=' +
                      self.origin_tracking_level]

        if not self.use_after_dtor:
            flags += ['-fno-sanitize-memory-use-after-dtor']

        if self.debug:
            flags += ['-ggdb', '-fno-omit-frame-pointer']

        ctx.cflags += flags
        ctx.cxxflags += flags
        ctx.ldflags += ['-fsanitize=memory']

        self.libcxx.configure(ctx)

    def prepare_run(self, ctx):
        if not self.use_after_dtor:
            ctx.runenv.MSAN_OPTIONS = 'poison_in_dtor=0'


class ClangCFI(Clang):
    """
    ClangCFI instanace.

    :name: clang-<llvm.version>-cfi
    :param llvm: an LLVM package
    :param check: list cfi schemes to check
    :param no_trap: list of cfi schemes to print a diagnostic info 
                    if program aborts
    :param recover: list of cfi schemes to continue execution 
                    if an error is encountered
    :param visibility:
    :param thin_lto: toggle thinLTO. if it set to false ``-flto`` is used
    :param no_check: list cfi schemes not to check
    :param ignorelist_path: absolute path to ignorelist (default: None)
    """
    @param_attrs
    def __init__(self, llvm, check=['cfi'], no_trap=['cfi'], recover=['all'],
                 visibility='hidden', thin_lto=False, no_check: Optional[str] = None,
                 ignorelist_path: Optional[str] = None):
        assert llvm.compiler_rt, 'ClangCFI needs LLVM with runtime support'
        super().__init__(llvm, lto=True)

    @property
    def name(self):
        return 'clang-%s-cfi' % self.llvm.version

    def configure(self, ctx):
        super().configure(ctx)

        ctx.cxxflags += ['-fsanitize=' +
                         ','.join('%s' % f for f in self.check)]
        ctx.ldflags += ctx.cxxflags

        ctx.cxxflags += ['-fvisibility=' + self.visibility]
        if self.no_check:
            ctx.cxxflags += ['-fno-sanitize=' +
                             ','.join('%s' % f for f in self.no_check)]

        if self.no_trap:
            ctx.cxxflags += ['-fno-sanitize-trap=' +
                             ','.join('%s' % f for f in self.no_trap)]

        if self.recover:
            ctx.cxxflags += ['-fsanitize-recover=' +
                             ','.join('%s' % f for f in self.recover)]

        if self.ignorelist_path:
            flags += ['-fsanitize-blacklist=%s' % self.ignorelist_path]

        if self.thin_lto:
            ctx.ldflags += ['-flto=thin']
        else:
            ctx.ldflags += ['-flto']

        # why do i need to link the ubsan here?
        ctx.ldflags += ['-fsanitize=undefined']


class UbSan(Clang):
    """
    UbSan instanace.

    :name: clang-<llvm.version>-ubsan
    :param llvm: an LLVM package with compiler-rt included
    :param check: list of checks (it continues execution on error)
    :param minimal_runtime:
    :param no_check: list of violation not to check
    :param trap: list of trap instruction
    :param no_recover: list of checks that exit the program
    :param debug: toggle debugging options
    :param ignorelist_path: absolute path to ignorelist (default: None)
    """
    @param_attrs
    def __init__(self, llvm, check=['undefined'], minimal_runtime=False,
                 no_check: Optional[str] = None, trap: Optional[str] = None,
                 no_recover: Optional[str] = None, debug=False,
                 ignorelist_path: Optional[str] = None):
        assert llvm.compiler_rt, 'UbSan needs LLVM with runtime support'
        assert check, 'No check flags are specified'

        opt = 1 if debug else 2
        super().__init__(llvm, optlevel=opt)

    @property
    def name(self):
        return 'clang-%s-ubsan' % self.llvm.version

    def configure(self, ctx):
        super().configure(ctx)

        flags = ['-fsanitize=' + ','.join('%s' % f for f in self.check)]
        ldflags = flags

        if self.no_check:
            flags += ['-fno-sanitize=' +
                      ','.join('%s' % f for f in self.no_check)]

        if self.trap:
            flags += ['-fsanitize-trap=' +
                      ','.join('%s' % f for f in self.trap)]

        if self.no_recover:
            flags += ['-fno-sanitize-recover=' +
                      ','.join('%s' % f for f in self.no_recover)]

        if self.minimal_runtime:
            flags += ['-fsanitize-minimal-runtime']

        if self.ignorelist_path:
            flags += ['-fsanitize-blacklist=%s' % self.ignorelist_path]

        if self.debug:
            flags += ['-ggdb', '-fno-omit-frame-pointer']

        ctx.cflags += flags
        ctx.cxxflags += flags
        ctx.ldflags += ldflags

    def prepare_run(self, ctx):
        if self.debug:
            ctx.runenv.UBSAN_OPTIONS = 'print_stacktrace=1'
