#!/usr/bin/env python3
"""Pack Athena's empty-tuning AP kernel using only a pinned public ramdisk."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BASELINE_SHA='5a0d8a151bd3bf14c80d3e779371c844481a77ac43d440db0a0e2b8b5f92a191'
IMAGE_SHA='6519c7da7d10fe7235953f9c4196b6a24a3894cc5adedd4a829058937ca4ef12'
DTB_SHA='8980ea5d3316c8eb3a408b8dafee0dbfd99bd07dc16aa635a69b6be38c27fccc'
BOOT_SHA='c6f38f2ca803845b395fe676df21de655a122377f884260d123bd8012fa3de8c'
AUDIT_SHA='c08460c03351c218549ed9f2544c718860b5ec26db142bb4ed850eb8927b8f81'
OVERLAY_SHA='077df6a4d6545a147449bbfee25070bc68935719ca787287843ee7e362d03a9c'

def digest(data):return hashlib.sha256(data).hexdigest()

def read(path,expected,maximum):
 if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=maximum:
  raise ValueError('input must be an ordinary bounded file')
 data=path.read_bytes()
 if digest(data)!=expected:raise ValueError('input identity mismatch: '+str(path))
 return data

def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path)
 value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
 return value

def prepare(baseline,image,dtb,hardware,output):
 original=read(baseline,BASELINE_SHA,16*1024*1024)
 kernel=read(image,IMAGE_SHA,16*1024*1024)
 tree=read(dtb,DTB_SHA,2*1024*1024)
 audit_path=hardware/'scripts/athena_scp_trial_dtb.py'
 read(audit_path,AUDIT_SHA,65536)
 overlay=hardware/'kernel-patches/athena-codec/athena-scp-trial.dtso'
 read(overlay,OVERLAY_SHA,65536)
 if output.exists() or output.is_symlink():raise ValueError('output exists')
 board=ROOT/'platforms/show/tools/linux/athena/kernel'
 dsp=module(board/'dsp_slot.py','tater_public_dsp_slot')
 _,slot=dsp.find_slot(tree)
 if dsp.parse_slot(slot):raise ValueError('source DTB must have empty speaker tuning')
 audit=module(audit_path,'tater_public_scp_audit')
 pack=module(board/'pack.py','tater_public_athena_pack')
 size=struct.unpack_from('<I',original,8)[0]; page=struct.unpack_from('<I',original,36)[0]
 ramdisk_size=struct.unpack_from('<I',original,16)[0]
 offset=page+((size+page-1)//page)*page
 ramdisk=original[offset:offset+ramdisk_size]
 if len(ramdisk)!=ramdisk_size:raise ValueError('truncated public ramdisk')
 output.mkdir(parents=True)
 subprocess.run(['dtc','-@','-I','dts','-O','dtb','-o',str(output/'scp.dtbo'),str(overlay)],check=True)
 subprocess.run(['fdtoverlay','-i',str(dtb),'-o',str(output/'trial.dtb'),str(output/'scp.dtbo')],check=True)
 trial=(output/'trial.dtb').read_bytes()
 scope=audit.audit(audit.properties(tree),audit.properties(trial))
 result=pack.pack(kernel,trial,ramdisk)
 _,slot=dsp.find_slot(result)
 if dsp.parse_slot(slot):raise ValueError('prepared boot contains speaker tuning')
 if digest(result)!=BOOT_SHA:raise ValueError('prepared empty-tuning boot differs from reviewed template')
 (output/'boot-athena.img').write_bytes(result)
 report={'schema':1,'target':'athena','boot_sha256':digest(result),'kernel_image_sha256':IMAGE_SHA,
  'public_baseline_sha256':BASELINE_SHA,'public_ramdisk_sha256':digest(ramdisk),
  'speaker_tuning_empty':True,'scope':scope,'flashed':False,'release_qualified':False}
 (output/'PREPARE.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('baseline','image','dtb','hardware','output'):parser.add_argument('--'+name,required=True,type=Path)
 args=parser.parse_args()
 try:print(json.dumps(prepare(args.baseline,args.image,args.dtb,args.hardware,args.output),sort_keys=True))
 except (OSError,ValueError,struct.error,subprocess.CalledProcessError) as error:parser.exit(1,'refusing: '+str(error)+'\n')
