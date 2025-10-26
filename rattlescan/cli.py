import os
import sys
import hashlib
import magic
import shutil
import math
from datetime import datetime
from collections import OrderedDict
from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import mutagen
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    import pytermgui as ptg
    PTG_AVAILABLE = True
except ImportError:
    PTG_AVAILABLE = False

def calculate_file_hashes(fp, bs=65536):
    h = OrderedDict()
    md5, sha1, sha256 = hashlib.md5(), hashlib.sha1(), hashlib.sha256()
    try:
        with open(fp, 'rb') as f:
            while data := f.read(bs):
                md5.update(data)
                sha1.update(data)
                sha256.update(data)
        h['MD5'], h['SHA-1'], h['SHA-256'] = md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()
    except Exception as e:
        h['Error'] = f"Could not calculate hashes: {e}"
    return h

def get_file_type_info(fp):
    info = OrderedDict()
    try:
        mime_type = magic.Magic(mime=True).from_file(fp)
        info['MIME Type'] = mime_type
        info['File Type Description'] = magic.Magic().from_file(fp)
        ext = Path(fp).suffix.lower()
        expected = {'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'], 'application/pdf': ['.pdf'], 'text/plain': ['.txt'], 'application/zip': ['.zip']}
        if mime_type in expected and ext not in expected[mime_type]:
            info['⚠ Extension Mismatch' if ext else '⚠ No Extension'] = f"File is {mime_type} but has {ext or 'no'} extension"
    except ImportError:
        info['Note'] = "python-magic not installed. Install with: pip install python-magic"
    except Exception as e:
        info['Error'] = str(e)
    return info

def human_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def mode_to_string(mode):
    import stat
    p = []
    for u in [(stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR), (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP), (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH)]:
        p.extend(['r' if mode & u[0] else '-', 'w' if mode & u[1] else '-', 'x' if mode & u[2] else '-'])
    return ''.join(p)

def get_file_system_metadata(fp):
    s = os.stat(fp)
    m = OrderedDict()
    m['Filename'], m['Full Path'] = Path(fp).name, os.path.abspath(fp)
    m['File Size'] = f"{s.st_size:,} bytes ({human_readable_size(s.st_size)})"
    m['Permissions (Octal)'], m['Permissions (String)'] = oct(s.st_mode)[-4:], mode_to_string(s.st_mode)
    m['Inode Number'], m['Device ID'], m['Hard Links'] = s.st_ino, s.st_dev, s.st_nlink
    try:
        m['User ID'], m['Group ID'] = s.st_uid, s.st_gid
    except AttributeError:
        pass
    fmt_ts = lambda ts: f"{datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (Unix: {int(ts)})"
    m['Birth Time'] = fmt_ts(s.st_birthtime) if hasattr(s, 'st_birthtime') else "N/A"
    m['Last Modified (mtime)'], m['Last Accessed (atime)'], m['Metadata Changed (ctime)'] = fmt_ts(s.st_mtime), fmt_ts(s.st_atime), fmt_ts(s.st_ctime)
    now = datetime.now().timestamp()
    m['Age (days)'] = f"{(now - s.st_mtime) / 86400:.2f}"
    if abs(s.st_mtime - s.st_atime) < 1:
        m['⚠ Timestamp Note'] = "Access and modification times are nearly identical"
    if s.st_mtime > now:
        m['⚠ Future Timestamp'] = "Modification time is in the future!"
    return m

def get_image_exif_metadata(fp):
    if not PIL_AVAILABLE:
        return {"Note": "Pillow library not installed. Cannot extract EXIF metadata."}
    exif = OrderedDict()
    try:
        with Image.open(fp) as img:
            exif['Image Format'], exif['Image Mode'], exif['Image Size'] = img.format, img.mode, f"{img.size[0]} x {img.size[1]} pixels"
            if not hasattr(img, '_getexif') or img._getexif() is None:
                exif['EXIF Status'] = "No EXIF data found"
                return exif
            for tid, val in img._getexif().items():
                tag = TAGS.get(tid, tid)
                if tag == 'GPSInfo':
                    exif['GPS Data'] = str({GPSTAGS.get(gtid, gtid): gval for gtid, gval in val.items()})
                    continue
                if isinstance(val, bytes):
                    val = f"<Binary Data, {len(val)} bytes>" if len(val) > 100 else val.decode('utf-8', errors='ignore')
                elif isinstance(val, str) and len(val) > 100:
                    val = val[:100] + "..."
                exif[tag] = val
            return exif
    except IOError:
        return None
    except Exception as e:
        return {"Error": f"EXIF extraction error: {e}"}

def get_pdf_metadata(fp):
    if not PYPDF2_AVAILABLE:
        return {"Note": "PyPDF2 not installed. Install with: pip install PyPDF2"}
    m = OrderedDict()
    try:
        with open(fp, 'rb') as f:
            pdf = PyPDF2.PdfReader(f)
            m['Number of Pages'], m['Encrypted'] = len(pdf.pages), pdf.is_encrypted
            if pdf.metadata:
                m.update({k.lstrip('/'): v for k, v in pdf.metadata.items()})
    except Exception as e:
        m['Error'] = f"PDF extraction error: {e}"
    return m

def get_audio_video_metadata(fp):
    if not MUTAGEN_AVAILABLE:
        return {"Note": "mutagen not installed. Install with: pip install mutagen"}
    m = OrderedDict()
    try:
        audio = mutagen.File(fp)
        if audio is None:
            return {"Note": "Not a recognized audio/video file"}
        if hasattr(audio.info, 'length'):
            m['Duration'] = f"{audio.info.length:.2f} seconds"
        if hasattr(audio.info, 'bitrate'):
            m['Bitrate'] = f"{audio.info.bitrate // 1000} kbps"
        if hasattr(audio.info, 'sample_rate'):
            m['Sample Rate'] = f"{audio.info.sample_rate} Hz"
        if hasattr(audio.info, 'channels'):
            m['Channels'] = audio.info.channels
        if audio.tags:
            m.update({str(k): str(v) for k, v in audio.tags.items()})
    except Exception as e:
        m['Error'] = f"Audio/video extraction error: {e}"
    return m

def analyze_file_entropy(fp, ss=1024*1024):
    try:
        with open(fp, 'rb') as f:
            data = f.read(ss)
        if len(data) == 0:
            return {"Entropy": "N/A (empty file)"}
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        ent = -sum((c/len(data)) * math.log2(c/len(data)) for c in freq if c > 0)
        r = OrderedDict()
        r['Entropy'] = f"{ent:.4f} bits/byte"
        r['Analysis'] = "High entropy - possibly encrypted or compressed" if ent > 7.5 else "Low entropy - likely plain text or repetitive data" if ent < 4.0 else "Medium entropy - typical binary data"
        return r
    except Exception as e:
        return {"Error": f"Entropy calculation error: {e}"}

def clean_image_metadata(fp, op=None):
    if not PIL_AVAILABLE:
        return False, "Pillow library not available"
    try:
        op = op or fp
        with Image.open(fp) as img:
            clean = Image.new(img.mode, img.size)
            clean.putdata(list(img.getdata()))
            clean.save(op)
        return True, "Metadata cleaned successfully"
    except Exception as e:
        return False, f"Error cleaning image metadata: {e}"

def clean_pdf_metadata(fp, op=None):
    if not PYPDF2_AVAILABLE:
        return False, "PyPDF2 library not available"
    try:
        op = op or fp + ".cleaned.pdf"
        with open(fp, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            writer = PyPDF2.PdfWriter()
            for pg in reader.pages:
                writer.add_page(pg)
            with open(op, 'wb') as out:
                writer.write(out)
        return True, f"Cleaned PDF saved to: {op}"
    except Exception as e:
        return False, f"Error cleaning PDF metadata: {e}"

def clean_audio_metadata(fp, op=None):
    if not MUTAGEN_AVAILABLE:
        return False, "mutagen library not available"
    try:
        op = op or fp + ".cleaned" + Path(fp).suffix
        shutil.copy2(fp, op)
        audio = mutagen.File(op)
        if audio and audio.tags:
            audio.delete()
            audio.save()
            return True, f"Cleaned audio saved to: {op}"
        return True, "No metadata tags found to remove"
    except Exception as e:
        return False, f"Error cleaning audio metadata: {e}"

def secure_wipe_file(fp, passes=3):
    try:
        sz = os.path.getsize(fp)
        with open(fp, 'r+b') as f:
            for i in range(passes):
                f.seek(0)
                f.write(os.urandom(sz) if i != 1 else bytes([0xFF] * sz))
                f.flush()
                os.fsync(f.fileno())
        os.remove(fp)
        return True, f"File securely wiped with {passes} passes"
    except Exception as e:
        return False, f"Error during secure wipe: {e}"

def interactive_clean_menu_ptg(fp):
    with ptg.WindowManager() as manager:
        result = {'action': 'skip'}
        
        def on_clean_copy(_):
            result['action'] = 'clean_copy'
            manager.stop()
        
        def on_clean_overwrite(_):
            result['action'] = 'clean_overwrite'
            manager.stop()
        
        def on_secure_wipe(_):
            result['action'] = 'secure_wipe'
            manager.stop()
        
        def on_skip(_):
            result['action'] = 'skip'
            manager.stop()
        
        window = ptg.Window(
            "[bold 210]Metadata Cleaning & Secure Wipe Options[/]",
            "",
            ptg.Button("Clean metadata (create cleaned copy)", onclick=on_clean_copy),
            ptg.Button("[yellow]Clean metadata (overwrite original) ⚠[/]", onclick=on_clean_overwrite),
            ptg.Button("[red]Secure wipe file (DOD 5220.22-M, 3-pass) ⚠⚠[/]", onclick=on_secure_wipe),
            "",
            ptg.Button("Skip cleaning", onclick=on_skip),
            width=60,
        )
        
        window.center()
        manager.add(window)
        manager.run()
        
        return result['action']

def interactive_clean_menu_fallback(fp):
    print("\n" + "=" * 70)
    print("  METADATA CLEANING & SECURE WIPE OPTIONS")
    print("=" * 70)
    print("\n[1] Clean metadata (create cleaned copy)")
    print("[2] Clean metadata (overwrite original) ⚠")
    print("[3] Secure wipe file (DOD 5220.22-M, 3-pass) ⚠⚠")
    print("[4] Skip cleaning\n")
    choice = input("Select option [1-4]: ").strip()
    if choice == '1':
        return 'clean_copy'
    elif choice == '2':
        confirm = input("\n⚠  WARNING: This will overwrite the original file. Continue? (yes/no): ").strip().lower()
        if confirm == 'yes':
            return 'clean_overwrite'
        else:
            print("Operation cancelled.")
            return 'skip'
    elif choice == '3':
        confirm = input("\n⚠⚠  DANGER: This will PERMANENTLY DELETE the file. Type 'DELETE' to confirm: ").strip()
        if confirm == 'DELETE':
            return 'secure_wipe'
        else:
            print("Operation cancelled.")
            return 'skip'
    return 'skip'

def interactive_clean_menu(fp):
    if PTG_AVAILABLE:
        return interactive_clean_menu_ptg(fp)
    else:
        return interactive_clean_menu_fallback(fp)

def perform_cleaning(fp, action):
    if action == 'skip':
        return
    ext = Path(fp).suffix.lower()
    print("\n" + "=" * 70)
    if action == 'secure_wipe':
        print("  PERFORMING SECURE WIPE")
        print("=" * 70)
        print("\nWiping file with DOD 5220.22-M standard (3 passes)...")
        succ, msg = secure_wipe_file(fp)
        if succ:
            print(f"\n✓ {msg}")
            print("✓ File has been permanently deleted")
        else:
            print(f"\n✗ {msg}")
    elif action in ['clean_copy', 'clean_overwrite']:
        print("  CLEANING METADATA")
        print("=" * 70)
        op = None if action == 'clean_overwrite' else None
        succ, msg = False, ""
        if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif']:
            if action == 'clean_copy':
                op = str(Path(fp).with_suffix('')) + '.cleaned' + ext
            succ, msg = clean_image_metadata(fp, op)
        elif ext == '.pdf':
            if action == 'clean_overwrite':
                tp = fp + '.temp.pdf'
                succ, msg = clean_pdf_metadata(fp, tp)
                if succ:
                    os.replace(tp, fp)
                    msg = "PDF metadata cleaned (original overwritten)"
            else:
                succ, msg = clean_pdf_metadata(fp)
        elif ext in ['.mp3', '.flac', '.ogg', '.m4a', '.wav']:
            if action == 'clean_copy':
                op = str(Path(fp).with_suffix('')) + '.cleaned' + ext
            succ, msg = clean_audio_metadata(fp, op)
        else:
            print(f"\n⚠  Metadata cleaning not supported for {ext} files")
            print("=" * 70)
            return
        if succ:
            print(f"\n✓ {msg}")
        else:
            print(f"\n✗ {msg}")
    print("=" * 70)

def print_metadata(md, title):
    if not md:
        return
    print("=" * 70)
    print(f"  {title.upper()}")
    print("=" * 70)
    ml = max(len(str(k)) for k in md.keys()) if md else 0
    for k, v in md.items():
        dv = str(v).replace('\n', ' ')
        if '⚠' in str(k):
            print(f"\033[93m{str(k).ljust(ml)} : {dv}\033[0m")
        else:
            print(f"{str(k).ljust(ml)} : {dv}")
    print()

def main():
    if len(sys.argv) < 2:
        print("Usage: python metadata_extractor.py <file_path> [--clean] [--wipe]")
        print("\nOptions:")
        print("  --clean    Automatically prompt for metadata cleaning after scan")
        print("  --wipe     Automatically prompt for secure file wiping after scan")
        if not PTG_AVAILABLE:
            print("\n[Note] Install pytermgui for enhanced UI: pip install pytermgui")
        sys.exit(1)
    fp = sys.argv[1]
    if not os.path.exists(fp):
        print(f"Error: File not found at path: {fp}")
        sys.exit(1)
    print("\n" + "=" * 70)
    print(f"  FORENSIC METADATA ANALYSIS")
    print(f"  File: {os.path.basename(fp)}")
    print(f"  Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")
    print_metadata(get_file_type_info(fp), "File Type Identification")
    print("Calculating file hashes...")
    print_metadata(calculate_file_hashes(fp), "Cryptographic Hashes")
    print_metadata(get_file_system_metadata(fp), "File System Metadata")
    print_metadata(analyze_file_entropy(fp), "Entropy Analysis")
    ext = Path(fp).suffix.lower()
    if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif'] and PIL_AVAILABLE:
        if exif := get_image_exif_metadata(fp):
            print_metadata(exif, "Image Metadata (EXIF)")
    elif ext == '.pdf':
        print_metadata(get_pdf_metadata(fp), "PDF Metadata")
    elif ext in ['.mp3', '.mp4', '.flac', '.ogg', '.wav', '.m4a', '.avi', '.mkv']:
        print_metadata(get_audio_video_metadata(fp), "Audio/Video Metadata")
    print("=" * 70)
    print("  ANALYSIS COMPLETE")
    print("=" * 70 + "\n")
    if action := interactive_clean_menu(fp):
        perform_cleaning(fp, action)

if __name__ == "__main__":
    main()
