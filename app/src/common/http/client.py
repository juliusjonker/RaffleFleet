# -*- coding: utf-8 -*-
import ctypes
from constants.env import OS, DEPS_PATH


CLIENT = ctypes.CDLL(str(
    DEPS_PATH / OS.name / f"http_client{OS.lib_ext}"
))

CLIENT.execReq.argtypes = [ctypes.c_char_p]
CLIENT.execReq.restype = ctypes.POINTER(ctypes.c_char)
CLIENT.freeMemory.argtypes = [ctypes.POINTER(ctypes.c_char)]
CLIENT.createClient.argtypes = [ctypes.c_char_p]
CLIENT.addCookie.argtypes = [ctypes.c_char_p]
CLIENT.deleteCookie.argtypes = [ctypes.c_char_p]
CLIENT.clearCookies.argtypes = [ctypes.c_char_p]
