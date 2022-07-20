import os
import shutil
import infra
from infra.packages.gnu import AutoMake, GNUTarPackage
from util import add_env_var


class Bdw_gc(GNUTarPackage):
    """
    :identifier: bdw_gc-<version>
    :param str version: version to download
    :param automake: automake package
    """
    name = 'bdw-gc'
    built_path = '.libs/libgc.so'
    installed_path = 'lib'
    tar_compression = 'gz'

    def __init__(self, version, automake: AutoMake):
        self.version = version
        self.automake = automake

    def dependencies(self):
        yield self.automake

    def fetch(self, ctx):
        tarname = 'gc-%s.tar.%s' % (self.version, self.tar_compression)
        infra.util.download(
            ctx, 'https://hboehm.info/gc/gc_source/%s' % (tarname))
        infra.util.untar(ctx, tarname, self.path(ctx, 'src'))

        libatomic_tar = 'libatomic_ops-7.2j.tar.gz'
        infra.util.download(
            ctx, 'https://github.com/ivmai/libatomic_ops/releases/download/v7.2j/' + libatomic_tar)
        infra.util.run(ctx, ['tar', '-xf', libatomic_tar])
        os.remove(libatomic_tar)
        shutil.move('libatomic_ops-7.2', self.path(ctx, 'src/libatomic_ops'))

    def install_env(self, ctx):
        super().install_env(ctx)
        add_env_var(ctx, 'PKG_CONFIG_PATH', self.path(
            ctx, 'install', 'lib', 'pkgconfig'))
