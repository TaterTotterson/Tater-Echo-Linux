#!/usr/bin/env python3
"""Rebuild Athena's open kernel/AP modules, offline; no firmware or device IO."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA='4633bbda2ab95eaf2a7af4041236451d6759c72e6946265531af4b3aacefbf89'
CONFIG_SHA='f41d3bfa9256e09d1b2e6605f1b99d6354cab9d8a1ddae5899deed7f3cc2bb12'
CODEC_LOCK_SHA='5b1842005582b5adaf8cdfefea608876012a05c074d5e8eda9d2cee5d03c8d38'
IMAGE_SHA='6519c7da7d10fe7235953f9c4196b6a24a3894cc5adedd4a829058937ca4ef12'
DTB_SHA='8980ea5d3316c8eb3a408b8dafee0dbfd99bd07dc16aa635a69b6be38c27fccc'

def digest(path):
 if path.is_symlink() or not path.is_file():raise ValueError('expected an ordinary input')
 value=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
 return value.hexdigest()

def build(source,hardware,codec_lock,output,builder):
 for path,expected in ((source,SOURCE_SHA),(codec_lock,CODEC_LOCK_SHA),(ROOT/'build-inputs/hardware-kernels/athena.config',CONFIG_SHA)):
  if digest(path)!=expected:raise ValueError('Athena build input differs from lock: '+str(path))
 lock=json.loads(codec_lock.read_text())
 for relative,expected in lock['module_sources'].items():
  if digest(hardware/relative)!=expected:raise ValueError('AP module source drift')
 if output.exists() or output.is_symlink():raise ValueError('output exists; refusing stale products')
 output.mkdir(parents=True)
 script="""set -eu
test "$(gcc-13 -dumpfullversion)" = 13.3.0
mkdir /work
cd /work
tar -xf /input/linux.tar.xz
cd linux-6.18.56
board=/repo/platforms/show/tools/linux/athena/kernel
cp "$board/dts/mt8183-amazon-athena.dts" arch/arm64/boot/dts/mediatek/
python3 "$board/dsp_slot.py" empty arch/arm64/boot/dts/mediatek/mt8183-amazon-athena-dsp-slot.bin
cp "$board/src/mt8183-athena.c" sound/soc/mediatek/mt8183/
patch -p1 -N -s --no-backup-if-mismatch -i "$board/patches/0001-mt8183-afe-leave-cache-only-before-enabling-clocks.patch"
for patcher in kbuild afe-di2 afe-awb-dl1 usb-force-vbus tcs3400 btmtksdio-bdaddr btmtksdio-p192 btmtksdio-late-register mt7663s-firmware-hold display tas5805m-dsp-slot cci-sram thermal-devinfo camera; do
 python3 "$board/patches/patch-$patcher.py" "$PWD"
done
python3 /hardware/kernel-patches/athena-codec/patch_scp_trial.py "$PWD" --apply
cp /repo/build-inputs/hardware-kernels/athena.config .config
export ARCH=arm64 CC=gcc-13 HOSTCC=gcc-13
export KBUILD_BUILD_USER=tater KBUILD_BUILD_HOST=athena-codec-build
export KBUILD_BUILD_TIMESTAMP='2026-11-14 10:00:00 UTC' KBUILD_BUILD_VERSION=1
export KCFLAGS='-fdebug-prefix-map=/work/linux-6.18.56=.' KAFLAGS='-fdebug-prefix-map=/work/linux-6.18.56=.'
make -s CC=gcc-13 HOSTCC=gcc-13 olddefconfig
cmp /repo/build-inputs/hardware-kernels/athena.config .config
make -s -j3 CC=gcc-13 HOSTCC=gcc-13 Image.gz modules mediatek/mt8183-amazon-athena.dtb
cp arch/arm64/boot/Image.gz /export/Image.gz
cp arch/arm64/boot/dts/mediatek/mt8183-amazon-athena.dtb /export/empty-tuning-compiled.dtb
cp .config /export/kernel.config
cp Module.symvers /export/Module.symvers
# Match the reviewed standalone-module invocation. Full-tree builds add
# intree=Y and use different __FILE__ strings, changing the locked bytes.
make -s -j3 CC=gcc-13 HOSTCC=gcc-13 M=drivers/remoteproc modules
mkdir /ap
cp /hardware/kernel-patches/athena-codec/ap/athena_ap.c /hardware/kernel-patches/athena-codec/ap/athena_ap_vdec.c /hardware/kernel-patches/athena-codec/ap/athena_ap.h /hardware/kernel-patches/athena-codec/ap/Makefile /ap/
make -s -j3 CC=gcc-13 HOSTCC=gcc-13 M=/ap modules
cp /ap/athena_ap.ko /ap/athena_ap_vdec.ko /export/
cp drivers/remoteproc/mtk_scp.ko drivers/remoteproc/mtk_scp_ipi.ko drivers/rpmsg/mtk_rpmsg.ko /export/
"""
 command=['docker','run','--rm','--platform','linux/arm64','--network','none',
  '-v',str(ROOT)+':/repo:ro','-v',str(source.resolve())+':/input/linux.tar.xz:ro',
  '-v',str(hardware.resolve())+':/hardware:ro','-v',str(output.resolve())+':/export',builder,'bash','-ec',script]
 subprocess.run(command,check=True)
 expected={'Image.gz':IMAGE_SHA,'empty-tuning-compiled.dtb':DTB_SHA,**lock['modules']}
 actual={name:digest(output/name) for name in expected}
 report={'schema':1,'target':'athena','builder':builder,'expected':expected,'actual':actual,
  'reproduced':actual==expected,'flashed':False,'release_qualified':False}
 (output/'BUILD.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 if not report['reproduced']:raise ValueError('Athena output drift; inspect BUILD.json before promotion')
 print(json.dumps(report,sort_keys=True))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('source','hardware','codec-lock','output'):parser.add_argument('--'+name,required=True,type=Path)
 parser.add_argument('--builder',required=True)
 args=parser.parse_args()
 try:build(args.source,args.hardware,args.codec_lock,args.output,args.builder)
 except (OSError,ValueError,subprocess.CalledProcessError) as error:parser.exit(1,'refusing: '+str(error)+'\n')
