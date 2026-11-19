"""Pequenas utilidades Win32 via ctypes: avisos, instância única e fechamento educado de janelas."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

MB_OK = 0x0
MB_OKCANCEL = 0x1
MB_ICONINFORMATION = 0x40
MB_ICONWARNING = 0x30
MB_ICONERROR = 0x10
MB_TOPMOST = 0x40000
MB_SETFOREGROUND = 0x10000
IDCANCEL = 2
IDTIMEOUT = 32000
WM_CLOSE = 0x0010
ERROR_ALREADY_EXISTS = 183

TITULO = "Klingo Automação"

# Janelas do próprio Windows que nunca devem receber WM_CLOSE
# (fechar a 'Progman' abre a tela de desligar do Explorer).
CLASSES_PROTEGIDAS = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
    "ApplicationFrameWindow",
}


def mensagem(texto: str, icone: int = MB_ICONINFORMATION, segundos: int = 0) -> None:
    """Mostra uma caixa de mensagem. Com segundos > 0 ela some sozinha."""
    estilo = MB_OK | icone | MB_TOPMOST | MB_SETFOREGROUND
    if segundos > 0:
        _message_box_timeout(texto, estilo, segundos)
    else:
        user32.MessageBoxW(None, texto, TITULO, estilo)


def perguntar_cancelar(texto: str, segundos: int) -> bool:
    """Mostra OK/Cancelar com tempo limite. Retorna True se o usuário clicou Cancelar."""
    estilo = MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND
    return _message_box_timeout(texto, estilo, segundos) == IDCANCEL


def _message_box_timeout(texto: str, estilo: int, segundos: int) -> int:
    # MessageBoxTimeoutW existe em todas as versões do Windows desde o XP (não documentada).
    fn = user32.MessageBoxTimeoutW
    fn.argtypes = [
        wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.UINT, wintypes.WORD, wintypes.DWORD,
    ]
    fn.restype = ctypes.c_int
    return fn(None, texto, TITULO, estilo, 0, segundos * 1000)


class InstanciaUnica:
    """Mutex nomeado: impede que o exe rode duas vezes ao mesmo tempo (logon + clique manual)."""

    def __init__(self, nome: str):
        self._handle = kernel32.CreateMutexW(None, False, f"Local\\{nome}")
        self.ja_rodando = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    def liberar(self) -> None:
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None


def fechar_janelas_abertas() -> list[str]:
    """Envia WM_CLOSE (o mesmo que clicar no X) para toda janela visível de aplicativo.

    Retorna a lista de títulos que receberam o pedido de fechamento.
    """
    janelas = listar_janelas()
    for hwnd, _ in janelas:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    return [titulo for _, titulo in janelas]


def listar_janelas() -> list[tuple[int, str]]:
    """Janelas visíveis de aplicativos do usuário (ignora o próprio Windows e este exe)."""
    meu_pid = os.getpid()
    achadas: list[tuple[int, str]] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindow(hwnd, 4):  # GW_OWNER: pula diálogos filhos
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == meu_pid:
            return True

        classe = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, classe, 256)
        if classe.value in CLASSES_PROTEGIDAS:
            return True

        tamanho = user32.GetWindowTextLengthW(hwnd)
        if tamanho == 0:
            return True
        titulo = ctypes.create_unicode_buffer(tamanho + 1)
        user32.GetWindowTextW(hwnd, titulo, tamanho + 1)

        achadas.append((hwnd, titulo.value))
        return True

    user32.EnumWindows(EnumWindowsProc(_callback), 0)
    return achadas
