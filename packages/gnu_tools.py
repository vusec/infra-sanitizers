import os
import infra
from util import add_env_var
from infra.packages.gnu import AutoMake, GNUTarPackage, LibTool
from packages.bdw_gc import Bdw_gc


class Libffi(GNUTarPackage):
    """
    :identifier: libffi-<version>
    :param str version: version to download
    """
    name = 'libffi'
    built_path = '.libs/libffi.so'
    installed_path = 'lib/libffi.so'
    tar_compression = 'gz'

    def fetch(self, ctx):
        ident = '%s-%s' % (self.name, self.version)
        tarname = ident + '.tar.' + self.tar_compression
        infra.util.download(
            ctx, 'https://gcc.gnu.org/pub/%s/%s' % (self.name, tarname))
        infra.util.untar(ctx, tarname, self.path(ctx, 'src'))

    def install_env(self, ctx):
        super().install_env(ctx)
        add_env_var(ctx, 'PKG_CONFIG_PATH', self.path(
            ctx, 'install', 'lib', 'pkgconfig'))


class Libunistring(GNUTarPackage):
    """
    :identifier: libunistring-<version>
    :param str version: version to download
    """
    name = 'libunistring'
    built_path = 'lib'
    installed_path = 'lib/libunistring.so'
    tar_compression = 'gz'

    def install_env(self, ctx):
        super().install_env(ctx)
        add_env_var(ctx, 'LIBRARY_PATH', self.path(ctx, 'install/lib'))
        add_env_var(ctx, 'CPATH', self.path(ctx, 'install/include'))


class GMP(GNUTarPackage):
    """
    :identifier: gmp-<version>
    :param str version: version to download
    """
    name = 'gmp'
    built_path = '.libs/libgmp.so'
    installed_path = 'lib/libgmp.so'
    tar_compression = 'bz2'

    def install_env(self, ctx):
        super().install_env(ctx)
        add_env_var(ctx, 'CPATH', self.path(ctx, 'install/include'))


class Guile(GNUTarPackage):
    """
    :identifier: guile-<version>
    :param str version: version to download
    :param gmp: gmp package
    :param libunistring: libunistring package
    :param libffi: libffi package
    :param bdw_gc: bdw_gc package
    """
    name = 'guile'
    built_path = 'libguile'
    installed_path = 'bin/guile'
    tar_compression = 'gz'

    def __init__(self, version: str,
                 gmp=GMP('6.2.1'),
                 libunistring=Libunistring('0.9.10'),
                 libffi=Libffi('3.3'),
                 bdw_gc=Bdw_gc('7.4.4', AutoMake.default()),
                 libtool=LibTool('2.4.6')):
        super().__init__(version)
        self.gmp = gmp
        self.libunistring = libunistring
        self.libffi = libffi
        self.bdw_gc = bdw_gc
        self.libtool = libtool

    def dependencies(self):
        yield self.gmp
        yield self.libunistring
        yield self.libffi
        yield self.bdw_gc
        yield self.libtool

    def build(self, ctx):
        return super().build(ctx)

    def build(self, ctx):
        add_env_var(ctx, 'LDFLAGS', '-L'+self.libtool.path(ctx, 'install/lib'))
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        if not os.path.exists('Makefile'):
            infra.util.run(ctx, ['../src/configure', '--prefix=' + self.path(
                ctx, 'install'), '--with-libgmp-prefix='+self.gmp.path(ctx, 'install')])
        infra.util.run(ctx, ['make', '-j%d' % ctx.jobs])

    def install_env(self, ctx):
        super().install_env(ctx)
        add_env_var(ctx, 'PKG_CONFIG_PATH', self.path(
            ctx, 'install', 'lib', 'pkgconfig'))


class AutoGen(GNUTarPackage):
    """
    :identifier: autogen-<version>
    :param str version: version to download
    :param guile: guile package
    """
    name = 'autogen'
    built_path = ''
    installed_path = 'bin/autogen'
    tar_compression = 'gz'

    def __init__(self, version: str, guile: Guile):
        super().__init__(version)
        self.guile = guile

    def dependencies(self):
        yield self.guile


class Gawk(GNUTarPackage):
    """
    :identifier: gawk-<version>
    :param str version: version to download
    """
    name = 'gawk'
    built_path = 'gawk'
    installed_path = 'bin/gawk'
    tar_compression = 'gz'
