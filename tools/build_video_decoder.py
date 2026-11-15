#!/usr/bin/env python3
"""Build the pinned ARMv7 FFmpeg in a fresh container, without device inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from urllib import request

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'build-inputs/video-decoder.json'


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def build(source,output):
    lock=json.loads(LOCK.read_text())
    if source.is_symlink() or not source.is_file() or digest(source)!=lock['source_sha256']:
        raise ValueError('FFmpeg source archive differs from the lock')
    if output.exists() or output.is_symlink():raise ValueError('output exists; refusing to reuse build products')
    identity=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',lock['builder']],text=True).strip()
    if identity!=lock['builder_image_id']:raise ValueError('builder config identity differs from the lock')
    output.mkdir(parents=True)
    script='''set -eu
apk add --no-cache PACKAGES
apk info -v > /out/BUILD-PACKAGES.txt
bash /platform/tools/linux/build-ffmpeg.sh -o /out/tater-ffmpeg-armv7 > /out/build.log 2>&1
cp /build/techo5-ffmpeg-8.1.2/COPYING.LGPLv2.1 /out/FFMPEG-LGPL-2.1.txt
/out/tater-ffmpeg-armv7 -version > /out/VERSION.txt 2>&1
/out/tater-ffmpeg-armv7 -bsfs > /out/BSFS.txt 2>&1
'''.replace('PACKAGES',' '.join(lock['packages']),1)
    subprocess.run(['docker','run','--rm','--platform','linux/arm/v7','--cpus','4',
        '-e','CAST_SDK=/','-e','TECHO5_IN_NS=1','-e','TECHO5_ROOT=/platform','-e','SOURCE_DATE_EPOCH=0',
        '-v',str((ROOT/'platforms/show').resolve())+':/platform:ro',
        '-v',str(source.resolve())+':/build/ffmpeg-8.1.2.tar.xz:ro',
        '-v',str(output.resolve())+':/out',lock['builder'],'sh','-ec',script],check=True)
    binary=output/'tater-ffmpeg-armv7'
    if digest(binary)!=lock['output_sha256'] or binary.stat().st_size!=lock['output_size']:
        raise ValueError('FFmpeg output drift: retain the failed build for inspection; do not publish it')
    for name in ('h264_mp4toannexb','h264_metadata'):
        if name not in (output/'BSFS.txt').read_text().splitlines():raise ValueError('required bitstream filter missing')
    print(json.dumps({'sha256':digest(binary),'size':binary.stat().st_size,'source_sha256':lock['source_sha256']},sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-tar',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.source_tar:build(args.source_tar,args.output)
        else:
            lock=json.loads(LOCK.read_text())
            with tempfile.TemporaryDirectory(prefix='tater-ffmpeg-source-') as temporary:
                source=Path(temporary)/'ffmpeg.tar.xz'
                with request.urlopen(lock['source_url'],timeout=60) as response:
                    if not response.geturl().startswith('https://'):raise ValueError('source redirect must remain HTTPS')
                    data=response.read(64*1024*1024+1)
                    if len(data)>64*1024*1024:raise ValueError('source exceeds its boundary')
                source.write_bytes(data)
                build(source,args.output)
    except (OSError,ValueError,subprocess.CalledProcessError) as error:parser.exit(1,'refusing: '+str(error)+'\n')
