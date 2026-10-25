#!/usr/bin/env python3
"""Прокси «Диктовка» между FluidVoice и LM Studio.

FluidVoice шлёт надиктованный текст в OpenAI-совместимый сервер. Прокси слушает
http://localhost:1235/v1 и отдаёт наружу виртуальные модели:
  pravka   — чистовая правка по правилам живого русского письма (prompt-pravka.txt)
  korotche — сокращение выделенного текста (prompt-korotche.txt)
  komanda  — голосовая команда над выделенным текстом («сделай короче», «вежливее»):
             инструкция клиента сохраняется, к ней дописываются правила языка (prompt-stil.txt)
Под ними работает локальная модель LM Studio (MODEL), размышления модели отключены
(reasoning_effort=none): иначе Gemma 4 думает 15 секунд над одной фразой.
Любая другая модель проходит насквозь как есть. Запросы пишутся в zhurnal.jsonl.
"""
import json
import os
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

KOREN = Path(__file__).resolve().parent
LMSTUDIO = os.environ.get("LMSTUDIO_URL", "http://localhost:1234")
MODEL = os.environ.get("MODEL", "google/gemma-4-12b-qat")
REZHIMY = {"pravka": "prompt-pravka.txt", "korotche": "prompt-korotche.txt"}
ZHURNAL = KOREN / "zhurnal.jsonl"


def podgotovit(zapros: dict) -> dict:
    rezhim = zapros.get("model")
    if rezhim == "komanda":
        stil = (KOREN / "prompt-stil.txt").read_text()
        soobshcheniya = zapros.get("messages", [])
        sistemnye = [m for m in soobshcheniya if m.get("role") == "system"]
        if sistemnye:
            sistemnye[0]["content"] = f"{sistemnye[0]['content']}\n\n{stil}"
        else:
            soobshcheniya.insert(0, {"role": "system", "content": stil})
        zapros["model"] = MODEL
        zapros.setdefault("temperature", 0.3)
    elif rezhim in REZHIMY:
        prompt = (KOREN / REZHIMY[rezhim]).read_text()
        # от клиента берём только текст пользователя, свою инструкцию ставим вместо его системной
        polzovatel = [m for m in zapros.get("messages", []) if m.get("role") != "system"]
        zapros["messages"] = [{"role": "system", "content": prompt}] + polzovatel
        zapros["model"] = MODEL
        zapros.setdefault("temperature", 0.2)
    zapros["reasoning_effort"] = "none"
    return zapros


class Obrabotchik(BaseHTTPRequestHandler):
    def _pereslat(self, telo: bytes | None):
        zapros_json, rezhim = None, None
        if telo:
            try:
                zapros_json = json.loads(telo)
                rezhim = zapros_json.get("model")
                telo = json.dumps(podgotovit(zapros_json)).encode()
            except json.JSONDecodeError:
                pass
        req = urllib.request.Request(LMSTUDIO + self.path, data=telo, method=self.command,
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        for popytka in range(2):
            try:
                with urllib.request.urlopen(req, timeout=300) as otvet:
                    dannye, kod = otvet.read(), otvet.status
                    tip = otvet.headers.get("Content-Type", "application/json")
            except urllib.error.HTTPError as e:
                dannye, kod, tip = e.read(), e.code, "application/json"
            # в 16 ГБ две модели не помещаются: выгружаем всё и даём LM Studio загрузить нужную
            if popytka == 0 and b"insufficient system resources" in dannye:
                subprocess.run([str(Path.home() / ".lmstudio/bin/lms"), "unload", "--all"], capture_output=True)
                req = urllib.request.Request(LMSTUDIO + self.path, data=telo, method=self.command,
                                             headers={"Content-Type": "application/json"})
                continue
            break
        if self.path.rstrip("/").endswith("/models") and self.command == "GET":
            # показываем клиенту и виртуальные режимы, чтобы их можно было выбрать в настройках
            try:
                spisok = json.loads(dannye)
                spisok["data"] = [{"id": r, "object": "model", "owned_by": "diktovka"}
                                  for r in [*REZHIMY, "komanda"]] + spisok.get("data", [])
                dannye = json.dumps(spisok).encode()
            except (json.JSONDecodeError, AttributeError):
                pass
        self.send_response(kod)
        self.send_header("Content-Type", tip)
        self.send_header("Content-Length", str(len(dannye)))
        self.end_headers()
        self.wfile.write(dannye)
        if zapros_json is not None:
            with ZHURNAL.open("a") as z:
                z.write(json.dumps({"vremya": time.strftime("%Y-%m-%d %H:%M:%S"), "rezhim": rezhim,
                                    "sekund": round(time.time() - t0, 1), "put": self.path,
                                    "vhod": zapros_json.get("messages", [])[-1:] if zapros_json else None,
                                    "otvet": dannye[:2000].decode("utf-8", "replace")},
                                   ensure_ascii=False) + "\n")

    def do_POST(self):
        dlina = int(self.headers.get("Content-Length", 0))
        self._pereslat(self.rfile.read(dlina))

    def do_GET(self):
        self._pereslat(None)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 1235), Obrabotchik).serve_forever()
