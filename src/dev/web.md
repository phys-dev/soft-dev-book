# Основы компьютерных сетей и веб-технологий

## Введение в сетевые технологии

Компьютерные сети представляют собой сложные многоуровневые системы, обеспечивающие обмен данными между устройствами. Современный интернет построен на принципах, позволяющих использовать сетевые возможности без необходимости глубокого понимания всех технических деталей.

## Сетевые модели: OSI vs TCP/IP

### Модель OSI (эталонная 7-уровневая модель)
1. **Физический уровень** - передача битов через физическую среду
2. **Канальный уровень** - передача кадров между соседними узлами
3. **Сетевой уровень** - маршрутизация между сетями (IP)
4. **Транспортный уровень** - обеспечение надежной доставки (TCP/UDP)
5. **Сеансовый уровень** - управление сессиями связи
6. **Уровень представления** - преобразование данных
7. **Прикладной уровень** - сетевые приложения (HTTP, DNS, FTP)

### Модель TCP/IP (практическая 4-уровневая модель)
- **Уровень сетевого доступа** (объединяет физический и канальный)
- **Сетевой уровень** (IP)
- **Транспортный уровень** (TCP/UDP)
- **Прикладной уровень** (HTTP, SMTP, DNS)

## Уровень сетевого доступа

### Физический уровень
Обеспечивает передачу необработанных битов через физическую среду:
- **Медные кабели**: витая пара (UTP/STP), коаксиальные кабели
- **Оптоволокно**: одномодовое и многомодовое
- **Беспроводные технологии**: Wi-Fi (802.11), Bluetooth, сотовая связь

**Ключевые характеристики**:
- Скорость передачи данных
- Полоса пропускания
- Затухание сигнала
- Помехоустойчивость

**Примеры проблем**:
- Обрыв кабеля
- Электромагнитные помехи
- Неправильная обжимка коннекторов
- Превышение максимальной длины сегмента

### Канальный уровень
Обеспечивает надежную передачу данных между устройствами в одной локальной сети:

**Основные технологии**:
- Ethernet (IEEE 802.3)
- Wi-Fi (IEEE 802.11)
- PPP (точка-точка)

**Ключевые компоненты**:
- **MAC-адреса**: уникальные идентификаторы сетевых интерфейсов
- **Ethernet-фреймы**: структурированные блоки данных
- **ARP-протокол**: разрешение IP-адресов в MAC-адреса
- **VLAN**: логическое разделение сети на виртуальные сегменты

**Диагностика**:
```bash
ip link show          # показать сетевые интерфейсы
ethtool eth0          # информация об интерфейсе
arp -a                # показать ARP-таблицу
```

## Сетевой уровень (IP)

### Основы IP-адресации

#### IPv4
- 32-битные адреса (4 октета по 8 бит)
- Формат: `192.168.1.1`
- Классы адресов: A, B, C, D, E
- Частные диапазоны:
  - `10.0.0.0/8`
  - `172.16.0.0/12`
  - `192.168.0.0/16`

#### IPv6
- 128-битные адреса (8 групп по 16 бит)
- Формат: `2001:0db8:85a3:0000:0000:8a2e:0370:7334`
- Сокращенная запись: `2001:db8:85a3::8a2e:370:7334`
- Типы адресов: unicast, multicast, anycast

### Маршрутизация
Определение пути для пакетов между различными сетями:

**Таблица маршрутизации**:
```bash
$ ip route show
default via 192.168.1.1 dev eth0
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.100
10.0.0.0/8 via 192.168.1.254 dev eth0
```

**Политики маршрутизации**:
```bash
$ ip rule
0:    from all lookup local
32766: from all lookup main
32767: from all lookup default
```

**Диагностика**:
```bash
traceroute 8.8.8.8
mtr 8.8.8.8
ip route get 8.8.8.8
```

## Транспортный уровень

### UDP (User Datagram Protocol)
- Без установления соединения
- Нет гарантий доставки
- Нет контроля перегрузок
- Низкие накладные расходы

**Применение**:
- DNS-запросы
- VoIP (голосовая связь)
- Онлайн-игры
- Видеотрансляции

### TCP (Transmission Control Protocol)
- Установление соединения (трехстороннее рукопожатие)
- Гарантии доставки и порядка
- Контроль перегрузок
- Механизмы повторной передачи

#### Трехстороннее рукопожатие
1. Клиент → Сервер: SYN (запрос на соединение)
2. Сервер → Клиент: SYN-ACK (подтверждение)
3. Клиент → Сервер: ACK (подтверждение)

#### Заголовок TCP
```
| Source Port | Destination Port |
| Sequence Number |
| Acknowledgment Number |
| Data Offset | Reserved | Flags | Window Size |
| Checksum | Urgent Pointer |
```

#### Управление перегрузками
- **Tahoe/Reno**: классические алгоритмы
- **Cubic**: используется по умолчанию в Linux
- **BBR**: современный алгоритм от Google

**Диагностика TCP**:
```bash
netstat -tn
ss -tlnp
tcpdump -i any tcp port 80
```

## Прикладной уровень

### DNS (Domain Name System)
Преобразование доменных имен в IP-адреса:

**Типы DNS-записей**:
- A/AAAA - IPv4/IPv6 адреса
- MX - почтовые серверы
- CNAME - канонические имена
- TXT - текстовые записи

**Пример на Python**:
```python
import socket
ip_address = socket.gethostbyname('example.com')
```

### URL (Uniform Resource Locator)
Структура: `protocol://host:port/path?query#fragment`

**Примеры**:
- `http://example.com:80/path?search=query`
- `https://api.example.com/v1/data`
- `ftp://ftp.example.com/files`
- `mailto:user@example.com`

### HTTP (HyperText Transfer Protocol)
Протокол прикладного уровня для передачи веб-контента.

#### HTTP-запрос
```
GET /index.html HTTP/1.1
Host: example.com
User-Agent: Mozilla/5.0
Accept: text/html
Connection: keep-alive
```

**Методы HTTP**:
- GET - получение ресурса
- POST - отправка данных
- PUT - обновление ресурса
- DELETE - удаление ресурса
- PATCH - частичное обновление

#### HTTP-ответ
```
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 1234
Server: nginx
Date: Mon, 21 Nov 2022 00:18:53 GMT
```

**Коды состояния**:
- 1xx - информационные
- 2xx - успешные (200 OK, 201 Created)
- 3xx - перенаправления (301 Moved Permanently)
- 4xx - ошибки клиента (404 Not Found)
- 5xx - ошибки сервера (500 Internal Server Error)

### Работа с HTTP в Python

#### Использование сокетов
```python
import socket

# TCP-соединение
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect(('example.com', 80))
    request = b'GET / HTTP/1.1\r\nHost: example.com\r\n\r\n'
    sock.sendall(request)
    response = sock.recv(4096)
```

#### Библиотека requests
```python
import requests

response = requests.get('https://api.example.com/data')
print(response.status_code)
print(response.headers)
print(response.json())
```

### SSL/TLS
Защищенная передача данных через шифрование:

```python
import ssl
import socket

context = ssl.create_default_context()
with socket.create_connection(('example.com', 443)) as sock:
    with context.wrap_socket(sock, server_hostname='example.com') as ssock:
        ssock.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\n\r\n')
        response = ssock.recv(4096)
```

## Веб-скрапинг и парсинг HTML

### Библиотека BeautifulSoup
```python
from bs4 import BeautifulSoup
import requests

html = requests.get('http://example.com').text
soup = BeautifulSoup(html, 'html.parser')

# Извлечение данных
title = soup.find('title').text
links = soup.find_all('a', href=True)
for link in links:
    print(link['href'], link.text)
```

### Практические советы по скрапингу
1. Проверяй `robots.txt`
2. Используй задержки между запросами
3. Устанавливай User-Agent заголовок
4. Обрабатывай ошибки
5. Кешируй полученные данные

## Работа с API

### Публичные API
```python
import requests
import json

# Пример работы с API словаря
DICTIONARY_API = 'https://dictionary.yandex.net/api/v1/dicservice.json/lookup'
params = {
    'key': 'your_api_key',
    'lang': 'en-ru',
    'text': 'hello'
}

response = requests.get(DICTIONARY_API, params=params)
data = response.json()
translations = data['def'][0]['tr']
```

### OAuth авторизация
```python
class ApiClient:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers['Authorization'] = f'Bearer {token}'
    
    def get_user_info(self):
        response = self.session.get('https://api.example.com/user')
        return response.json()
```

### JSON формат
JavaScript Object Notation - стандартный формат для обмена данными:

```python
import json

# Сериализация
data = {'name': 'John', 'age': 30}
json_string = json.dumps(data)

# Десериализация
parsed_data = json.loads(json_string)
```

## Асинхронные HTTP-запросы

### Библиотека httpx
```python
import httpx

# Синхронные запросы
with httpx.Client() as client:
    response = client.get('https://example.com')
    print(response.status_code)

# Асинхронные запросы
import asyncio

async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get('https://example.com')
        return response.json()
```

## Заключение

Современные сетевые технологии представляют собой многоуровневую систему, где каждый уровень решает определенные задачи:
- **Физический и канальный уровни** обеспечивают базовую передачу данных
- **Сетевой уровень** отвечает за маршрутизацию между сетями
- **Транспортный уровень** гарантирует надежную доставку
- **Прикладной уровень** предоставляет интерфейсы для конкретных сервисов

Понимание этих принципов позволяет эффективно диагностировать проблемы, разрабатывать сетевые приложения и взаимодействовать с веб-сервисами через API. Современные инструменты и библиотеки Python значительно упрощают работу с сетевыми протоколами, делая разработку сетевых приложений доступной для широкого круга программистов.