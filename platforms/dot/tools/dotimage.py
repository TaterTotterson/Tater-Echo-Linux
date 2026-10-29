"""The Dot's signed release and the boot image built from it, shared by install-dot.py and update-boot.py."""
import gzip
import hashlib
import io
import lzma
import os
import re
import struct
import subprocess
import sys
import tarfile
import zlib

from techo5lib import Release, alpine, fail, repo_root, tar_extract_all, tar_read

REPO = 'HuskerMinion/techo5-dot'
# Each board's Bluetooth kernel in a release. dot-v1.0.18 and earlier carry biscuit's only, and a
# kernel carrying another board's device trees must never go onto a unit: a board whose kernel the
# release lacks runs its own.
KERNEL_ASSETS = {
    'biscuit': 'techo5-dot-kernel-bt.zImage-dtb',
    'radar': 'techo5-dot-kernel-bt-radar.zImage-dtb',
}
KERNEL_ASSET = KERNEL_ASSETS['biscuit']
# The Echo 2nd gen's Linux 6.1 kernel (LibreEcho's, tools/linux/build-kernel-61.sh), taken instead of the
# 3.18 one only when asked for (--linux-61), or by update-boot.py for a unit already running it. Its
# local version is what tells it from the 3.18 kernel, whose config names the same board.
KERNEL_61_ASSETS = {'radar': 'techo5-dot-kernel-61-radar.zImage-dtb'}
KERNEL_61_VERSIONS = {'radar': '-techo5-radar'}
# Amazon's device type ids, in /proc/idme/device_type_id: the board each kernel is chosen by.
BOARD_TYPE_IDS = {
    'A3S5BH2HU6VAYF': 'biscuit',
    'A7WXQPH584YP': 'radar',
    'A32DOYMUN6DTXA': 'donut',
}
# Each board's root filesystem key in a release's manifest: the Echo Dot 3rd gen (donut) has its own
# daemon (echod built with -tags dot,donut) and boot scripts (tools/linux/rootfs-donut).
ROOTFS_KEYS = {'biscuit': 'arm-dot', 'radar': 'arm-dot', 'donut': 'arm-donut'}
# Where the Echo Dot 3's initramfs is loaded: TWRP's address. The stock header's 0x44000000 leaves under
# 4 MB below ram_console and pstore at 0x44400000, and an initramfs this size there never boots.
DONUT_RAMDISK_ADDR = '0x43478000'
APKS_ASSET = 'techo5-dot-rescue-apks.tar'


def kernel_config(path):
    """The kernel config a zImage-dtb carries (CONFIG_IKCONFIG), or None when the kernel is not
    gzip-compressed or carries none."""
    with open(path, 'rb') as f:
        data = f.read()
    at = data.find(b'\x1f\x8b\x08')
    if at < 0:
        return None
    try:
        image = zlib.decompressobj(31).decompress(data[at:])
        at = image.find(b'IKCFG_ST')
        if at < 0:
            return None
        return zlib.decompressobj(31).decompress(image[at + 8:])
    except zlib.error:
        return None


def kernel_board(path):
    """The board a zImage-dtb was built for, read from the kernel config it carries: CONFIG_ARCH_MTK_PROJECT,
    'biscuit' or 'radar' (LibreEcho's 6.1 kernel keeps it too). The appended device trees cannot tell them
    apart: both boards' call themselves MT8163. None when the board cannot be read."""
    config = kernel_config(path)
    m = config and re.search(rb'^CONFIG_ARCH_MTK_PROJECT="([a-z0-9_]+)"$', config, re.M)
    return m.group(1).decode() if m else None


def kernel_is_61(path, board):
    """Whether a zImage-dtb is board's Linux 6.1 kernel (KERNEL_61_VERSIONS), not its 3.18 one."""
    want = KERNEL_61_VERSIONS.get(board)
    config = kernel_config(path)
    return bool(want and config and re.search(rb'^CONFIG_LOCALVERSION="%s"$' % re.escape(want.encode()), config, re.M))


class DotRelease:
    """The release's files, downloaded into workdir and checked against the release's signed manifest,
    which covers the root filesystem, the Bluetooth kernel and the rescue packages alike."""

    def __init__(self, workdir, tag='latest', board='biscuit'):
        rel = Release(REPO, tag, workdir)
        self.rel = rel
        self.version = rel.version
        self.board = board
        self.rootfs = rel.rootfs(ROOTFS_KEYS[board])
        self.kernel = rel.asset(KERNEL_ASSET) if board != 'donut' else None
        self.apks = os.path.join(rel.dir, 'apks-dot')
        tar_extract_all(rel.asset(APKS_ASSET), self.apks)
        # What the boot image needs from the root filesystem: busybox, and the Wi-Fi bring-up on the Dot
        # 2 boards (wmtup) or our wpa_supplicant on the Dot 3 (tools/linux/build-wpa-supplicant.sh).
        self.busybox = os.path.join(rel.dir, 'busybox.static')
        self.wmtup = os.path.join(rel.dir, 'wmtup') if board != 'donut' else None
        self.wpa_supplicant = os.path.join(rel.dir, 'wpa_supplicant-donut') if board == 'donut' else None
        wants = [('bin/busybox.static', self.busybox)]
        if self.wmtup:
            wants.append(('usr/local/bin/wmtup', self.wmtup))
        if self.wpa_supplicant:
            wants.append(('sbin/wpa_supplicant', self.wpa_supplicant))
        for member, out in wants:
            data = tar_read(self.rootfs, member)
            if data is None:
                fail('the root filesystem has no %s' % member)
            with open(out, 'wb') as f:
                f.write(data)
        self.alpine = alpine(workdir)

    def kernel_for(self, board, linux61=False):
        """The release's Bluetooth kernel for board (its Linux 6.1 kernel with linux61), downloaded and
        checked against the signed manifest like the rest, or None when the release has none for it (then
        the unit keeps its own)."""
        if linux61:
            name = KERNEL_61_ASSETS.get(board)
            if not name or not self.rel.signed(name):
                return None
            return self.rel.asset(name)
        if board == 'biscuit':
            return self.kernel
        if board == 'donut':
            return None  # the Echo Dot 3 runs its own kernel: the Bluetooth stack is modules in its rootfs
        name = KERNEL_ASSETS.get(board)
        if not name or not self.rel.signed(name):
            return None
        return self.rel.asset(name)


def with_member(apk, member, path, out):
    """out: the data of the Alpine package apk as a .tar.gz, with member's contents replaced by the file
    at path. mkimage takes the first copy of a path it meets and packages come before --add, so a
    replacement has to be made inside the package."""
    with open(apk, 'rb') as f:
        blob = f.read()
    parts, off = [], 0
    while off < len(blob):  # an apk is three gzip members: signature, control, data
        d = zlib.decompressobj(31)
        data = d.decompress(blob[off:]) + d.flush()
        parts.append(data)
        off = len(blob) - len(d.unused_data)
    src = tarfile.open(fileobj=io.BytesIO(parts[-1]))
    buf = io.BytesIO()
    found = False
    with tarfile.open(fileobj=buf, mode='w') as dst:
        for ti in src.getmembers():
            if ti.name == member:
                with open(path, 'rb') as f:
                    new = f.read()
                ti.size = len(new)
                dst.addfile(ti, io.BytesIO(new))
                found = True
            else:
                dst.addfile(ti, src.extractfile(ti) if ti.isfile() else None)
    if not found:
        fail('%s has no %s to replace' % (os.path.basename(apk), member))
    with open(out, 'wb') as f:
        f.write(gzip.compress(buf.getvalue()))


TWRP_HANDOFF_SERVICE = b'''\n# Tater Linux runs from this board's recovery partition.  A Volume-Up handoff
# boots this TWRP image from RAM, then puts Linux back before the user leaves
# TWRP so the following reboot behaves like the other Echo satellites.
service tater-restore-linux /sbin/sh /sbin/tater-restore-linux.sh
    user root
    group root
    seclabel u:r:recovery:s0
    oneshot
'''

TWRP_HANDOFF_SCRIPT = b'''#!/sbin/sh
PATH=/sbin:/system/bin
export PATH
TMP=/tmp/tater-twrp-handoff.log
S=/cache/techo5
LINUX=$S/linux.img
REC=/dev/block/mmcblk0p12
MISC=/dev/block/mmcblk0p8
exec >$TMP 2>&1
echo "tater-twrp-handoff: waiting for cache"

n=0
while [ $n -lt 60 ]; do
    if grep -q ' /cache ' /proc/mounts; then break; fi
    mkdir -p /cache
    mount -t ext4 /dev/block/mmcblk0p15 /cache 2>/dev/null || true
    sleep 1
    n=$((n + 1))
done
if ! grep -q ' /cache ' /proc/mounts; then
    echo "tater-twrp-handoff: cache did not mount; leaving TWRP installed"
    exit 1
fi
cp $TMP $S/twrp-handoff.log 2>/dev/null || true

restore_twrp() {
    image=$S/twrp-handoff.img
    [ -s "$image" ] || image=$S/twrp.img
    [ -s "$image" ] || return 1
    length=$(wc -c < "$image")
    wanted=$(md5sum "$image" | cut -d' ' -f1)
    dd if="$image" of=$REC bs=1048576 2>/dev/null
    sync
    actual=$(head -c "$length" $REC | md5sum | cut -d' ' -f1)
    [ "$actual" = "$wanted" ]
}

if [ ! -s "$LINUX" ] || [ "$(head -c 8 "$LINUX")" != ANDROID! ]; then
    echo "tater-twrp-handoff: no valid Linux image; leaving TWRP installed"
    exit 1
fi
length=$(wc -c < "$LINUX")
wanted=$(md5sum "$LINUX" | cut -d' ' -f1)
echo "tater-twrp-handoff: restoring Linux ($length bytes)"
dd if="$LINUX" of=$REC bs=1048576 2>/dev/null
sync
actual=$(head -c "$length" $REC | md5sum | cut -d' ' -f1)
if [ "$actual" != "$wanted" ]; then
    echo "tater-twrp-handoff: Linux read-back failed; restoring TWRP"
    restore_twrp || echo "tater-twrp-handoff: WARNING: TWRP read-back also failed"
    exit 1
fi

arm_linux() {
    # TWRP's toybox dd disables the notrunc/sync conversion flags. Exact byte counts update
    # only the intended fields of the block device and work in this recovery.
    printf 'boot-recovery' | dd of=$MISC bs=13 count=1 2>/dev/null
    printf 'TECHO5-TRIES 0 twrp handoff\n' | dd of=$MISC bs=1 seek=7168 2>/dev/null
    sync
    [ "$(head -c 13 $MISC 2>/dev/null)" = boot-recovery ]
}

if ! arm_linux; then
    echo "tater-twrp-handoff: ERROR: Linux boot request did not stick"
    cp $TMP $S/twrp-handoff.log 2>/dev/null || true
    exit 1
fi
echo "tater-twrp-handoff: Linux restored, armed, and verified; TWRP remains active in RAM"
cp $TMP $S/twrp-handoff.log 2>/dev/null || true
: > $S/twrp-handoff.ready
'''


def _pad4(value):
    return (value + 3) & ~3


def _newc_record(magic, fields, name, data):
    """Return one newc record, preserving metadata supplied by fields."""
    name_bytes = name.encode() + b'\0'
    values = list(fields)
    values[6] = len(data)
    values[11] = len(name_bytes)
    values[12] = sum(data) & 0xffffffff if magic == b'070702' else 0
    header = magic + b''.join(b'%08X' % value for value in values)
    record = header + name_bytes
    record += b'\0' * (_pad4(len(record)) - len(record))
    record += data
    record += b'\0' * (_pad4(len(record)) - len(record))
    return record


def _patch_newc(raw, replacements, additions):
    """Replace and append regular files in a single newc initramfs."""
    out = bytearray()
    seen = set()
    offset = 0
    next_inode = 0x7a7000
    while offset + 110 <= len(raw):
        magic = raw[offset:offset + 6]
        if magic not in (b'070701', b'070702'):
            fail('TWRP ramdisk is not a newc archive at byte %d' % offset)
        fields = [int(raw[offset + 6 + index * 8:offset + 14 + index * 8], 16)
                  for index in range(13)]
        name_size, file_size = fields[11], fields[6]
        name_start = offset + 110
        name_end = name_start + name_size
        if name_end > len(raw) or not raw[name_end - 1:name_end] == b'\0':
            fail('TWRP ramdisk has a damaged newc filename')
        name = raw[name_start:name_end - 1].decode()
        data_start = _pad4(name_end)
        data_end = data_start + file_size
        if data_end > len(raw):
            fail('TWRP ramdisk has a truncated %s entry' % name)
        data = raw[data_start:data_end]
        next_offset = _pad4(data_end)

        if name == 'TRAILER!!!':
            for added_name, (mode, added_data) in additions.items():
                if added_name in seen:
                    fail('TWRP ramdisk already contains %s' % added_name)
                added_fields = [next_inode, 0o100000 | mode, 0, 0, 1, 0,
                                len(added_data), 0, 0, 0, 0, 0, 0]
                out.extend(_newc_record(b'070701', added_fields, added_name, added_data))
                next_inode += 1
            out.extend(_newc_record(magic, fields, name, data))
            missing = set(replacements) - seen
            if missing:
                fail('TWRP ramdisk is missing %s' % ', '.join(sorted(missing)))
            return bytes(out)

        seen.add(name)
        if name in replacements:
            data = replacements[name](data)
        out.extend(_newc_record(magic, fields, name, data))
        offset = next_offset
    fail('TWRP ramdisk has no newc trailer')


def _read_boot_image(path):
    with open(path, 'rb') as source:
        image = source.read()
    if image[:8] != b'ANDROID!':
        fail('%s is not an Android boot image' % path)
    kernel_size, _, ramdisk_size, _, second_size, _, _, page_size, header_version = struct.unpack(
        '<9I', image[8:44])
    if header_version != 0 or second_size:
        fail('%s uses an unsupported Android boot image header' % path)
    rounded = lambda value: (value + page_size - 1) // page_size * page_size
    header = bytearray(image[:page_size])
    kernel = image[page_size:page_size + kernel_size]
    ramdisk_start = page_size + rounded(kernel_size)
    ramdisk = image[ramdisk_start:ramdisk_start + ramdisk_size]
    if len(kernel) != kernel_size or len(ramdisk) != ramdisk_size:
        fail('%s is a truncated Android boot image' % path)
    return header, kernel, ramdisk, page_size


def _write_boot_image(header, kernel, ramdisk, page_size, out):
    rounded = lambda value: (value + page_size - 1) // page_size * page_size
    struct.pack_into('<I', header, 8, len(kernel))
    struct.pack_into('<I', header, 16, len(ramdisk))
    struct.pack_into('<I', header, 24, 0)
    digest = hashlib.sha1()
    for blob in (kernel, ramdisk, b'', b''):
        digest.update(blob)
        digest.update(struct.pack('<I', len(blob)))
    header[576:608] = digest.digest() + b'\0' * 12
    image = bytes(header)
    image += kernel + b'\0' * (rounded(len(kernel)) - len(kernel))
    image += ramdisk + b'\0' * (rounded(len(ramdisk)) - len(ramdisk))
    with open(out, 'wb') as destination:
        destination.write(image)
    return len(image)


def build_twrp_handoff_image(twrp, out, max_size=16 * 1024 * 1024):
    """Build TWRP that restores the Dot 2 Linux recovery image while running.

    Biscuit and Radar have only one recovery partition.  Their bootloader's
    Volume-Up route enters that partition, so Linux temporarily replaces
    itself with this unit's own TWRP.  The added TWRP service verifies and puts
    Linux back while TWRP continues running from RAM; the next boot is Linux.
    """
    header, kernel, compressed, page_size = _read_boot_image(twrp)
    try:
        if compressed.startswith(b'\x1f\x8b'):
            raw = gzip.decompress(compressed)
        else:
            raw = lzma.decompress(compressed, format=lzma.FORMAT_AUTO)
    except (OSError, lzma.LZMAError) as error:
        fail('cannot decompress the TWRP ramdisk: %s' % error)

    def add_service(contents):
        if b'service tater-restore-linux ' in contents:
            fail('TWRP ramdisk already contains the Tater handoff service')
        if not contents.endswith(b'\n'):
            contents += b'\n'
        return contents + TWRP_HANDOFF_SERVICE

    patched = _patch_newc(
        raw,
        {'init.recovery.mt8163.rc': add_service},
        {'sbin/tater-restore-linux.sh': (0o755, TWRP_HANDOFF_SCRIPT)},
    )
    ramdisk = lzma.compress(patched, format=lzma.FORMAT_ALONE, preset=9)
    size = _write_boot_image(header, kernel, ramdisk, page_size, out)
    if size > max_size:
        fail('TWRP handoff image does not fit the recovery partition')
    return size


def build_boot_image(recovery, out, alpine_tgz, busybox, wmtup, apks, kernel=None, board='biscuit', wpa_supplicant=None):
    """A unit's boot image: its own backup's header and kernel (the recovery partition's on the Dot 2
    boards, without a kernel given; the booted slot's stock kernel on the Echo Dot 3), the rescue initramfs
    on Alpine's base, and the slot, network and TWRP tools."""
    j = os.path.join
    linux = j(repo_root(), 'tools', 'linux')
    donut = board == 'donut'
    mk = [sys.executable, j(linux, 'mkimage.py'), '--kernel-image', recovery, '--rootfs', alpine_tgz,
          '--init', j(linux, 'init-donut' if donut else 'init'), '--add', busybox + '=/bin/busybox.static',
          '--cmdline-drop', 'skip_initramfs', '--cmdline-drop', 'root=', '--cmdline-drop', 'dm=',
          '--cmdline-append', 'techo5.stay_minutes=15', '-o', out]
    if wmtup:
        mk += ['--add', wmtup + '=/usr/local/bin/wmtup']
    if donut:
        mk += ['--ramdisk-addr', DONUT_RAMDISK_ADDR]
    if kernel:
        mk += ['--kernel', kernel]
    for apk in sorted(os.listdir(apks)):
        if not apk.endswith('.apk'):
            continue
        if donut and apk.startswith('wpa_supplicant-'):
            # Alpine's 2.11 never completes a handshake with the Dot 3's Wi-Fi driver; ours does
            # (tools/linux/wpa-patches/0100-donut-no-wmm-replay-counters.patch).
            swapped = out + '.wpa_supplicant.tar.gz'
            with_member(j(apks, apk), 'sbin/wpa_supplicant', wpa_supplicant, swapped)
            mk += ['--apk', swapped]
            continue
        mk += ['--apk', j(apks, apk)]
    for t in ('slotctl', 'techo5-net', 'wifi-set', 'to-twrp', 'techo5-firewall'):
        mk += ['--script', j(linux, 'rootfs', 'usr', 'local', 'sbin', t) + '=/usr/local/sbin/' + t]
    if subprocess.run(mk).returncode != 0:
        fail('building the boot image failed')


if __name__ == '__main__':
    # release-dot.ps1 checks each kernel it publishes is the board's: python tools/dotimage.py board <file>
    # prints the board, with " 6.1" after it for a Linux 6.1 kernel.
    if len(sys.argv) != 3 or sys.argv[1] != 'board':
        sys.exit('usage: dotimage.py board <zImage-dtb>')
    b = kernel_board(sys.argv[2])
    print((b + (' 6.1' if kernel_is_61(sys.argv[2], b) else '')) if b else '')
