"""Create a clickable EMA shortcut.

    python create_shortcut.py              # Desktop shortcut
    python create_shortcut.py --start-menu # also add it to the Start Menu / applications
"""

import base64
import os
import stat
import subprocess
import sys

from ema import APP_ID

ROOT = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(ROOT, "EMA.pyw")
ICON_DIR = os.path.join(ROOT, "ema", "assets")

# Gives the shortcut the same AppUserModelID as the running program, so the taskbar
# button groups with the shortcut and "Pin to taskbar" keeps the EMA icon.
_APP_ID_HELPER = r"""
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

public static class EmaShortcut {
    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    class ShellLink {}

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
    interface IPropertyStore {
        void GetCount(out uint count);
        void GetAt(uint index, out PropertyKey key);
        void GetValue(ref PropertyKey key, [Out] PropVariant value);
        void SetValue(ref PropertyKey key, [In] PropVariant value);
        void Commit();
    }

    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct PropertyKey { public Guid fmtid; public uint pid; }

    [StructLayout(LayoutKind.Explicit, Size = 24)]
    class PropVariant {
        [FieldOffset(0)] public ushort vt;
        [FieldOffset(8)] public IntPtr pointer;
    }

    [DllImport("shell32.dll")]
    static extern void SHChangeNotify(int eventId, uint flags, IntPtr item1, IntPtr item2);

    public static void SetAppId(string path, string appId) {
        var link = new ShellLink();
        ((IPersistFile)link).Load(path, 2);
        var key = new PropertyKey { fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid = 5 };
        var value = new PropVariant { vt = 31, pointer = Marshal.StringToCoTaskMemUni(appId) };
        try {
            var store = (IPropertyStore)link;
            store.SetValue(ref key, value);
            store.Commit();
            ((IPersistFile)link).Save(path, true);
        } finally {
            Marshal.FreeCoTaskMem(value.pointer);
        }
        SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero);
    }
}
"""


def _ps_quote(text):
    return "'" + text.replace("'", "''") + "'"


def windows_shortcut(folder_id):
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    script = f"""
$path = Join-Path ([Environment]::GetFolderPath({_ps_quote(folder_id)})) 'EMA.lnk'
if (Test-Path $path) {{ Remove-Item $path }}
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
$s.TargetPath = {_ps_quote(pythonw)}
$s.Arguments = {_ps_quote(chr(34) + LAUNCHER + chr(34))}
$s.WorkingDirectory = {_ps_quote(ROOT)}
$s.IconLocation = {_ps_quote(os.path.join(ICON_DIR, 'ema.ico') + ',0')}
$s.Description = 'EMA - brain slice analysis'
$s.Save()
Add-Type -TypeDefinition {_ps_quote(_APP_ID_HELPER)}
[EmaShortcut]::SetAppId($path, {_ps_quote(APP_ID)})
try {{ & ie4uinit.exe -show }} catch {{ }}
$path
"""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-EncodedCommand", encoded],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def mac_shortcut():
    path = os.path.expanduser("~/Desktop/EMA.command")
    with open(path, "w") as f:
        f.write(f'#!/bin/sh\ncd "{ROOT}"\nexec "{sys.executable}" -m ema\n')
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def linux_shortcut(folder):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "ema.desktop")
    with open(path, "w") as f:
        f.write(
            "[Desktop Entry]\nType=Application\nName=EMA\n"
            f"Exec={sys.executable} -m ema\nPath={ROOT}\n"
            f"Icon={os.path.join(ICON_DIR, 'ema.png')}\nTerminal=false\n"
        )
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def main():
    start_menu = "--start-menu" in sys.argv
    if sys.platform == "win32":
        created = [windows_shortcut("Desktop")]
        if start_menu:
            created.append(windows_shortcut("Programs"))
    elif sys.platform == "darwin":
        created = [mac_shortcut()]
    else:
        created = [linux_shortcut(os.path.expanduser("~/Desktop"))]
        if start_menu:
            created.append(linux_shortcut(os.path.expanduser("~/.local/share/applications")))
    for path in created:
        print(f"Created {path}")


if __name__ == "__main__":
    main()
