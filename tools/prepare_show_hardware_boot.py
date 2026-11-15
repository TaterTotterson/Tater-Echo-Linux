#!/usr/bin/env python3
"""Assemble Show camera-kernel candidates from audited PUBLIC inputs only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import zlib

PROFILES = {
 'checkers': {
  'baseline_sha256':'46c19fd23c210714e29eb2bf88c77b540f3290c0cf50b680b22032e7a4771da7',
  'raw_sha256':'758cb695409303453232e4313574af005a670619007df47c479afb473344e957',
  'dtb_tail_sha256':'4feeb7eaf382b03353eef699c045f59ba588c7daacc4f408a774c99227a05360',
  'kernel_sha256':'26ec7e3d23673ca892d1f6f3aeba9de2932c1b028a056e7a216d53333c82d995',
 },
 'cronos': {
  'baseline_sha256':'7e9ce93a54fc613cbfab5d15929aa06bfd6f63c2c432d6f8261b3599fc3cd791',
  'raw_sha256':'d26bc727b9780cc7eda3efba5e1ecfe8249dd4b3658e77d5aa84e85e9cd2e930',
  'dtb_tail_sha256':'6f4933f7dde548d83164c19b3df41d0c82b0a098a1fa9140a89ae12f48b72928',
  'kernel_sha256':'79410d93c4a5a5c2920cd4b4164f2d99afef17661b0cdaea1a45336e6ab734e4',
 },
}
SOURCES = {
 'scripts/repack_legacy_boot.py':'42788e7c3631bee43f059c2f87028b26f473ca5fa1ad9a87609e0530c8cb30fb',
 'scripts/athena_scp_trial_dtb.py':'c08460c03351c218549ed9f2544c718860b5ec26db142bb4ed850eb8927b8f81',
}

def digest(data):return hashlib.sha256(data).hexdigest()

def read(path,maximum):
 if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=maximum:
  raise ValueError('input must be an ordinary bounded file')
 return path.read_bytes()

def module(root,relative):
 path=root/relative
 if digest(read(path,65536))!=SOURCES[relative]:raise ValueError('hardware tooling source drift')
 name='tater_public_'+path.stem
 spec=importlib.util.spec_from_file_location(name,path)
 result=importlib.util.module_from_spec(spec);sys.modules[name]=result;spec.loader.exec_module(result)
 return result

def split(data):
 stream=zlib.decompressobj(31);stream.decompress(data,64*1024*1024)
 if not stream.eof or not stream.unused_data:raise ValueError('not a complete kernel with appended DTBs')
 return data[:len(data)-len(stream.unused_data)],stream.unused_data

def prepare(target,baseline,raw,hardware,output):
 p=PROFILES[target]
 donor=read(baseline,16*1024*1024);kernel=read(raw,16*1024*1024)
 if digest(donor)!=p['baseline_sha256'] or digest(kernel)!=p['raw_sha256']:
  raise ValueError('not the exact public baseline and reviewed raw kernel')
 if output.exists() or output.is_symlink():raise ValueError('output exists')
 boot=module(hardware,'scripts/repack_legacy_boot.py')
 dt=module(hardware,'scripts/athena_scp_trial_dtb.py')
 original=boot.verify(donor)
 gz,_=split(kernel);_,tail=split(original.kernel)
 if digest(tail)!=p['dtb_tail_sha256']:raise ValueError('baseline DTB identity mismatch')
 offset=0;count=0
 while offset<len(tail):
  if tail[offset:offset+4]!=b'\xd0\x0d\xfe\xed':raise ValueError('unexpected appended DTB data')
  size=struct.unpack_from('>I',tail,offset+4)[0]
  if not 40<=size<=len(tail)-offset:raise ValueError('invalid appended DTB bounds')
  properties=dt.properties(tail[offset:offset+size])
  if ('/soc/spi@1100a000/spi@0','amzn,mic-downmix') in properties:
   raise ValueError('public baseline must preserve separate microphone channels')
  offset+=size;count+=1
 result=gz+tail
 if digest(result)!=p['kernel_sha256']:raise ValueError('prepared kernel mismatch')
 image=boot.repack(original,result)
 check=boot.verify(image)
 if check.ramdisk!=original.ramdisk or check.second!=original.second or check.device_tree!=original.device_tree:
  raise ValueError('non-kernel payload changed')
 output.mkdir(parents=True)
 (output/'Image.gz-dtb').write_bytes(result)
 (output/'boot.img').write_bytes(image)
 report={'schema':1,'target':target,'baseline_sha256':p['baseline_sha256'],
  'raw_sha256':p['raw_sha256'],'kernel_sha256':digest(result),'boot_sha256':digest(image),
  'dtb_count':count,'separate_microphones':True,'public_ramdisk_preserved':True,'flashed':False,'release_qualified':False}
 (output/'PREPARE.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--target',required=True,choices=PROFILES)
 for name in ('baseline','raw','hardware','output'):parser.add_argument('--'+name,required=True,type=Path)
 args=parser.parse_args()
 try:print(json.dumps(prepare(args.target,args.baseline,args.raw,args.hardware,args.output),sort_keys=True))
 except (OSError,ValueError,struct.error,zlib.error) as error:parser.exit(1,'refusing: '+str(error)+'\n')
