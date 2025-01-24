# Copyright 2022 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import math

import attrs

from subiquity.common.types.storage import GuidedResizeValues
from subiquity.models.filesystem import GiB, MiB, align_down, align_up

BIOS_GRUB_SIZE_BYTES = 1 * MiB
PREP_GRUB_SIZE_BYTES = 8 * MiB


@attrs.define(auto_attribs=True)
class PartitionScaleFactors:
    minimum: int
    priority: int
    maximum: int


uefi_scale = PartitionScaleFactors(minimum=538 * MiB, priority=538, maximum=1075 * MiB)
bootfs_scale = PartitionScaleFactors(
    minimum=1792 * MiB, priority=1024, maximum=2048 * MiB
)
rootfs_scale = PartitionScaleFactors(minimum=900 * MiB, priority=10000, maximum=-1)


def scale_partitions(all_factors, available_space):
    """for the list of scale factors, provide list of scaled partition size.
    Assumes at most one scale factor with maximum==-1, and
    available_space is at least as big as the sum of all partition minimums.
    The scale factor with maximum==-1 is given all remaining disk space."""
    ret = []
    sum_priorities = sum([factor.priority for factor in all_factors])
    for cur in all_factors:
        scaled = int((available_space / sum_priorities) * cur.priority)
        if scaled < cur.minimum:
            ret.append(cur.minimum)
        elif scaled > cur.maximum:
            ret.append(cur.maximum)
        else:
            ret.append(scaled)
    if -1 in ret:
        used = sum(filter(lambda x: x != -1, ret))
        idx = ret.index(-1)
        ret[idx] = available_space - used
    return ret


def get_efi_size(available_space):
    all_factors = (uefi_scale, bootfs_scale, rootfs_scale)
    return scale_partitions(all_factors, available_space)[0]


def get_bootfs_size(available_space):
    all_factors = (uefi_scale, bootfs_scale, rootfs_scale)
    return scale_partitions(all_factors, available_space)[1]


# Calculation of guided resize values is primarly focues on finding a suggested
# midpoint - what will we resize down to while leaving some room for the
# existing partition and the new install?
# 1) Obtain the suggested size for the install
#    (see calculate_suggested_install_min)
# 2) Look at the output from the resize tool to see the theoretical minimum
#    size of the partition we might resize, and pad it a bit (2 GiB or 25%)
# 3) Subtract the two minimum suggested sizes to obtain the space that we can
#    decide to keep with the existing partition, or allocate to the new install
# 4) Assume that the installs will grow proportionally to their minimum sizes,
#    and split according to the ratio of the minimum sizes
def calculate_guided_resize(
    part_min: int, part_size: int, install_min: int, part_align: int = MiB
) -> GuidedResizeValues:
    if part_min < 0:
        return None

    part_size = align_up(part_size, part_align)

    other_room_to_grow = max(2 * GiB, math.ceil(0.25 * part_min))
    padded_other_min = part_min + other_room_to_grow
    other_min = min(align_up(padded_other_min, part_align), part_size)

    plausible_free_space = part_size - other_min
    if plausible_free_space < install_min:
        return None

    other_max = align_down(part_size - install_min, part_align)
    resize_window = other_max - other_min
    ratio = other_min / (other_min + install_min)
    raw_recommended = math.ceil(resize_window * ratio) + other_min
    recommended = align_up(raw_recommended, part_align)
    return GuidedResizeValues(
        install_max=plausible_free_space,
        minimum=other_min,
        recommended=recommended,
        maximum=other_max,
    )


# Factors for suggested minimum install size:
# 1) Source minimum - The minimum reported as part of source selection.  This
#    is absolute bare minimum information to get bits on the disk and doesn’t
#    factor in filesystem overhead.   Obtained from the size value of the
#    chosen source as found at /casper/install-sources.yaml.
# 2) Room for boot - we employ a scaling system to help select the recommended
#    size of a dedicated /boot and/or efi system partition (see above).  If
#    /boot is not actually a separate partition, this space needs to be
#    accounted for as part of the planned rootfs size.
# 3) room for esp - similar to boot.  Included in all calculations, even if
#    we're not UEFI boot.
# 4) Room to grow - while meaningful work can sometimes be possible on a full
#    disk, it’s not the sort of thing to suggest in a guided install.
#    Suggest for room to grow max(2GiB, 50% of source minimum).
def calculate_suggested_install_min(source_min: int, part_align: int = MiB) -> int:
    room_for_boot = bootfs_scale.minimum
    room_for_esp = uefi_scale.minimum
    room_to_grow = max(2 * GiB, math.ceil(0.5 * source_min))
    total = source_min + room_for_boot + room_for_esp + room_to_grow
    return align_up(total, part_align)


# Scale the usage of the vg to leave room for snapshots and such. We should
# use more of a smaller disk to avoid the user running into out of space errors
# earlier than they probably expect to.
def scaled_rootfs_size(available: int):
    if available < 10 * (1 << 30):
        # Use all of a small (<10G) disk.
        return available
    elif available < 20 * (1 << 30):
        # Use 10G of a smallish (<20G) disk.
        return 10 * (1 << 30)
    elif available < 200 * (1 << 30):
        # Use half of a larger (<200G) disk.
        return available // 2
    else:
        # Use at most 100G of a large disk.
        return 100 * (1 << 30)
