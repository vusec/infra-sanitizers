import os
import infra
from infra.packages import LLVM, LLVMPasses, LibShrink
from infra.packages.gnu import BinUtils
from util import git_fetch


def strbool(b):
    return 'true' if b else 'false'


class DeltaPointersPasses(LLVMPasses):
    def __init__(self, llvm: LLVM,
                 relative_srcdir: str,
                 build_suffix: str,
                 use_builtins: bool,
                 debug=False,
                 gold_passes: bool = True):
        self.relative_srcdir = relative_srcdir
        super().__init__(llvm, '', build_suffix, use_builtins, debug, gold_passes)

    def is_fetched(self, ctx):
        return False

    def fetch(self, ctx):
        self.custom_srcdir = self.path(ctx, '..', self.relative_srcdir)


class DeltaPointersSource(infra.Package):

    addrspace_bits = 32
    overflow_bit = True
    runtime_stats = False
    llvm_patches = ['gold-plugins', 'statsfilter']
    llvm = LLVM('3.8.0', compiler_rt=False, patches=llvm_patches)
    llvm.binutils = BinUtils('2.30')

    def __init__(self, commit='master', debug=False) -> None:
        self.commit = commit
        self.debug = debug
        self.llvm_passes = DeltaPointersPasses(
            llvm=self.llvm,
            relative_srcdir=f'{self.ident()}/src/llvm-passes',
            build_suffix='deltatags',
            use_builtins=True)

    def ident(self):
        return 'deltapointers-' + self.commit

    def dependencies(self):
        yield self.llvm
        yield self.llvm_passes
        yield LibShrink(self.addrspace_bits)

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        git_fetch(ctx, 'https://github.com/vusec/deltapointers.git', self.commit)

        os.chdir('src')
        infra.util.apply_patch(ctx, os.path.join(
            ctx.paths.root, 'patches/deltatags/llvm-passes.patch'), 1)

        infra.util.apply_patch(ctx, os.path.join(
            ctx.paths.root, 'patches/deltatags/runtime.patch'), 1)     

    def is_built(self, ctx):
        return os.path.exists('obj/libdeltatags.a')

    def build(self, ctx):
        os.makedirs('obj', exist_ok=True)
        self.run_make(ctx, '-j%d' % ctx.jobs)

    def run_make(self, ctx, *args):
        os.chdir(self.path(ctx, 'src/runtime'))
        env = {
            'OBJDIR': self.path(ctx, 'obj'),
            'LLVM_VERSION': self.llvm.version,
            'ADDRSPACE_BITS': str(self.addrspace_bits),
            'OVERFLOW_BIT': strbool(self.overflow_bit),
            'RUNTIME_STATS': strbool(self.runtime_stats),
            'DEBUG': strbool(self.debug)
        }
        setup_path = os.path.join(ctx.paths.root, 'setup.py')
        return infra.util.run(ctx, [
            'make',
            f'PKG_CONFIG=python3 {setup_path} pkg-config',
            *args],
            env=env)

    def install(self, ctx):
        pass

    def is_installed(self, ctx):
        return self.is_built(ctx)

    def configure(self, ctx):
        self.llvm.configure(ctx)
        self.llvm_passes.configure(ctx)

        # undef symbols to make sure the pass can find them
        exposed_functions = [
            'strsize_nullsafe', 'strtok', 'strtok_ubound', 'rts_gep',
            'rts_load', 'rts_store', 'check_neg_arith', 'mask_pointer_bzhi',
            'mask_pointer_pext_reg', 'mask_pointer_pext_glob', 'execv_mask',
            'execvp_mask', 'execvpe_mask', 'execve_mask', 'writev_mask',
            'is_oob', '_tag_pointer', '_mask_pointer', '_tag_of', '_take_tag',
            '_ptr_arith'
        ]
        ctx.ldflags += ['-u__noinstrument_' + fn for fn in exposed_functions]

        # link static library
        ctx.ldflags += ['-L' + self.path(ctx, 'obj'), '-Wl,-whole-archive',
                        '-l:libdeltatags.a', '-Wl,-no-whole-archive']
        cflags = ['-DDELTAPOINTERS', '-I' + self.path(ctx, 'src/runtime')]
        cflags += self.llvm_passes.runtime_cflags(ctx)
        ctx.cflags += cflags
        ctx.cxxflags += cflags

        # pass overflow-bit option to instrumentation pass
        LLVM.add_plugin_flags(ctx, '-overflow-bit=' +
                              strbool(self.overflow_bit))


class DeltaTags(infra.Instance):
    addrspace_bits = 32

    def __init__(self, name, overflow_check, optimizer, debug=False):
        self.name = name
        self.overflow_check = overflow_check
        self.optimizer = optimizer
        self.debug = debug
        self.libshrink = LibShrink(self.addrspace_bits, debug=debug)
        self.source = DeltaPointersSource(debug=debug)

    def dependencies(self):
        yield self.source
        yield self.libshrink

    def configure(self, ctx):
        self.source.configure(ctx)
        self.libshrink.configure(ctx)

        if self.debug:
            ctx.cflags += ['-O0', '-ggdb']
            ctx.cxxflags += ['-O0', '-ggdb']
            LLVM.add_plugin_flags(ctx, '-disable-opt')
        else:
            # note: link-time optimizations break some programs (perlbench,
            # gcc) if our instrumentation runs and -O2 was not passed at
            # compile time
            ctx.cflags += ['-O2']
            ctx.cxxflags += ['-O2']

        def add_stats_pass(name, *args):
            LLVM.add_plugin_flags(ctx, name, '-stats-only=' + name, *args)

        # prepare initalizations of globals so that the next passes only have to
        # operate on instructions (rather than constantexprs)
        add_stats_pass('-defer-global-init')
        add_stats_pass('-expand-const-global-users')

        # make sure all calls to allocation functions are direct
        add_stats_pass('-replace-address-taken-malloc')

        # do some analysis for optimizations
        if self.optimizer == 'old':
            add_stats_pass('-safe-allocs-old')
        elif self.optimizer == 'new':
            # simplify loops to ease analysis
            LLVM.add_plugin_flags(ctx, '-loop-simplify')
            add_stats_pass('-safe-allocs')

        # find integers that contain pointer values and thus need to be masked
        add_stats_pass('-find-reinterpreted-pointers')

        # tag heap/stack/global allocations
        add_stats_pass('-deltatags-alloc',
                       '-address-space-bits=%d' % self.addrspace_bits)

        # propagate size tags on ptr arith and libc calls
        add_stats_pass('-deltatags-prop',
                       '-deltatags-check-overflow=' + self.overflow_check)

        # mask pointers at dereferences / libcalls
        add_stats_pass('-mask-pointers',
                       '-mask-pointers-ignore-list=strtok')

        # undo loop simplification changes
        if self.optimizer == 'new':
            LLVM.add_plugin_flags(ctx, '-simplifycfg')

        # dump IR for debugging
        LLVM.add_plugin_flags(ctx, '-dump-ir')

        # inline statically linked helpers
        LLVM.add_plugin_flags(ctx, '-custominline')

    def prepare_run(self, ctx):
        assert 'target_run_wrapper' not in ctx
        ctx.target_run_wrapper = self.libshrink.run_wrapper(ctx)

    @ classmethod
    def make_instances(cls):
        # cls(name, overflow_check, optimizer)
        yield cls('deltatags-noopt', 'none', None)
        yield cls('deltatags', 'none', 'old')
        yield cls('deltatags-satarith', 'satarith', 'old')
        yield cls('deltatags-newopt', 'none', 'new')
