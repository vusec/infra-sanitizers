#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
import sys
import os.path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'infra'))

import infra
from instances import *
from infra.instances.clang import Clang
from infra.packages.llvm import LLVM
from infra.instances import ASan
from infra.packages.gnu import BinUtils

setup = infra.Setup(__file__)
llvm = LLVM('6.0.0', True)
llvm.binutils = BinUtils('2.30')

''' Sanitizers '''
setup.add_instance(DeltaTags('deltatags', 'none', 'old'))
setup.add_instance(ClangCFI(llvm))
setup.add_instance(UbSan(llvm))
setup.add_instance(DangSan())
setup.add_instance(FFMalloc(llvm))
setup.add_instance(HexType())
setup.add_instance(MarkUs(llvm=llvm))
setup.add_instance(Memcheck(llvm))
setup.add_instance(HexVasan())
setup.add_instance(ASan(llvm))
setup.add_instance(TypeSan(
    ignorelist_path=os.path.join(
        BASE_DIR, 'ignorelists', 'typesan_ignorelist.txt'),
))
setup.add_instance(LowFat(
    ignorelist_path=os.path.join(
        BASE_DIR, 'ignorelists', 'lowfat_ignorelist.txt')
))
setup.add_instance(MSan(llvm))

''' Baselines '''
setup.add_instance(Clang(llvm))
setup.add_instance(Clang(llvm, lto=True))
setup.add_instance(HexTypeBaseline())
setup.add_instance(DangSanBaseline())
setup.add_instance(LowFatBaseline())
setup.add_instance(TypeSanBaseline())

''' Targets '''
patches = ['asan', 'dealII-stddef', 'omnetpp-invalid-ptrcheck', 'gcc-init-ptr', 'libcxx']
setup.add_target(infra.targets.SPEC2006(
    # see the following link for more options for source[_type] below:
    # http://instrumentation-infra.readthedocs.io/en/master/targets.html#infra.targets.SPEC2006
    source='spec-mount-dir', # SET THIS FOR SPEC
    source_type='mounted',   # SET THIS FOR SPEC
    patches=patches
))

setup.main()
