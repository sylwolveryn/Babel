//! Reading the buffer through the addon's own table, instead of hunting for it.
//!
//! The addon parks a constant in its saved table. A constant can be searched for
//! at leisure — it does not move while you look — and a Lua table's storage does
//! not move at all while the table does not rehash, which the addon prevents by
//! declaring every key at load. So the slot holding the buffer's pointer sits
//! beside that constant, and reading one pointer gives the current string
//! whatever address it has wandered to.
//!
//! The 3.3.5a client is a 32-bit process running Lua 5.1, so a pointer is four
//! bytes and the whole address space sits below 4 GB. On that build a TValue is
//! sixteen bytes (an eight-byte value union, the type tag, padding) and a
//! TString header is sixteen bytes too, which is why `skip` is tried at 16 first.
//!
//! Proven on a live game before any of it was written: one slot, six reads over
//! twelve seconds, six different string addresses, every one a valid buffer.

use std::sync::Mutex;

#[cfg(windows)]
use rayon::prelude::*;
#[cfg(windows)]
use windows::Win32::Foundation::{CloseHandle, HANDLE};

use crate::markers::{find_content_start, rank, MARKER, MARKER_END};
#[cfg(windows)]
use crate::process::{get_pool, get_readable_regions, open_process, owned_process, read_memory, CHUNK_SIZE, MAX_BUF_READ};

/// The number the addon parks in its saved table and never changes.
///
/// Everything else about the buffer moves. It is a Lua string, so every rebuild
/// allocates a new one somewhere else — fourteen rebuilds landed in fourteen
/// regions twenty gigabytes apart — and searching for something that moves while
/// you search is why every version of this scanner has either burned a core or
/// gone deaf. Measured: the previous release, 48% of one core and five messages
/// a minute.
///
/// A constant can be searched for at leisure. And a Lua table's storage does not
/// move while the table does not rehash, which the addon prevents by declaring
/// all its keys at load. So the slot holding the buffer's pointer sits a few
/// dozen bytes from this number, and reading it gives the current string — no
/// search, at any point, ever again.
const ANCHOR_VALUE: f64 = 8675309123457.0;

/// How long the pulse may stand still at the slot before the table is presumed
/// dead. Three heartbeats: the addon rebuilds at least every two seconds, so
/// six is comfortably beyond doubt and still eight times faster than noticing
/// by the pointer breaking.
pub(crate) const ANCHOR_MAX_QUIET_MS: u64 = 6_000;

/// How far either side of the anchor to look for that slot. The proof found it
/// 112 bytes below.
const ANCHOR_WINDOW: usize = 8192;

/// Pointer width in the game process. 3.3.5a's Wow.exe is 32-bit.
pub(crate) const PTR_SIZE: usize = 4;

/// The highest address a 32-bit process can hand out (with large-address-aware
/// set, which many 3.3.5a installs patch in).
const MAX_TARGET_ADDRESS: usize = 0xFFFF_FFFF;

/// Lua string header sizes worth trying, most likely first. 16 is the 32-bit
/// Lua 5.1 TString; the rest cover allocator padding.
const STRING_HEADER_SKIPS: [usize; 6] = [16, 20, 24, 12, 32, 0];

fn read_pointer(bytes: &[u8]) -> Option<usize> {
    Some(u32::from_le_bytes(bytes.get(..PTR_SIZE)?.try_into().ok()?) as usize)
}

fn plausible_pointer(pointer: usize) -> bool {
    (0x10000..=MAX_TARGET_ADDRESS).contains(&pointer)
}

pub(crate) struct Anchor {
    pub(crate) pid: u32,
    /// The pulse last read through this slot, and when. A reload leaves the old
    /// table in memory with its buffer frozen at the last thing said before it,
    /// and that reads exactly like a working slot in a quiet chat — the same
    /// confusion the buffer itself caused, one level up.
    pub(crate) last_pulse: i64,
    pub(crate) last_pulse_ms: u64,
    /// Address of the pointer-sized slot holding the pointer to the buffer string.
    pub(crate) slot: usize,
    /// Distance from that pointer to the text — the Lua string header.
    pub(crate) skip: usize,
    pub(crate) handle: isize,
}

pub(crate) static ANCHOR: Mutex<Option<Anchor>> = Mutex::new(None);

// ── Reading through the addon's table ────────────────────────────────────────

/// Read the buffer the slot currently points at.
#[cfg(windows)]
pub(crate) fn read_via_slot(handle: HANDLE, slot: usize, skip: usize) -> Option<Vec<u8>> {
    let mut pointer_bytes = [0u8; PTR_SIZE];
    if !read_memory(handle, slot, &mut pointer_bytes) {
        return None;
    }
    let pointer = read_pointer(&pointer_bytes)?;
    if !plausible_pointer(pointer) {
        return None;
    }
    let mut raw = vec![0u8; MAX_BUF_READ];
    if !read_memory(handle, pointer + skip, &mut raw) {
        return None;
    }
    let cs = find_content_start(&raw)?;
    let ep = raw[cs..].windows(MARKER_END.len()).position(|w| w == MARKER_END)?;
    Some(raw[cs..cs + ep].to_vec())
}

/// Find the anchor, then the slot beside it. Slow, and done once.
#[cfg(windows)]
pub(crate) fn locate_anchor(pid: u32) -> Option<(usize, usize)> {
    let handle = open_process(pid)?;
    let needle = ANCHOR_VALUE.to_le_bytes();
    let regions = get_readable_regions(handle);

    let anchors: Mutex<Vec<usize>> = Mutex::new(Vec::new());
    get_pool().install(|| {
        regions.par_iter().for_each_init(
            // Owned, so each worker's handle is closed when the thread is
            // done with it rather than leaked four at a time per scan.
            || owned_process(pid),
            |h, region| {
                let Some(owned) = h else { return };
                let handle = owned.0;
                let mut offset = 0usize;
                let mut chunk = vec![0u8; CHUNK_SIZE];
                while offset < region.size {
                    let size = CHUNK_SIZE.min(region.size - offset);
                    let base = region.base + offset;
                    offset += size;
                    let buf = &mut chunk[..size];
                    if !read_memory(handle, base, buf) { continue; }
                    // Four-byte steps: a 32-bit allocator only promises four-byte
                    // alignment, so the double may not sit on an eight-byte line.
                    let mut at = 0usize;
                    while at + 8 <= buf.len() {
                        if buf[at..at + 8] == needle {
                            anchors.lock().unwrap().push(base + at);
                        }
                        at += 4;
                    }
                }
            },
        );
    });

    let anchors = anchors.into_inner().ok()?;

    // Every candidate, then the liveliest — not the first that looks right.
    //
    // A reload leaves the previous table in memory until the collector gets to
    // it, so there can be two of these, and the dead one answers every question
    // the same way the live one does. It cost a hundred and eighty seconds of
    // silence to learn that twice.
    let mut best: Option<((i64, i32), usize, usize)> = None;
    for anchor in anchors {
        let low = anchor.saturating_sub(ANCHOR_WINDOW);
        let mut window = vec![0u8; ANCHOR_WINDOW * 2];
        if !read_memory(handle, low, &mut window) { continue; }
        for offset in (0..window.len().saturating_sub(PTR_SIZE)).step_by(PTR_SIZE) {
            let Some(pointer) = read_pointer(&window[offset..]) else { continue };
            if !plausible_pointer(pointer) { continue; }
            for skip in STRING_HEADER_SKIPS {
                let mut head = [0u8; 10];
                if !read_memory(handle, pointer + skip, &mut head) || head != *MARKER {
                    continue;
                }
                let slot = low + offset;
                if let Some(content) = read_via_slot(handle, slot, skip) {
                    let score = rank(&content);
                    if best.as_ref().is_none_or(|(b, _, _)| score > *b) {
                        best = Some((score, slot, skip));
                    }
                }
                break;
            }
        }
    }
    unsafe { let _ = CloseHandle(handle); }
    best.map(|(_, slot, skip)| (slot, skip))
}

#[cfg(not(windows))]
pub(crate) fn locate_anchor(_pid: u32) -> Option<(usize, usize)> { None }


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_pointer_is_four_little_endian_bytes() {
        assert_eq!(read_pointer(&[0x78, 0x56, 0x34, 0x12, 0xFF, 0xFF]), Some(0x1234_5678));
        assert_eq!(read_pointer(&[0x01, 0x02, 0x03]), None);
    }

    #[test]
    fn only_addresses_a_32_bit_process_can_own_are_plausible() {
        assert!(!plausible_pointer(0));
        assert!(!plausible_pointer(0xFFFF));
        assert!(plausible_pointer(0x0040_0000));
        assert!(plausible_pointer(0xFFFF_FFFF));
        assert!(!plausible_pointer(0x1_0000_0000));
    }

    #[test]
    fn the_32_bit_lua_string_header_is_tried_first() {
        assert_eq!(STRING_HEADER_SKIPS[0], 16);
    }
}
