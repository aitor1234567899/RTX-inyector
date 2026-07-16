"""
GTA V DLL Injector
"""

import ctypes
import json
import os
import sys
import struct
import threading
import time
import webbrowser
from ctypes import c_void_p, c_char_p, c_wchar_p, c_wchar, Structure, POINTER, sizeof, byref, cast
from tkinter import *
from tkinter import ttk, filedialog, messagebox
import tkinter as tk

from ctypes.wintypes import (
    BOOL, DWORD, HANDLE, HWND, UINT, WORD, LONG, ULONG,
    LPVOID, LPCVOID, LPCSTR, LPWSTR, HINSTANCE, HMODULE
)

kernel32 = ctypes.WinDLL('kernel32.dll')
user32 = ctypes.WinDLL('user32.dll')

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x4
PAGE_EXECUTE_READWRITE = 0x40
MEM_RELEASE = 0x8000
TH32CS_SNAPPROCESS = 0x00000002

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [DWORD, BOOL, DWORD]
OpenProcess.restype = HANDLE

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [HANDLE]
CloseHandle.restype = BOOL

VirtualAllocEx = kernel32.VirtualAllocEx
VirtualAllocEx.argtypes = [HANDLE, LPVOID, ctypes.c_size_t, DWORD, DWORD]
VirtualAllocEx.restype = LPVOID

VirtualFreeEx = kernel32.VirtualFreeEx
VirtualFreeEx.argtypes = [HANDLE, LPVOID, ctypes.c_size_t, DWORD]
VirtualFreeEx.restype = BOOL

WriteProcessMemory = kernel32.WriteProcessMemory
WriteProcessMemory.argtypes = [HANDLE, LPVOID, LPCVOID, ctypes.c_size_t, POINTER(ctypes.c_size_t)]
WriteProcessMemory.restype = BOOL

CreateRemoteThread = kernel32.CreateRemoteThread
CreateRemoteThread.argtypes = [HANDLE, LPVOID, ctypes.c_size_t, LPVOID, LPVOID, DWORD, POINTER(DWORD)]
CreateRemoteThread.restype = HANDLE

WaitForSingleObject = kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = [HANDLE, DWORD]
WaitForSingleObject.restype = DWORD

GetLastError = kernel32.GetLastError
GetLastError.argtypes = []
GetLastError.restype = DWORD

GetModuleHandleA = kernel32.GetModuleHandleA
GetModuleHandleA.argtypes = [LPCSTR]
GetModuleHandleA.restype = HMODULE

GetProcAddress = kernel32.GetProcAddress
GetProcAddress.argtypes = [HMODULE, LPCSTR]
GetProcAddress.restype = LPVOID

CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [DWORD, DWORD]
CreateToolhelp32Snapshot.restype = HANDLE


class PROCESSENTRY32W(Structure):
    _fields_ = [
        ('dwSize', DWORD),
        ('cntUsage', DWORD),
        ('th32ProcessID', DWORD),
        ('th32DefaultHeapID', POINTER(ULONG)),
        ('th32ModuleID', DWORD),
        ('th32ThreadCount', DWORD),
        ('th32ParentProcessID', DWORD),
        ('pcPriClassBase', LONG),
        ('dwFlags', DWORD),
        ('szExeFile', c_wchar * 260),
    ]


Process32FirstW = kernel32.Process32FirstW
Process32FirstW.argtypes = [HANDLE, POINTER(PROCESSENTRY32W)]
Process32FirstW.restype = BOOL

Process32NextW = kernel32.Process32NextW
Process32NextW.argtypes = [HANDLE, POINTER(PROCESSENTRY32W)]
Process32NextW.restype = BOOL


TARGET_PROCESSES = ['GTA5.exe', 'GTA5_Enhanced.exe']
DISCORD_URL = 'https://discord.gg/hJ4sXdjqy4'
CONFIG_FILE = os.path.join(os.path.expanduser('~'), 'Documents', 'Inyector DLL RTX SERVER', 'config.json')


class InjectionEngine:
    def __init__(self):
        self.process_handle = None
        self.process_id = None

    def get_processes(self):
        procesos = []
        snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snapshot:
            return procesos

        pe = PROCESSENTRY32W()
        pe.dwSize = sizeof(PROCESSENTRY32W)

        all_procs = []
        if Process32FirstW(snapshot, byref(pe)):
            while True:
                name = pe.szExeFile
                pid = pe.th32ProcessID
                if pid > 0:
                    all_procs.append({'pid': pid, 'name': name})
                    if name in TARGET_PROCESSES:
                        procesos.append({'pid': pid, 'name': name})
                if not Process32NextW(snapshot, byref(pe)):
                    break

        CloseHandle(snapshot)

        if not procesos:
            for p in all_procs:
                if 'gta' in p['name'].lower():
                    procesos.append(p)

        return procesos

    def open_process(self, process_id):
        self.process_id = process_id
        self.process_handle = OpenProcess(PROCESS_ALL_ACCESS, False, process_id)
        if not self.process_handle:
            return False
        return True

    def close_process(self):
        if self.process_handle:
            CloseHandle(self.process_handle)
            self.process_handle = None
            self.process_id = None

    def allocate_memory(self, size):
        address = VirtualAllocEx(
            self.process_handle, None, size,
            MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
        )
        return address

    def free_memory(self, address):
        VirtualFreeEx(self.process_handle, address, 0, MEM_RELEASE)

    def write_memory(self, address, data):
        data_bytes = data.encode('utf-16-le') + b'\x00\x00'
        bytes_written = ctypes.c_size_t()
        result = WriteProcessMemory(
            self.process_handle, address, data_bytes,
            len(data_bytes), ctypes.byref(bytes_written)
        )
        return bool(result)

    def create_remote_thread(self, address):
        kernel32_handle = GetModuleHandleA(b'kernel32.dll')
        loadlib_addr = GetProcAddress(kernel32_handle, b'LoadLibraryW')
        if not loadlib_addr:
            return None
        thread_handle = CreateRemoteThread(
            self.process_handle, None, 0,
            loadlib_addr, address, 0, None
        )
        return thread_handle

    def inject(self, dll_path, process_id):
        if not os.path.exists(dll_path):
            return False, "DLL no encontrada"
        if not dll_path.lower().endswith('.dll'):
            return False, "El archivo debe ser .dll"

        if not self.open_process(process_id):
            return False, "No se pudo abrir el proceso"

        dll_path_abs = os.path.abspath(dll_path)
        address = self.allocate_memory(len(dll_path_abs) * 2 + 10)
        if not address:
            self.close_process()
            return False, "No se pudo asignar memoria"

        if not self.write_memory(address, dll_path_abs):
            self.free_memory(address)
            self.close_process()
            return False, "No se pudo escribir en memoria"

        thread_handle = self.create_remote_thread(address)
        if not thread_handle:
            self.free_memory(address)
            self.close_process()
            return False, "No se pudo crear el hilo remoto"

        WaitForSingleObject(thread_handle, 5000)

        CloseHandle(thread_handle)
        self.free_memory(address)
        self.close_process()

        return True, "DLL inyectada correctamente"


class InjectorApp:
    def __init__(self):
        self.root = Tk()
        self.root.title("RTXSERVER INYECTOR")

        try:
            self.root.iconbitmap(self.resource_path('ico.ico'))
        except Exception:
            try:
                user32.LoadImageW.restype = HANDLE
                icon_handle = user32.LoadImageW(0, sys.executable, 1, 32, 32, 0x00002000)
                if icon_handle:
                    user32.SendMessageW(self.root.winfo_id(), 0x0080, 0, icon_handle)
                    user32.SendMessageW(self.root.winfo_id(), 0x0080, 1, icon_handle)
            except Exception:
                pass

        self.root.geometry("900x550")
        self.root.resizable(True, True)
        self.root.minsize(800, 500)

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (900 // 2)
        y = (self.root.winfo_screenheight() // 2) - (550 // 2)
        self.root.geometry(f"900x550+{x}+{y}")

        self.engine = InjectionEngine()
        self.selected_pid = None
        self.selected_process = None
        self.dll_path = None

        self.colors = {
            'bg_dark': '#0d0d0d',
            'bg_medium': '#001a0d',
            'bg_light': '#002a14',
            'accent': '#00ff88',
            'text': '#ffffff',
            'text_dim': '#00b85c',
            'border': '#005530',
            'discord': '#5865F2',
        }

        self.configure_ui()
        self.create_ui()
        self.refresh_processes()
        self.start_auto_refresh()
        self.load_last_dll()

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_dll', '')
        except:
            return ''

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({'last_dll': self.dll_path or ''}, f)
        except:
            pass

    def configure_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.Treeview",
            background=self.colors['bg_medium'],
            foreground=self.colors['text'],
            fieldbackground=self.colors['bg_medium'],
            bordercolor=self.colors['border'],
            borderwidth=0)
        style.map("Custom.Treeview",
            background=[('selected', self.colors['accent'])],
            foreground=[('selected', self.colors['bg_dark'])])
        style.configure("Custom.Treeview.Heading",
            background=self.colors['bg_light'],
            foreground=self.colors['text'],
            relief='flat')

    def create_ui(self):
        main_frame = Frame(self.root, bg=self.colors['bg_dark'])
        main_frame.pack(fill=BOTH, expand=True)

        self.create_header(main_frame)

        content = Frame(main_frame, bg=self.colors['bg_dark'])
        content.pack(fill=BOTH, expand=True, padx=15, pady=15)

        left_panel = Frame(content, bg=self.colors['bg_medium'])
        left_panel.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
        self.create_process_panel(left_panel)

        right_panel = Frame(content, bg=self.colors['bg_medium'])
        right_panel.pack(side=RIGHT, fill=BOTH, expand=True, padx=(8, 0))
        self.create_dll_panel(right_panel)
        self.create_control_panel(right_panel)

        self.create_footer(main_frame)

    def resource_path(self, relative_path):
        if getattr(sys, '_MEIPASS', None):
            base_path = sys._MEIPASS
        elif getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def create_header(self, parent):
        header = Frame(parent, bg=self.colors['bg_dark'], height=70)
        header.pack(fill=X)
        header.pack_propagate(False)

        border = Frame(header, bg=self.colors['accent'], height=2)
        border.pack(side=BOTTOM, fill=X)

        title_label = Label(header, text="RTXSERVER INYECTOR",
                           font=("Segoe UI", 24, "bold"),
                           fg=self.colors['accent'], bg=self.colors['bg_dark'],
                           cursor='hand2')
        title_label.pack(side=LEFT, padx=20, pady=10)
        title_label.bind('<Button-1>', lambda e: webbrowser.open(DISCORD_URL))

        Label(header, text="GTA5.exe / GTA5_Enhanced.exe",
              font=("Segoe UI", 10),
              fg=self.colors['text_dim'], bg=self.colors['bg_dark']).pack(side=LEFT, pady=10)

    def create_process_panel(self, parent):
        title_frame = Frame(parent, bg=self.colors['bg_medium'])
        title_frame.pack(fill=X, padx=15, pady=(15, 10))

        Label(title_frame, text="PROCESOS",
              font=("Segoe UI", 12, "bold"),
              fg=self.colors['accent'], bg=self.colors['bg_medium']).pack(side=LEFT)

        Button(title_frame, text="Refrescar",
               font=("Segoe UI", 9),
               fg=self.colors['accent'], bg=self.colors['bg_medium'],
               relief='flat', cursor='hand2',
               command=self.refresh_processes).pack(side=RIGHT)

        list_frame = Frame(parent, bg=self.colors['bg_medium'])
        list_frame.pack(fill=BOTH, expand=True, padx=15, pady=(0, 15))

        tree_scroll = Scrollbar(list_frame)
        tree_scroll.pack(side=RIGHT, fill=Y)

        self.process_tree = ttk.Treeview(list_frame,
                                        yscrollcommand=tree_scroll.set,
                                        style="Custom.Treeview", height=15)
        self.process_tree.pack(fill=BOTH, expand=True)
        tree_scroll.config(command=self.process_tree.yview)

        self.process_tree['columns'] = ('pid', 'name')
        self.process_tree.column('#0', width=0, stretch=NO)
        self.process_tree.column('pid', width=100, anchor='center')
        self.process_tree.column('name', width=250, anchor='w')

        self.process_tree.heading('pid', text='PID')
        self.process_tree.heading('name', text='NOMBRE')

        self.process_tree.bind('<<TreeviewSelect>>', self.on_process_select)
        self.process_tree.bind('<Double-Button-1>', self.on_process_double_click)

    def create_dll_panel(self, parent):
        Label(parent, text="DLL",
              font=("Segoe UI", 12, "bold"),
              fg=self.colors['accent'], bg=self.colors['bg_medium']).pack(fill=X, padx=15, pady=(15, 10))

        dll_frame = Frame(parent, bg=self.colors['bg_light'], height=50)
        dll_frame.pack(fill=X, padx=15, pady=(0, 10))

        self.dll_label = Label(dll_frame, text="Ningun archivo seleccionado",
                              font=("Segoe UI", 10),
                              fg=self.colors['text_dim'], bg=self.colors['bg_light'], anchor='w')
        self.dll_label.pack(side=LEFT, fill=X, expand=True, padx=10, pady=10)

        Button(dll_frame, text="EXAMINAR",
               font=("Segoe UI", 10, "bold"),
               fg=self.colors['bg_dark'], bg=self.colors['accent'],
               relief='flat', cursor='hand2',
               command=self.browse_dll).pack(side=RIGHT, padx=10, pady=5)

        self.dll_info = Label(parent, text="",
                             font=("Segoe UI", 9),
                             fg=self.colors['text_dim'], bg=self.colors['bg_medium'], anchor='w')
        self.dll_info.pack(fill=X, padx=15, pady=(0, 15))

    def create_control_panel(self, parent):
        Label(parent, text="CONTROLES",
              font=("Segoe UI", 12, "bold"),
              fg=self.colors['accent'], bg=self.colors['bg_medium']).pack(fill=X, padx=15, pady=(0, 10))

        info_frame = Frame(parent, bg=self.colors['bg_light'], height=60)
        info_frame.pack(fill=X, padx=15, pady=(0, 15))

        self.process_info = Label(info_frame,
                                text="Selecciona un proceso de la lista",
                                font=("Segoe UI", 10),
                                fg=self.colors['text_dim'], bg=self.colors['bg_light'],
                                justify='left', anchor='w')
        self.process_info.pack(fill=BOTH, expand=True, padx=10, pady=5)

        self.inject_btn = Button(parent, text="INYECTAR DLL",
                               font=("Segoe UI", 14, "bold"),
                               fg=self.colors['bg_dark'], bg=self.colors['accent'],
                               relief='flat', cursor='hand2',
                               state='disabled', command=self.inject_dll)
        self.inject_btn.pack(fill=X, padx=15, pady=(0, 15), ipady=15)

    def create_footer(self, parent):
        footer = Frame(parent, bg=self.colors['bg_dark'], height=30)
        footer.pack(fill=X, side=BOTTOM)
        Frame(footer, bg=self.colors['border'], height=1).pack(side=TOP, fill=X)
        Label(footer, text="Educational Purpose Only",
              font=("Segoe UI", 9),
              fg=self.colors['text_dim'], bg=self.colors['bg_dark']).pack(side=LEFT, padx=15, pady=5)

        discord_btn = Button(footer, text="DISCORD",
                            font=("Segoe UI", 9, "bold"),
                            fg="white", bg=self.colors['discord'],
                            relief='flat', cursor='hand2',
                            command=lambda: webbrowser.open(DISCORD_URL))
        discord_btn.pack(side=RIGHT, padx=15, pady=3)

    def refresh_processes(self):
        self.process_tree.delete(*self.process_tree.get_children())
        procesos = self.engine.get_processes()
        for proc in procesos:
            self.process_tree.insert('', END, values=(proc['pid'], proc['name']))

    def on_process_select(self, event=None):
        selection = self.process_tree.selection()
        if selection:
            item = self.process_tree.item(selection[0])
            values = item['values']
            if values:
                self.selected_pid = values[0]
                self.selected_process = values[1]
                self.process_info.config(
                    text=f"Proceso: {self.selected_process}\nPID: {self.selected_pid}",
                    fg=self.colors['text']
                )
                if self.dll_path:
                    self.inject_btn.config(state='normal')

    def on_process_double_click(self, event=None):
        self.on_process_select()
        if self.dll_path and self.selected_pid:
            self.inject_dll()

    def browse_dll(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar DLL",
            filetypes=[("DLL Files", "*.dll"), ("All Files", "*.*")],
            initialdir=os.path.expanduser("~")
        )
        if filename:
            self.dll_path = filename
            self.dll_label.config(text=os.path.basename(filename), fg=self.colors['text'])
            size = os.path.getsize(filename)
            self.dll_info.config(text=f"{filename} | {size / 1024:.1f} KB")
            self.save_config()
            if self.selected_pid:
                self.inject_btn.config(state='normal')

    def inject_dll(self):
        if not self.dll_path:
            messagebox.showwarning("Advertencia", "Selecciona una DLL primero")
            return
        if not self.selected_pid:
            messagebox.showwarning("Advertencia", "Selecciona un proceso primero")
            return
        self.inject_btn.config(state='disabled', text="INYECTANDO...")
        threading.Thread(target=self._inject_thread, daemon=True).start()

    def _inject_thread(self):
        success, message = self.engine.inject(self.dll_path, self.selected_pid)
        self.root.after(0, self._after_inject, success, message)

    def _after_inject(self, success, message):
        self.inject_btn.config(state='normal', text="INYECTAR DLL")
        if success:
            messagebox.showinfo("Éxito", message)
        else:
            messagebox.showerror("Error", message)

    def load_last_dll(self):
        last_dll = self.load_config()
        if last_dll and os.path.exists(last_dll):
            self.dll_path = last_dll
            self.dll_label.config(text=os.path.basename(last_dll), fg=self.colors['text'])
            size = os.path.getsize(last_dll)
            self.dll_info.config(text=f"{last_dll} | {size / 1024:.1f} KB")
            if self.selected_pid:
                self.inject_btn.config(state='normal')

    def start_auto_refresh(self):
        self.refresh_processes()
        self.root.after(5000, self.start_auto_refresh)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    try:
        app = InjectorApp()
        app.run()
    except Exception as e:
        messagebox.showerror("Error", f"Error: {e}")
