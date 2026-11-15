#!/usr/bin/env python3
"""Rebuild reviewed MT8163 kernels in a fresh offline container; never flash."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT/'build-inputs/hardware-kernels'
TOOLCHAIN_SHA256 = '8ce3e7688a47d8cd2d8e8323f147104ae1c8139520eca50ccf8a7fa933002731'
PROFILES = {
 'checkers': {
  'source_sha256':'4e0b311affbd75d58c64630c235146a5f27edcfcfdac6104e7e7cd4ca86ebe08','strip':1,
  'config_sha256':'93bde8f9783a91ad4e5626030fd81b5f60112903d4466a24d08798c2d9568271',
  'release':'4.9.337-g8d928c5176cc','localversion':'-g8d928c5176cc',
  'user':'root','host':'ce210981830e','timestamp':'Thu Nov 12 14:25:24 UTC 2026','version':'4',
  'expected_raw_sha256':'758cb695409303453232e4313574af005a670619007df47c479afb473344e957',
  'patches':[f'platforms/show/tools/linux/patches/checkers-000{n}-{name}.patch' for n,name in (
   (1,'mic-enable-on-capture'),(2,'camera-follows-the-latch'),(3,'mute-button-follows-a-short-press'),(4,'jack-plugged-in-at-boot'))]
   +['build-inputs/hardware-kernels/checkers-display-compat.patch','platforms/show/tools/linux/checkers-patches/0005-camera-clock-handles.patch'],
 },
 'cronos': {
  'source_sha256':'4e0b311affbd75d58c64630c235146a5f27edcfcfdac6104e7e7cd4ca86ebe08','strip':1,
  'config_sha256':'1967374f541393c4373beb0d4ee6bf152a9da22a6a4b0eb53526df4a419f04c6',
  'release':'4.9.337-g8d928c5176cc','localversion':'-g8d928c5176cc',
  'user':'tater','host':'cronos-research','timestamp':'Fri Nov 13 17:15:00 UTC 2026','version':'2',
  'expected_raw_sha256':'d26bc727b9780cc7eda3efba5e1ecfe8249dd4b3658e77d5aa84e85e9cd2e930',
  'patches':['platforms/show/tools/linux/checkers-patches/0005-camera-clock-handles.patch'],
 },
 'rook': {
  'source_sha256':'10769f2501d815a19bb8f045fc1d8df9bf8cebae164f45cf83f901160c63809c','strip':0,
  'config_sha256':'9e51dd4b9849c29c4bd88c56b04c0338f528d01dae9ed7071edbaacacb8fb7d8',
  'release':'4.9.337-g4174e0b4d0e2','localversion':'-g4174e0b4d0e2',
  'user':'tater','host':'rook-research','timestamp':'Sun Nov 15 01:30:00 UTC 2026','version':'2',
  'expected_raw_sha256':'aa33d9b29a5c4d3e5a3805842df385858589de62272e8cca8a5f263adaef5d17',
  'patches':['platforms/spot/patches/0001-fix-mchange-irq-prototype.patch','platforms/show/tools/linux/checkers-patches/0005-camera-clock-handles.patch'],
 },
}

def sha256(path):
 value=hashlib.sha256()
 if path.is_symlink() or not path.is_file(): raise ValueError('expected an ordinary file: '+str(path))
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''): value.update(block)
 return value.hexdigest()

def build(target,source,toolchain,output,builder,jobs):
 profile=PROFILES[target]
 config=INPUTS/(target+'.config')
 for path,expected in ((source,profile['source_sha256']),(toolchain,TOOLCHAIN_SHA256),(config,profile['config_sha256'])):
  if sha256(path)!=expected: raise ValueError('input hash mismatch: '+str(path))
 if output.exists() or output.is_symlink(): raise ValueError('output exists; refusing to overwrite or reuse objects')
 if not 1<=jobs<=8: raise ValueError('jobs must be between one and eight')
 patches={relative:sha256(ROOT/relative) for relative in profile['patches']}
 output.mkdir(parents=True)
 environment={
  'ARCH':'arm64','CROSS_COMPILE':'/toolchain/bin/aarch64-linux-gnu-',
  'LOCALVERSION':profile['localversion'],'KBUILD_BUILD_USER':profile['user'],
  'KBUILD_BUILD_HOST':profile['host'],'KBUILD_BUILD_TIMESTAMP':profile['timestamp'],
  'KBUILD_BUILD_VERSION':profile['version'],'LC_ALL':'C','TZ':'UTC',
 }
 # Checkers' old Docker hostname is an arbitrary builder label, not a device
 # identity. Pinning it reproduces the reviewed raw image before DTB correction.
 # No boot image, device backup or vendor library is read by this builder.
 script="""set -eu
mkdir /src /out /toolchain
tar -xf /inputs/toolchain.tar.xz -C /toolchain --strip-components=1
test "$(/toolchain/bin/aarch64-linux-gnu-gcc -dumpversion)" = 8.3.0
tar -xf /inputs/source.tar.gz -C /src --strip-components=STRIP
cd /src
PATCHES
touch .scmversion
cp /repo/build-inputs/hardware-kernels/TARGET.config /out/.config
make -s O=/out olddefconfig
cmp /repo/build-inputs/hardware-kernels/TARGET.config /out/.config
make -s -jJOBS O=/out Image.gz-dtb
test "$(cat /out/include/config/kernel.release)" = RELEASE
cp /out/arch/arm64/boot/Image.gz-dtb /export/Image.gz-dtb
cp /out/.config /export/kernel.config
cp /out/Module.symvers /export/Module.symvers
"""
 script=script.replace('STRIP',str(profile['strip'])).replace('TARGET',target).replace('JOBS',str(jobs)).replace('RELEASE',profile['release'])
 script=script.replace('PATCHES','\n'.join('git apply --check /repo/'+p+'\ngit apply /repo/'+p for p in patches))
 command=['docker','run','--rm','--platform','linux/amd64','--network','none']
 for key,value in environment.items(): command+=['-e',key+'='+value]
 command+=['-v',str(ROOT)+':/repo:ro','-v',str(source.resolve())+':/inputs/source.tar.gz:ro',
  '-v',str(toolchain.resolve())+':/inputs/toolchain.tar.xz:ro','-v',str(output.resolve())+':/export',builder,'bash','-ec',script]
 subprocess.run(command,check=True)
 actual=sha256(output/'Image.gz-dtb')
 record={'schema':1,'target':target,'builder':builder,'profile':profile,'patches':patches,
  'kernel_sha256':actual,'reproduced':actual==profile['expected_raw_sha256'],'flashed':False}
 (output/'BUILD.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
 if not record['reproduced']: raise ValueError('kernel differs from reviewed raw build; inspect BUILD.json, do not publish/promote')
 return record

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--target',choices=PROFILES,required=True)
 for name in ('source','toolchain','output'): parser.add_argument('--'+name,type=Path,required=True)
 parser.add_argument('--builder',required=True,help='Linux image with git, make, bc, bison, flex and host C compiler')
 parser.add_argument('--jobs',type=int,default=2)
 args=parser.parse_args()
 try: print(json.dumps(build(args.target,args.source,args.toolchain,args.output,args.builder,args.jobs),sort_keys=True))
 except (OSError,ValueError,subprocess.CalledProcessError) as error: parser.exit(1,'refusing: '+str(error)+'\n')
