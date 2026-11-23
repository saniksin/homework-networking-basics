#!/usr/bin/env python3
"""Мінімальний тестовий REST API для ДЗ №3 (лише стандартна бібліотека Python).

Запуск:   python3 test_api.py            (слухає http://127.0.0.1:8000)
Ресурс:   /books

  GET    /books          - список книг              -> 200 OK (кешується, є ETag)
  GET    /books/<id>     - одна книга               -> 200 OK / 404 Not Found
  POST   /books          - створити книгу           -> 201 Created + Location
  PUT    /books/<id>     - повністю замінити книгу  -> 200 OK / 404 Not Found
  DELETE /books/<id>     - видалити книгу           -> 204 No Content / 404 Not Found

POST приймає тіло як JSON (Content-Type: application/json)
або як форму (Content-Type: application/x-www-form-urlencoded).
"""
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST, PORT = "127.0.0.1", 8000

books = {
    1: {"id": 1, "title": "Комп'ютерні мережі", "author": "Таненбаум"},
    2: {"id": 2, "title": "TCP/IP Illustrated", "author": "Стівенс"},
}
next_id = 3


class Handler(BaseHTTPRequestHandler):
    server_version = "TestAPI/1.0"
    protocol_version = "HTTP/1.1"

    # --- допоміжні методи -------------------------------------------------
    def _send(self, code, body=None, headers=None):
        data = b"" if body is None else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        if body is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if data and self.command != "HEAD":
            self.wfile.write(data)

    def _book_id(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if parts[0] != "books":
            return None, False
        if len(parts) == 1:
            return None, True
        return (int(parts[1]) if parts[1].isdigit() else -1), True

    def _read_body(self):
        """Повертає (дані, помилка). Тіло читається завжди і повністю, інакше
        його залишок у keep-alive з'єднанні сервер прочитав би як наступний запит."""
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.close_connection = True
            return None, "некоректний Content-Length"
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            try:
                data = json.loads(raw or "{}")
            except json.JSONDecodeError:
                return None, "тіло не є коректним JSON"
            if not isinstance(data, dict):
                return None, "очікується JSON-об'єкт"
            return data, None
        # форма: title=foo&author=bar
        return {k: v[0] for k, v in parse_qs(raw).items()}, None

    # --- методи HTTP ------------------------------------------------------
    def do_GET(self):
        book_id, ok = self._book_id()
        if not ok:
            return self._send(404, {"error": "not found"})
        if book_id is None:
            body = list(books.values())
        elif book_id in books:
            body = books[book_id]
        else:
            return self._send(404, {"error": f"book {book_id} not found"})

        # GET - безпечний та ідемпотентний, тому відповідь можна кешувати.
        etag = '"' + hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16] + '"'
        cache = {"Cache-Control": "public, max-age=60", "ETag": etag}
        if self.headers.get("If-None-Match") == etag:
            return self._send(304, None, cache)  # дані не змінились - тіло не надсилаємо
        self._send(200, body, cache)

    do_HEAD = do_GET

    def do_POST(self):
        global next_id
        data, err = self._read_body()
        book_id, ok = self._book_id()
        if not ok:
            return self._send(404, {"error": "not found"})
        if book_id is not None:
            return self._send(405, {"error": "POST дозволено лише на /books"},
                              {"Allow": "GET, HEAD, PUT, DELETE"})
        if err:
            return self._send(400, {"error": err})
        if not data.get("title"):
            return self._send(400, {"error": "поле title обов'язкове"})
        book = {"id": next_id, "title": data["title"], "author": data.get("author", "")}
        books[next_id] = book
        next_id += 1
        # POST змінює стан сервера, тому відповідь не кешується.
        self._send(201, book, {"Location": f"/books/{book['id']}", "Cache-Control": "no-store"})

    def do_PUT(self):
        data, err = self._read_body()
        book_id, ok = self._book_id()
        if not ok:
            return self._send(404, {"error": "not found"})
        if book_id is None:
            return self._send(405, {"error": "PUT дозволено лише на /books/<id>"},
                              {"Allow": "GET, HEAD, POST"})
        if book_id not in books:
            return self._send(404, {"error": f"book {book_id} not found"})
        if err:
            return self._send(400, {"error": err})
        books[book_id] = {"id": book_id, "title": data.get("title", ""), "author": data.get("author", "")}
        self._send(200, books[book_id], {"Cache-Control": "no-store"})

    def do_DELETE(self):
        book_id, ok = self._book_id()
        if not ok:
            return self._send(404, {"error": "not found"})
        if book_id is None:
            return self._send(405, {"error": "DELETE дозволено лише на /books/<id>"},
                              {"Allow": "GET, HEAD, POST"})
        if book_id not in books:
            return self._send(404, {"error": f"book {book_id} not found"})
        del books[book_id]
        self._send(204, None, {"Cache-Control": "no-store"})


if __name__ == "__main__":
    print(f"Test API: http://{HOST}:{PORT}/books")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
