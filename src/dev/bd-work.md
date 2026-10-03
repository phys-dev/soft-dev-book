# Работа с базами данных

В настоящей главе рассматривается работа с базами данных из программ и их эксплуатация. Глава продолжает главу [«Базы данных»](./bd.md), где изложены назначение СУБД, реляционная модель, язык SQL и индексы, и использует её сквозной пример — журнал измерений `lab.db`, который заполняет скрипт `make_lab.py`, — а также сервер PostgreSQL в контейнере `pg`, запущенный там же вместе с псевдонимом `psql`. Последовательно рассматриваются драйверы `sqlite3` и psycopg и защита от SQL-инъекций, транзакции и одновременный доступ, выбор между SQLite, PostgreSQL и MySQL, ORM SQLAlchemy, резервные копии, репликация, масштабирование и мониторинг, нереляционные хранилища и выбор СУБД, затем учебный сервис в четырёх хранилищах, связка баз данных с pandas и порядок перехода лаборатории от файлов к базе. Опыты главы продолжают опыты главы «Базы данных»: журнал содержит построенные там индексы и статистику, а в PostgreSQL лежит таблица `measurements` из опыта с `EXPLAIN ANALYZE`.

Листинги главы выполнены на той же машине, что и листинги главы «Базы данных», — виртуальной машине под Python 3.12 со встроенной библиотекой SQLite 3.45, SQLAlchemy 2.1, psycopg 3.3, pandas 3.0 и Flask 3.1, на которой записаны демонстрации лекции «Базы данных»; PostgreSQL 17 и Redis 8 работали на ней в контейнерах Docker. Консоли `sqlite3` на машине нет, и запросы к SQLite выполнены модулем `sqlite3` из Python. Времена выполнения зависят от машины и меняются от запуска к запуску, тогда как планы запросов, числа строк и значения воспроизводятся.

## Тот же SQL из Python

> **Слайды к главе.** Интерфейс DB-API на примере модулей sqlite3 и psycopg, параметры запросов и SQL-инъекции, ORM SQLAlchemy, pandas и форматы файлов изложены также в пятой части лекции «Базы данных» с демонстрациями в терминале; слайды лекции доступны [на сайте книги](https://phys-dev.github.io/soft-dev-book/slides/lecture-13.html#/sec-py) и [в PDF](https://github.com/phys-dev/soft-dev-book/releases/latest/download/soft-dev-book-lecture-13.pdf).

<iframe src="../slides/lecture-13.html#/sec-py" title="Слайды лекции «Базы данных»: Python и базы" loading="lazy" allowfullscreen style="width:100%; aspect-ratio:16/10; border:0; border-radius:6px"></iframe>

### Модуль sqlite3

Модуль `sqlite3`, входящий в стандартную библиотеку, устанавливать не требуется. Драйверы баз данных в Python следуют общему интерфейсу DB-API, описанному в PEP 249: функция `connect` возвращает соединение, метод `execute` выполняет запрос с параметрами, `fetchone` и `fetchall` или итерация по курсору возвращают строки кортежами, `commit` и `rollback` управляют транзакцией. Поэтому код для SQLite и PostgreSQL выглядит почти одинаково. Рассмотрим скрипт сбора данных, записывающий точки в отдельную базу `daq.db`:

```python
import random
import sqlite3


def read_adc():
    """Опрос АЦП; здесь сигнал датчика положения имитируется генератором."""
    return round(random.gauss(0.41, 0.002), 4)


random.seed(1)
# открывается (или создаётся) файл базы; ":memory:" — временная база в памяти
con = sqlite3.connect("daq.db")
# в SQLite проверка внешних ключей по умолчанию выключена
con.execute("PRAGMA foreign_keys = ON")

cur = con.cursor()  # курсор выполняет запросы и отдаёт результаты

# таблица создаётся, если её ещё нет (текст запроса — тот же SQL)
cur.execute("""
    CREATE TABLE IF NOT EXISTS measurements (
        id      INTEGER PRIMARY KEY,
        run_id  INTEGER NOT NULL,
        channel TEXT NOT NULL,
        t       REAL NOT NULL,
        value   REAL NOT NULL
    )
""")

# одиночная вставка: значения передаются кортежем, в запросе — знаки вопроса
cur.execute(
    "INSERT INTO measurements (run_id, channel, t, value) VALUES (?, ?, ?, ?)",
    (1, "BPM01", 0.0, 0.412),
)

# массовая вставка: executemany принимает любой итерируемый объект
points = [(1, "BPM01", i / 10, read_adc()) for i in range(1, 1000)]
cur.executemany(
    "INSERT INTO measurements (run_id, channel, t, value) VALUES (?, ?, ?, ?)",
    points,
)
con.commit()  # изменения фиксируются на диске

# выборка: по курсору можно итерироваться, каждая строка — кортеж
for t, value in cur.execute(
    "SELECT t, value FROM measurements WHERE channel = ? AND t < ? ORDER BY t",
    ("BPM01", 0.3),
):
    print(t, value)

con.close()
```

    0.0 0.412
    0.1 0.4126
    0.2 0.4129

Для небольших выборок удобны `cur.fetchone()` и `cur.fetchall()`, однако итерация по курсору экономнее: строки читаются по мере надобности и не накапливаются в памяти все сразу. Повторный запуск скрипта добавит в таблицу ещё тысячу точек, поскольку `CREATE TABLE IF NOT EXISTS` существующую таблицу не пересоздаёт.

### Драйвер psycopg

Для PostgreSQL в новом коде используют драйвер psycopg третьей версии (`pip install "psycopg[binary]"`), заменяющий psycopg2: он передаёт параметры серверу отдельно от текста запроса, умеет работать асинхронно и поддерживает конвейерную отправку команд. Отличий от `sqlite3` два. Знак параметра — `%s` вместо `?`. Конструкция `with psycopg.connect(...) as conn:` при выходе из блока фиксирует транзакцию и закрывает соединение, тогда как `with con:` в `sqlite3` только завершает транзакцию, оставляя соединение открытым. Для массовой загрузки вместо тысяч `INSERT` используют команду `COPY`, которой psycopg передаёт строки потоком; это самый быстрый способ загрузить данные в PostgreSQL.

```python
import psycopg

DSN = "host=127.0.0.1 user=postgres password=lab"
points = [(7, "BPM01", i / 100, round(0.16 + 1e-4 * i, 4)) for i in range(5000)]

with psycopg.connect(DSN) as conn:          # при выходе: COMMIT и закрытие
    conn.execute("DROP TABLE IF EXISTS points")
    conn.execute("CREATE TABLE points (run_id int, channel text, t float8, value float8)")
    with conn.cursor().copy(
        "COPY points (run_id, channel, t, value) FROM STDIN"
    ) as copy:
        for row in points:
            copy.write_row(row)             # строки уходят серверу потоком
    rows = conn.execute(
        "SELECT t, value FROM points WHERE run_id = %s AND t < %s ORDER BY t",
        (7, 0.03),
    ).fetchall()
print(rows)
```

    [(0.0, 0.16), (0.01, 0.1601), (0.02, 0.1602)]

Соединение с PostgreSQL обслуживает отдельный серверный процесс, и открыть его дорого. Оценим, во что обходится соединение на каждый запрос, по сравнению с одним постоянным соединением и с пулом `psycopg_pool.ConnectionPool` из пакета `psycopg-pool`:

```python
import time

import psycopg
from psycopg_pool import ConnectionPool

DSN = "host=127.0.0.1 user=postgres password=lab"
N = 200


def per_query(func):
    """Среднее время одного вызова, мс."""
    start = time.perf_counter()
    for _ in range(N):
        func()
    return (time.perf_counter() - start) / N * 1000


def new_connection():                       # соединение на каждый запрос
    with psycopg.connect(DSN) as conn:
        conn.execute("SELECT 1").fetchone()


conn = psycopg.connect(DSN, autocommit=True)  # одно соединение на всю работу
pool = ConnectionPool(DSN, min_size=2, max_size=4, open=True)


def from_pool():                            # соединение из пула, затем обратно
    with pool.connection() as c:
        c.execute("SELECT 1").fetchone()


print(f"новое соединение  {per_query(new_connection):6.2f} мс на запрос")
print(f"одно соединение   {per_query(lambda: conn.execute('SELECT 1').fetchone()):6.2f} мс на запрос")
print(f"пул соединений    {per_query(from_pool):6.2f} мс на запрос")
pool.close()
```

    новое соединение    3.15 мс на запрос
    одно соединение     0.07 мс на запрос
    пул соединений      0.19 мс на запрос

Открытие соединения, включающее сетевое рукопожатие, проверку пароля и запуск серверного процесса, обходится в 3 мс, в 45 раз дороже самого запроса. Пул держит соединения открытыми и выдаёт их на время блока `with pool.connection()`; по выходе из блока он фиксирует транзакцию и возвращает соединение в пул. Разница с одним соединением объясняется именно транзакцией: соединение из пула работает без автофиксации, и запрос обрамляют команды `BEGIN` и `COMMIT`, а с параметром `kwargs={"autocommit": True}` пул отвечает так же быстро, как одно соединение. Таким образом, сервис открывает соединения один раз на процесс — пулом в самой программе или посредником PgBouncer перед сервером, — а не на каждый запрос.

### Параметризованные запросы и SQL-инъекции

В примерах выше значения подставлялись через знаки вопроса, а не f-строками, и причиной этого является безопасность. Пусть имя канала приходит извне: из формы на веб-странице, из аргумента командной строки или из присланного файла.

```python
channel = input("Канал: ")

# ТАК ДЕЛАТЬ НЕЛЬЗЯ: запрос склеивается из чужого текста
cur.execute(f"SELECT t, value FROM measurements WHERE channel = '{channel}'")
```

Если пользователь введёт `' OR '1'='1`, итоговый запрос превратится в `... WHERE channel = '' OR '1'='1'`, где условие всегда истинно, фильтр исчезает, а наружу уходит вся таблица. Ввод вида `'; DROP TABLE measurements; --` в драйвере, исполняющем несколько команд подряд, уничтожит таблицу. Это явление называется **SQL-инъекцией**, одной из самых старых и до сих пор распространённых уязвимостей (см. [xkcd про школьника Bobby Tables](https://xkcd.com/327/)).

Параметризованный запрос неуязвим по построению: текст запроса и данные передаются драйверу *раздельно*, и введённая строка остаётся строкой при любом содержимом:

```python
# правильно: запрос отдельно, данные отдельно
cur.execute("SELECT t, value FROM measurements WHERE channel = ?", (channel,))
```

Проверим оба способа на копии журнала `inject.db` (`cp lab.db inject.db`): последний опыт удаляет таблицу, и ставить его на рабочем журнале нельзя. Скрипт получает имя канала аргументом командной строки и считает точки запросом, склеенным f-строкой, и запросом с параметром:

```python
"""SQL-инъекция: запрос, склеенный из строки, против запроса с параметром."""
import sqlite3
import sys

con = sqlite3.connect("inject.db")            # копия журнала: cp lab.db inject.db
channel = sys.argv[-1]
unsafe = f"SELECT count(*) FROM measurements WHERE channel = '{channel}'"
print("склеено: ", unsafe)
if sys.argv[1] == "--script":                 # executescript выполняет все операторы
    con.executescript(unsafe)
    tables = con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    print("таблицы: ", [row[0] for row in tables])
    sys.exit()
try:
    print("склейка: ", con.execute(unsafe).fetchone()[0], "строк")
except sqlite3.Error as e:
    print("склейка: ", f"{type(e).__name__}: {e}")
safe = "SELECT count(*) FROM measurements WHERE channel = ?"
print("параметр:", con.execute(safe, (channel,)).fetchone()[0], "строк")
```

```bash
$ python3 inject.py BPM01
склеено:  SELECT count(*) FROM measurements WHERE channel = 'BPM01'
склейка:  200000 строк
параметр: 200000 строк
$ python3 inject.py "' OR '1'='1"
склеено:  SELECT count(*) FROM measurements WHERE channel = '' OR '1'='1'
склейка:  1000000 строк
параметр: 0 строк
$ python3 inject.py "'; DROP TABLE measurements; --"
склеено:  SELECT count(*) FROM measurements WHERE channel = ''; DROP TABLE measurements; --'
склейка:  ProgrammingError: You can only execute one statement at a time.
параметр: 0 строк
$ python3 inject.py --script "'; DROP TABLE measurements; --"
склеено:  SELECT count(*) FROM measurements WHERE channel = ''; DROP TABLE measurements; --'
таблицы:  ['experiments', 'runs', 'sqlite_stat1']
```

Для обычного ввода оба способа возвращают 200 000 строк. Ввод `' OR '1'='1` превращает склеенный запрос в условие, истинное для всех строк, и запрос возвращает 1 000 000 — все измерения всех каналов, — а запрос с параметром ищет канал с именем `' OR '1'='1` и находит 0 строк. Ввод с точкой с запятой и `DROP TABLE` в методе `execute` не срабатывает: модуль `sqlite3` отказывается выполнять больше одного оператора и выдаёт `ProgrammingError`. Это свойство драйвера, а не защита: тот же ввод, переданный в `executescript`, который выполняет операторы подряд, удаляет таблицу `measurements`, и в базе остаются только `experiments`, `runs` и служебная таблица статистики `sqlite_stat1`, созданная командой `ANALYZE` в главе «Базы данных».

**Значения передаются только через параметры, всегда**, даже если данные собственные. Параметром может быть лишь значение, но не имя таблицы или столбца; имена, подставляемые динамически, необходимо проверять по белому списку. Вторая линия защиты — права: сервис подключается к базе от роли, которой разрешены только нужные операции с нужными таблицами, и команда `DROP TABLE` от его имени не выполнится.

## Транзакции и ACID

> **Слайды к главе.** Гарантии ACID и цена фиксации, уровни изоляции, блокировки и журнал WAL в SQLite и многоверсионность в PostgreSQL изложены также в четвёртой части лекции «Базы данных» с демонстрациями в терминале; слайды лекции доступны [на сайте книги](https://phys-dev.github.io/soft-dev-book/slides/lecture-13.html#/sec-tx) и [в PDF](https://github.com/phys-dev/soft-dev-book/releases/latest/download/soft-dev-book-lecture-13.pdf).

<iframe src="../slides/lecture-13.html#/sec-tx" title="Слайды лекции «Базы данных»: транзакции" loading="lazy" allowfullscreen style="width:100%; aspect-ratio:16/10; border:0; border-radius:6px"></iframe>

**Транзакция** представляет собой группу запросов, выполняемую как единое целое: применяются либо все, либо ни один. Её гарантии описывает аббревиатура **ACID**. Атомарность (atomicity) означает неделимость транзакции: сбой, случившийся на середине, откатывает всё сделанное. Согласованность (consistency) требует, чтобы база переходила из одного корректного состояния в другое, не нарушая ограничений — ключей, `NOT NULL`, `UNIQUE`. Изолированность (isolation) скрывает от параллельных транзакций промежуточные состояния друг друга; насколько строго, задаёт уровень изоляции, рассматриваемый ниже. Долговечность (durability) сохраняет подтверждённые командой `COMMIT` данные даже при внезапном отключении питания, поскольку до ответа клиенту изменения записываются в журнал на диске.

Заход и снятые в нём точки необходимо записывать в базу вместе: заход без точек и точки без захода одинаково бессмысленны.

```python
import sqlite3


def save_run(con, run_row, points):
    """Сохраняет заход и все его измерения одной транзакцией."""
    cur = con.cursor()
    try:
        cur.execute("INSERT INTO runs (experiment_id, run_number, energy_mev, started_at) "
                    "VALUES (?, ?, ?, ?)", run_row)       # неявно открывает транзакцию
        run_id = cur.lastrowid
        cur.executemany("INSERT INTO measurements (run_id, channel, t, value) "
                        "VALUES (?, ?, ?, ?)", [(run_id, ch, t, v) for ch, t, v in points])
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
```

Модуль `sqlite3` открывает транзакцию неявно перед первой изменяющей командой, `commit` её фиксирует, `rollback` откатывает. Ту же пару обеспечивает конструкция `with con:`, подтверждающая транзакцию при выходе из блока и откатывающая её при исключении; соединение она, в отличие от файла в конструкции `with open`, не закрывает. Проверим функцию на журнале:

```python
con = sqlite3.connect("lab.db")
con.execute("PRAGMA foreign_keys = ON")
count = "SELECT (SELECT count(*) FROM runs), (SELECT count(*) FROM measurements)"
print("до:          ", con.execute(count).fetchone())
save_run(con, (2, 42, 25.0, "2026-09-02T10:00:00Z"), [("BPM01", 0.0, 0.5), ("BPM01", 0.01, 0.51)])
print("после 42:    ", con.execute(count).fetchone())
try:   # вторая точка без значения: NOT NULL нарушен на середине транзакции
    save_run(con, (2, 43, 25.5, "2026-09-02T11:00:00Z"), [("BPM01", 0.0, 0.5), ("BPM01", 0.01, None)])
except sqlite3.IntegrityError as e:
    print("ошибка:      ", e)
print("после 43:    ", con.execute(count).fetchone(), "| заход 43:",
      con.execute("SELECT count(*) FROM runs WHERE run_number = 43").fetchone()[0])
try:   # то же через with con: — commit при успехе, rollback при исключении
    with con:
        con.execute("INSERT INTO runs (experiment_id, run_number, energy_mev, started_at) "
                    "VALUES (2, 44, 26.0, '2026-09-02T12:00:00Z')")
        con.execute("INSERT INTO runs (experiment_id, run_number, energy_mev, started_at) "
                    "VALUES (2, 44, 26.0, '2026-09-02T12:00:00Z')")   # UNIQUE нарушен
except sqlite3.IntegrityError as e:
    print("with con:    ", e)
print("после 44:    ", con.execute(count).fetchone(), "| соединение открыто:",
      con.execute("SELECT 1").fetchone() == (1,))
```

    до:           (41, 1000000)
    после 42:     (42, 1000002)
    ошибка:       NOT NULL constraint failed: measurements.value
    после 43:     (42, 1000002) | заход 43: 0
    with con:     UNIQUE constraint failed: runs.experiment_id, runs.run_number
    после 44:     (42, 1000002) | соединение открыто: True

Заход 42 с двумя точками записан, и счётчики стали 42 и 1 000 002. У второй точки захода 43 значение пустое: первая точка вставилась, вторая нарушила ограничение `NOT NULL`, и `rollback` откатил всю транзакцию — счётчики прежние, а самого захода 43 в таблице нет. Тот же результат даёт `with con:`, внутри которой заход 44 вставляется дважды: второй раз нарушает ограничение `UNIQUE` на паре кампании и номера захода, транзакция откатывается, а соединение остаётся открытым.

Долговечность требует времени: каждая фиксация ждёт, пока диск подтвердит запись. Оценим цену фиксации на скрипте `bulk.py`, который вставляет 1000 строк четырьмя способами; соединение открыто в режиме автофиксации, в котором каждый оператор вне явной транзакции фиксируется сам:

```python
"""Цена фиксации: 1000 точек четырьмя способами (SQLite, режим журнала по умолчанию)."""
import os
import sqlite3
import sys
import time

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SCHEMA = "CREATE TABLE m (run_id INTEGER, channel TEXT, t REAL, value REAL)"
ROWS = [(1, "BPM01", i / 10, 0.4 + i * 1e-4) for i in range(N)]
INSERT = "INSERT INTO m VALUES (?, ?, ?, ?)"


def fresh(path="bulk.db"):
    for suffix in ("", "-journal", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    con = sqlite3.connect(path, isolation_level=None)  # автофиксация каждого оператора
    con.execute(SCHEMA)
    return con


def commit_each(con):
    for row in ROWS:
        con.execute(INSERT, row)          # каждая вставка фиксируется отдельно


def one_transaction(con):
    con.execute("BEGIN")
    for row in ROWS:
        con.execute(INSERT, row)
    con.execute("COMMIT")


def executemany(con):
    con.execute("BEGIN")
    con.executemany(INSERT, ROWS)
    con.execute("COMMIT")


def multi_values(con):
    step = 32766 // 4                     # предел числа параметров в одном запросе
    for k in range(0, N, step):
        chunk = ROWS[k:k + step]
        sql = "INSERT INTO m VALUES " + ", ".join(["(?, ?, ?, ?)"] * len(chunk))
        con.execute(sql, [x for row in chunk for x in row])


print(f"SQLite {sqlite3.sqlite_version}, {N} строк")
for func in (commit_each, one_transaction, executemany, multi_values):
    con = fresh()
    start = time.perf_counter()
    func(con)
    elapsed = time.perf_counter() - start
    count = con.execute("SELECT count(*) FROM m").fetchone()[0]
    con.close()
    print(f"{func.__name__:16s} {elapsed * 1000:9.1f} мс  ({count} строк)")
```

    SQLite 3.45.1, 1000 строк
    commit_each          654.8 мс  (1000 строк)
    one_transaction        1.8 мс  (1000 строк)
    executemany            1.5 мс  (1000 строк)
    multi_values           2.0 мс  (1000 строк)

Когда каждая вставка фиксируется отдельно, тысяча строк записывается за 0,65 с: тысяча фиксаций означает тысячу ожиданий подтверждения от диска. Те же вставки в рамках одной транзакции занимают 1,8 мс, через `executemany` — 1,5 мс, многострочным `VALUES` — 2,0 мс: важна не форма запроса, а число фиксаций. Таким образом, скрипт сбора данных записывает точки группами и фиксирует их раз в несколько секунд, а не после каждой точки.

### Уровни изоляции

Полная изоляция, при которой параллельные транзакции дают тот же результат, что и выполненные по очереди, дорога, поэтому стандарт SQL определяет четыре уровня изоляции через аномалии, допустимые на каждом из них. Грязное чтение — транзакция видит незафиксированные изменения другой. Неповторяемое чтение — повторный запрос той же строки внутри транзакции возвращает другое значение, потому что другая транзакция успела её изменить и зафиксировать. Фантомы — повторный запрос по условию возвращает новые строки. Аномалия сериализации — результат параллельных транзакций невозможно получить ни при каком порядке их последовательного выполнения.

| Уровень | Грязное чтение | Неповторяемое чтение | Фантомы | Аномалия сериализации |
|---|---|---|---|---|
| READ UNCOMMITTED | возможно | возможно | возможны | возможна |
| READ COMMITTED | нет | возможно | возможны | возможна |
| REPEATABLE READ | нет | нет | возможны | возможна |
| SERIALIZABLE | нет | нет | нет | нет |

Таблица показывает минимальные требования стандарта; реализации бывают строже. PostgreSQL по умолчанию работает на уровне READ COMMITTED, где каждый оператор видит данные, зафиксированные к его началу. На уровне REPEATABLE READ вся транзакция видит снимок на момент первого запроса, и фантомов в PostgreSQL на нём тоже нет, а READ UNCOMMITTED ведёт себя как READ COMMITTED. MySQL с движком InnoDB по умолчанию использует REPEATABLE READ, а SQLite обеспечивает сериализуемость, разрешая в каждый момент одну пишущую транзакцию. За строгость платят: на уровнях REPEATABLE READ и SERIALIZABLE PostgreSQL может прервать транзакцию ошибкой сериализации, и приложение обязано повторить её целиком. Поведение обоих уровней показывает опыт в конце раздела.

### Блокировки и журнал WAL в SQLite

SQLite разграничивает доступ блокировками всего файла базы. В режиме журнала по умолчанию, DELETE, транзакция перед изменением страницы копирует её прежнее содержимое в файл `lab.db-journal`, а новые страницы записывает в `lab.db` при фиксации; при сбое прежние страницы восстанавливаются из журнала. Чтобы зафиксировать транзакцию, писателю нужна исключительная блокировка, и он ждёт, пока не закончатся все читающие транзакции; новые читатели, в свою очередь, ждут окончания фиксации.

В режиме WAL, который включает команда `PRAGMA journal_mode=WAL`, новые версии страниц дописываются в файл `lab.db-wal`, а основной файл не меняется до контрольной точки, которая переносит страницы обратно. Читатель видит снимок базы на момент начала своей транзакции, и режим WAL обеспечивает чтение одновременно с записью: график строится, пока скрипт сбора пишет данные. Писатель в обоих режимах один: вторая пишущая транзакция ждёт освобождения блокировки время `timeout`, по умолчанию 5 с в модуле `sqlite3`, и затем получает ошибку `database is locked`. Транзакцию, которая будет писать, начинают командой `BEGIN IMMEDIATE`, чтобы ждать блокировку сразу, а не посреди работы. Режим WAL запоминается в файле базы, но требует, чтобы все процессы работали на одной машине: на сетевом диске (NFS, SMB) он неприменим.

Скрипт `locks.py` открывает к одной базе два соединения с явным управлением транзакциями и временем ожидания блокировки 0,5 с: соединение A пишет, B читает.

```python
"""Два соединения к одной базе SQLite: блокировки в режиме журнала DELETE и в WAL."""
import os
import sqlite3
import sys
import time

MODE = sys.argv[1]
for f in ("locks.db", "locks.db-wal", "locks.db-shm", "locks.db-journal"):
    if os.path.exists(f):
        os.remove(f)
setup = sqlite3.connect("locks.db")
mode = setup.execute(f"PRAGMA journal_mode={MODE}").fetchone()[0]
setup.execute("CREATE TABLE m (run_id INTEGER, value REAL)")
setup.execute("INSERT INTO m VALUES (1, 0.41)")
setup.commit()
setup.close()
# isolation_level=None: транзакции открываются и завершаются явно
a = sqlite3.connect("locks.db", isolation_level=None, timeout=0.5)   # пишет
b = sqlite3.connect("locks.db", isolation_level=None, timeout=0.5)   # читает


def rows(con):
    return con.execute("SELECT count(*) FROM m").fetchone()[0]


def attempt(sql_con, sql):
    start = time.perf_counter()
    try:
        sql_con.execute(sql)
        result = "ok"
    except sqlite3.OperationalError as e:
        result = str(e)
    return f"{result} ({time.perf_counter() - start:.2f} с)"


print("journal_mode =", mode)
a.execute("BEGIN IMMEDIATE")
a.execute("INSERT INTO m VALUES (2, 0.42)")
print(f"1. A: BEGIN IMMEDIATE, INSERT       A видит {rows(a)}, B видит {rows(b)}")
print(f"2. B: INSERT, пока пишет A          {attempt(b, 'INSERT INTO m VALUES (3, 0.43)')}")
print(f"3. A: COMMIT                        {attempt(a, 'COMMIT')}, B видит {rows(b)}")
b.execute("BEGIN")
print(f"4. B: BEGIN, SELECT                 B видит {rows(b)}")
a.execute("BEGIN IMMEDIATE")
a.execute("INSERT INTO m VALUES (4, 0.44)")
print(f"5. A: INSERT, COMMIT при чтении B   {attempt(a, 'COMMIT')}, B видит {rows(b)}")
b.execute("COMMIT")
if a.in_transaction:
    print(f"6. B: COMMIT; A: повторный COMMIT   {attempt(a, 'COMMIT')}, B видит {rows(b)}")
else:
    print(f"6. B: COMMIT                        B видит {rows(b)}")
print("файлы:", " ".join(sorted(f for f in os.listdir(".") if f.startswith("locks.db"))))
```

```bash
$ python3 locks.py delete
journal_mode = delete
1. A: BEGIN IMMEDIATE, INSERT       A видит 2, B видит 1
2. B: INSERT, пока пишет A          database is locked (0.54 с)
3. A: COMMIT                        ok (0.01 с), B видит 2
4. B: BEGIN, SELECT                 B видит 2
5. A: INSERT, COMMIT при чтении B   database is locked (0.53 с), B видит 2
6. B: COMMIT; A: повторный COMMIT   ok (0.01 с), B видит 3
файлы: locks.db
$ python3 locks.py wal
journal_mode = wal
1. A: BEGIN IMMEDIATE, INSERT       A видит 2, B видит 1
2. B: INSERT, пока пишет A          database is locked (0.53 с)
3. A: COMMIT                        ok (0.01 с), B видит 2
4. B: BEGIN, SELECT                 B видит 2
5. A: INSERT, COMMIT при чтении B   ok (0.00 с), B видит 2
6. B: COMMIT                        B видит 3
файлы: locks.db locks.db-shm locks.db-wal
```

В режиме DELETE незафиксированная строка A соединению B не видна, а попытка B вставить свою строку ждёт 0,5 с и завершается ошибкой `database is locked`: писатель может быть только один. После фиксации A соединение B видит две строки. Затем B открывает читающую транзакцию, A вставляет ещё строку, и его `COMMIT` через 0,5 с тоже получает `database is locked`: фиксации мешает открытое чтение. Транзакция A при этом не теряется: после `COMMIT` в B повторный `COMMIT` в A проходит, и B видит три строки. В режиме WAL второй писатель по-прежнему получает отказ, но `COMMIT` при открытом чтении B проходит сразу, а B до конца своей транзакции видит снимок с двумя строками и лишь в новой транзакции видит три. Рядом с базой появляются файлы `locks.db-wal` и `locks.db-shm`.

### Многоверсионность в PostgreSQL

PostgreSQL изолирует транзакции не блокировками на чтение, а многоверсионностью (multiversion concurrency control, MVCC). `UPDATE` не меняет строку на месте: он записывает новую версию строки, а у старой отмечает в служебном поле `xmax` номер изменившей транзакции; у каждой версии в поле `xmin` записан номер создавшей её транзакции. Каждый запрос работает со снимком — сведениями о том, какие транзакции были зафиксированы к его началу, — и по `xmin` и `xmax` решает, какую из версий видеть. Поэтому читатели не ждут писателей, а писатели не ждут читателей; ждать друг друга приходится только транзакциям, изменяющим одну и ту же строку. Откат дёшев: транзакция лишь помечается прерванной, а её версии становятся невидимыми.

Покажем, как версии строки видны на разных уровнях изоляции. Скрипт `mvcc.py` открывает два сеанса. Сеанс A работает в режиме автофиксации, в котором каждая команда составляет отдельную транзакцию, а сеанс B начинает транзакцию на заданном уровне изоляции и читает строку вместе с полями `xmin` и `xmax`.

```python
"""Два сеанса PostgreSQL: версии строки и уровень изоляции читателя."""
import sys

import psycopg

LEVEL = sys.argv[1]                        # READ COMMITTED или REPEATABLE READ
DSN = "host=127.0.0.1 user=postgres password=lab"
ROW = "SELECT xmin, xmax, energy FROM runs WHERE id = 1"

a = psycopg.connect(DSN, autocommit=True)  # A: каждая команда — своя транзакция
b = psycopg.connect(DSN, autocommit=True)  # B: транзакция открывается явно
a.execute("DROP TABLE IF EXISTS runs")
a.execute("CREATE TABLE runs (id int PRIMARY KEY, energy real)")
a.execute("INSERT INTO runs VALUES (1, 5.0)")


def show(who, con):
    xmin, xmax, energy = con.execute(ROW).fetchone()
    print(f"{who:26s} xmin={xmin} xmax={xmax} energy={energy}")


print("уровень изоляции B:", LEVEL)
b.execute(f"BEGIN ISOLATION LEVEL {LEVEL}")
show("B: BEGIN, SELECT", b)
a.execute("UPDATE runs SET energy = 5.5 WHERE id = 1")
show("A: UPDATE зафиксирован", a)
show("B: тот же SELECT", b)
try:
    b.execute("UPDATE runs SET energy = energy + 1 WHERE id = 1")
    b.execute("COMMIT")
    show("B: свой UPDATE, COMMIT", b)
except psycopg.errors.SerializationFailure as e:
    print(f"{'B: свой UPDATE':26s} {e.diag.message_primary}")
    b.execute("ROLLBACK")
```

```bash
$ python3 mvcc.py "READ COMMITTED"
уровень изоляции B: READ COMMITTED
B: BEGIN, SELECT           xmin=747 xmax=0 energy=5.0
A: UPDATE зафиксирован     xmin=748 xmax=0 energy=5.5
B: тот же SELECT           xmin=748 xmax=0 energy=5.5
B: свой UPDATE, COMMIT     xmin=749 xmax=0 energy=6.5
$ python3 mvcc.py "REPEATABLE READ"
уровень изоляции B: REPEATABLE READ
B: BEGIN, SELECT           xmin=752 xmax=0 energy=5.0
A: UPDATE зафиксирован     xmin=753 xmax=0 energy=5.5
B: тот же SELECT           xmin=752 xmax=753 energy=5.0
B: свой UPDATE             could not serialize access due to concurrent update
```

На уровне READ COMMITTED сеанс B сначала видит версию с `xmin=747`; после того как A изменил строку и зафиксировал изменение, тот же запрос в той же транзакции B возвращает новую версию, `xmin=748` и `energy=5.5`. Это неповторяемое чтение. Собственный `UPDATE` в B прибавляет единицу к последнему зафиксированному значению, и после фиксации значение равно 6,5. На уровне REPEATABLE READ сеанс B после изменения в A продолжает видеть старую версию: `xmin=752` и `xmax=753`, то есть версия уже удалена транзакцией 753, но снимок B взят до её фиксации. Когда B пытается изменить эту строку, PostgreSQL отвечает ошибкой `could not serialize access due to concurrent update`: изменение по устаревшему снимку потеряло бы обновление из A, и транзакцию B необходимо повторить. Номера транзакций зависят от предыстории сервера и при повторе опыта будут другими.

Обратная сторона многоверсионности — мёртвые версии, которые не видит уже ни один снимок. Их убирает команда `VACUUM`, обычно запускаемая автоочисткой. Долгая транзакция или забытый открытый сеанс держат старый снимок, и `VACUUM` не может удалить версии, которые этот снимок ещё видит. Покажем это на таблице из 100 000 строк с отключённой автоочисткой; число живых и мёртвых версий и размер файла считает функция `pgstattuple` одноимённого расширения:

```python
import psycopg

DSN = "host=127.0.0.1 user=postgres password=lab"
a = psycopg.connect(DSN, autocommit=True)
a.execute("CREATE EXTENSION IF NOT EXISTS pgstattuple")
a.execute("DROP TABLE IF EXISTS runs_log")
a.execute("CREATE TABLE runs_log (id int PRIMARY KEY, energy real) "
          "WITH (autovacuum_enabled = off)")      # автоочистка не вмешивается
a.execute("INSERT INTO runs_log SELECT i, 5.0 FROM generate_series(1, 100000) AS i")


def state(stage):
    live, dead, size = a.execute(
        "SELECT tuple_count, dead_tuple_count, table_len FROM pgstattuple('runs_log')"
    ).fetchone()
    print(f"{stage:28s} живых {live:6d}, мёртвых {dead:6d}, файл {size / 2**20:.1f} МиБ")


state("после вставки")
b = psycopg.connect(DSN, autocommit=True)
b.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")    # долгая транзакция
b.execute("SELECT count(*) FROM runs_log").fetchone()  # снимок взят
a.execute("UPDATE runs_log SET energy = energy + 0.5")
state("после UPDATE всех строк")
a.execute("VACUUM runs_log")
state("VACUUM при открытом снимке")
b.execute("COMMIT")
a.execute("VACUUM runs_log")
state("VACUUM после COMMIT в B")
a.execute("VACUUM FULL runs_log")
state("VACUUM FULL")
```

    после вставки                живых 100000, мёртвых      0, файл 3.5 МиБ
    после UPDATE всех строк      живых 100000, мёртвых 100000, файл 6.9 МиБ
    VACUUM при открытом снимке   живых 100000, мёртвых 100000, файл 6.9 МиБ
    VACUUM после COMMIT в B      живых 100000, мёртвых      0, файл 6.9 МиБ
    VACUUM FULL                  живых 100000, мёртвых      0, файл 3.5 МиБ

`UPDATE` всех строк удвоил файл: новые версии записаны рядом со старыми. `VACUUM` при открытом снимке B не удалил ни одной мёртвой версии, после завершения транзакции B удалил все, но файл остался прежнего размера. Обычный `VACUUM` освобождает место внутри файла, и следующие изменения займут его, а уменьшает файл, лишь когда освободились страницы в самом его конце; сжимает таблицу `VACUUM FULL`, переписывая её под исключительной блокировкой. При частых изменениях и долгих транзакциях таблица и её индексы разрастаются, и простой запрос начинает читать тысячи мёртвых версий ради одной живой. Поэтому долгие транзакции необходимо находить по столбцам `xact_start` и `backend_xmin` представления `pg_stat_activity` и завершать.

## SQLite, PostgreSQL или MySQL

Три реляционные СУБД, чаще всего встречающиеся в лаборатории, различаются не языком запросов (SQL везде почти один и тот же), а тем, кто и каким образом получает доступ к базе.

| | SQLite | PostgreSQL | MySQL / MariaDB |
|---|---|---|---|
| Архитектура | встраиваемая библиотека, вся база в одном файле | клиент-серверная, процесс на соединение | клиент-серверная, поток на соединение |
| Установка | не нужна, есть в Python | отдельный сервис | отдельный сервис |
| Одновременная запись | одна пишущая транзакция в каждый момент | много клиентов | много клиентов |
| Изоляция по умолчанию | сериализуемая | READ COMMITTED | REPEATABLE READ |
| Типизация | динамическая, строгая в таблицах STRICT | строгая, богатая (массивы, JSONB, диапазоны) | строгая, скромнее |
| Права доступа | нет (права на файл) | пользователи, роли, гранулярные права | пользователи и права |
| Сильная сторона | нулевая настройка, переносимость | функциональность и расширения (PostGIS, TimescaleDB) | распространённость в веб-хостинге |
| Типичный случай | локальные данные, прототипы, базы до десятков и сотен ГБ на локальном диске | серверное приложение, общая база группы | веб-проекты, унаследованные системы |

Если данные лежат на локальном диске и работают с ними один исследователь и его скрипты, то выбирается **SQLite**. Если база нужна нескольким людям или сервисам по сети, если в неё пишут одновременно и требуются права доступа, то предпочтительнее **PostgreSQL**: сегодня это выбор по умолчанию для серверной СУБД, а его внутреннее устройство подробно описано в книге Е. Рогова «PostgreSQL 18 изнутри» [17], которая свободно распространяется в электронном виде. **MySQL** чаще достаётся как данность вместе с унаследованным проектом или хостингом, чем выбирается осознанно для новой системы.

## ORM: SQLAlchemy

SQL в виде строк внутри Python-кода не проверяется до запуска, результаты приходят кортежами, а логика, связывающая объект с его окружением, оказывается распределённой по запросам. **ORM** (Object-Relational Mapping) отображает таблицы на классы, строки на объекты, а внешние ключи на атрибуты-связи. Стандартом де-факто в Python является [SQLAlchemy](https://docs.sqlalchemy.org/en/21/). Во второй версии модели описываются аннотациями `Mapped` и функцией `mapped_column`, запросы строятся функцией `select`, а выполняются в сеансе `Session`, который отслеживает изменённые объекты и при `commit` превращает их в `INSERT` и `UPDATE`. Пример работает с отдельной базой `orm.db`: модели описывают только часть столбцов схемы журнала, и вставка в `lab.db` нарушила бы ограничения `NOT NULL` её таблиц.

```python
import sys

from sqlalchemy import ForeignKey, create_engine, event, select
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, Session, mapped_column, relationship, selectinload,
)


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    energy_mev: Mapped[float]
    # связь «один ко многим»: у захода — список измерений
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="run"
    )


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    channel: Mapped[str]
    value: Mapped[float]
    run: Mapped[Run] = relationship(back_populates="measurements")


# отдельная база примера; адрес можно передать аргументом
engine = create_engine(sys.argv[1] if len(sys.argv) > 1 else "sqlite:///orm.db")
Base.metadata.drop_all(engine)    # пример начинается с пустой базы
Base.metadata.create_all(engine)  # таблицы создаются по классам

with Session(engine) as session:
    # объекты вместо INSERT: связи расставляются сами
    for energy in (8.0, 12.5, 15.0):
        run = Run(energy_mev=energy)
        run.measurements.append(Measurement(channel="BPM01", value=0.03 * energy))
        session.add(run)
    session.commit()

    # запрос вместо SELECT ... JOIN: сразу нужные столбцы обеих таблиц
    stmt = (select(Measurement.channel, Measurement.value, Run.energy_mev)
            .join(Run).where(Run.energy_mev > 10.0))
    print(stmt.compile(engine))
    for channel, value, energy in session.execute(stmt):
        print(channel, round(value, 4), energy)
```

    SELECT measurements.channel, measurements.value, runs.energy_mev
    FROM measurements JOIN runs ON runs.id = measurements.run_id
    WHERE runs.energy_mev > ?
    BPM01 0.375 12.5
    BPM01 0.45 15.0

Перед результатом печатается SQL, который построил `select`: соединение `JOIN` с условием по внешнему ключу и параметр `?` драйвера `sqlite3`. Запрос выбирает сразу нужные столбцы обеих таблиц. Если же выбрать объекты, `select(Measurement).join(Run)`, и в цикле обращаться к `m.run.energy_mev`, соединение послужит только отбору строк: связь `Measurement.run` по умолчанию загружается лениво, и обращение к ней для каждого нового захода выполняет отдельный запрос `SELECT ... FROM runs WHERE runs.id = ?`. Это проблема N+1: один запрос за списком и по запросу на каждый его элемент. Число запросов к базе подсчитывает обработчик события `before_cursor_execute`; продолжение того же скрипта обходит заходы и обращается к их измерениям:

```python
# число запросов к базе при обходе связей
queries = []
event.listen(engine, "before_cursor_execute",
             lambda *args: queries.append(args[2]))
for options in ([], [selectinload(Run.measurements)]):
    queries.clear()
    with Session(engine) as session:
        for run in session.scalars(select(Run).options(*options)):
            len(run.measurements)  # обращение к связи
    print("selectinload:" if options else "ленивая загрузка:", len(queries), "запроса")
```

    ленивая загрузка: 4 запроса
    selectinload: 2 запроса

При ленивой загрузке обращение к связи `measurements` у каждого из трёх заходов выполняет отдельный запрос, всего их четыре — один за заходами и три за точками; опция `selectinload` позволяет обойтись двумя запросами: за заходами и затем за всеми их точками одним запросом с условием `IN`. Явное соединение `join` заполняет связь, только если указать опцию `contains_eager`.

Смена SQLite на PostgreSQL сводится к замене адреса в `create_engine` и установке драйвера (`pip install "psycopg[binary]"`); для простых моделей остальной код не меняется, а различия типов и поведения проявляются на сложных схемах. Тот же скрипт работает с отдельной базой `orm`, созданной в контейнере командой `docker exec pg createdb -U postgres orm`:

```bash
$ python3 orm_demo.py postgresql+psycopg://postgres:lab@127.0.0.1/orm
SELECT measurements.channel, measurements.value, runs.energy_mev
FROM measurements JOIN runs ON runs.id = measurements.run_id
WHERE runs.energy_mev > %(energy_mev_1)s
BPM01 0.375 12.5
BPM01 0.45 15.0
ленивая загрузка: 4 запроса
selectinload: 2 запроса
```

Текст SQL тот же, отличается только запись параметра: `%(energy_mev_1)s` в стиле psycopg.

ORM оправдан в приложении с десятком связанных таблиц и развивающейся схемой (накопленные миграции удобно вести инструментом [Alembic](https://alembic.sqlalchemy.org/)), при командной разработке и множестве типовых операций «создать-прочитать-обновить-удалить». Чистый SQL предпочтителен для аналитических запросов с многоуровневыми агрегатами и оконными функциями (SQL здесь лаконичнее ORM-конструкций), для массовых загрузок и разовых скриптов. ORM не освобождает от знания SQL: он генерирует тот же SQL, и когда запрос выполняется медленно, разбираться приходится со сгенерированным текстом; для этого достаточно включить `create_engine(..., echo=True)` и просмотреть запросы, уходящие в базу.

## Эксплуатация

> **Слайды к главе.** Резервные копии и их восстановление, журнал WAL и восстановление на момент времени, репликация, масштабирование, мониторинг, нереляционные хранилища и выбор СУБД изложены также в шестой части лекции «Базы данных» с демонстрациями в терминале; слайды лекции доступны [на сайте книги](https://phys-dev.github.io/soft-dev-book/slides/lecture-13.html#/sec-ops) и [в PDF](https://github.com/phys-dev/soft-dev-book/releases/latest/download/soft-dev-book-lecture-13.pdf).

<iframe src="../slides/lecture-13.html#/sec-ops" title="Слайды лекции «Базы данных»: эксплуатация и выбор" loading="lazy" allowfullscreen style="width:100%; aspect-ratio:16/10; border:0; border-radius:6px"></iframe>

Раздел посвящён эксплуатации созданной базы: резервным копиям и восстановлению, журналу WAL и репликации, масштабированию и мониторингу.

### Резервные копии

Резервная копия защищает от того, от чего транзакции не защищают: от ошибочной команды `DROP TABLE` или `DELETE` без `WHERE`, сбоя диска, потери машины. Копирование файла базы SQLite командой `cp` корректно, только когда к базе никто не подключён. В режиме WAL подтверждённые транзакции до контрольной точки лежат в отдельном файле, и копия одного основного файла их теряет. Согласованную копию работающей базы обеспечивает метод `Connection.backup()` из Python или команда `VACUUM INTO`. Рассмотрим разницу на процессе сбора данных `writer.py`, который переводит базу `wal.db` в режим WAL, записывает и фиксирует 500 строк и продолжает работать с открытым соединением:

```python
"""Пишущий процесс: база в режиме WAL, 500 зафиксированных строк, соединение открыто."""
import signal
import sqlite3
import sys
import time

signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))   # kill — штатное завершение
con = sqlite3.connect("wal.db")
con.execute("PRAGMA journal_mode=WAL")
con.execute("CREATE TABLE m (t REAL, value REAL)")
with con:                                                   # транзакция зафиксирована
    con.executemany("INSERT INTO m VALUES (?, ?)", [(i / 10, 0.4) for i in range(500)])
try:
    while True:                                             # процесс сбора данных работает
        time.sleep(1)
finally:
    con.close()             # последнее соединение: контрольная точка, файл -wal удаляется
```

Копию методом `backup()` делает скрипт `backup.py`:

```python
"""Онлайн-копия базы SQLite: Connection.backup()."""
import sqlite3
import sys

src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)                    # согласованная копия, включая страницы из -wal
dst.close()
src.close()
```

Сеанс в терминале:

```bash
$ python3 writer.py &
$ sleep 1; wc -c wal.db*
 4096 wal.db
32768 wal.db-shm
28872 wal.db-wal
65736 total
$ C="SELECT count(*) FROM m"
$ cp wal.db copy.db; python3 -m sqlite3 copy.db "$C"
OperationalError (SQLITE_ERROR): no such table: m
$ python3 backup.py wal.db bak.db; python3 -m sqlite3 bak.db "$C"
(500,)
$ python3 -m sqlite3 wal.db "VACUUM INTO 'into.db'"; python3 -m sqlite3 into.db "$C"
(500,)
$ kill %1; sleep 1; wc -c wal.db*
20480 wal.db
$ cp wal.db copy2.db; python3 -m sqlite3 copy2.db "$C"
(500,)
```

Основной файл занимает 4096 байт — одну страницу с заголовком, — а данные лежат в файле `wal.db-wal`. Копия основного файла открывается как база без таблиц: подтверждённые данные в неё не попали. `Connection.backup()` и `VACUUM INTO` делают согласованные копии с 500 строками. После завершения писателя его соединение закрывается штатно: последнее соединение выполняет контрольную точку, журнал переносится в основной файл, который вырастает до 20 480 байт, файлы `-wal` и `-shm` исчезают, и простая копия тоже содержит 500 строк.

Для PostgreSQL есть два способа. Утилита `pg_dump` создаёт логическую копию одной базы — SQL-команды или сжатый архив, который восстанавливает `pg_restore`, — на момент начала копирования; её можно развернуть и на более новой версии сервера. Утилита `pg_basebackup` снимает физическую копию файлов всего сервера, а вместе с непрерывным архивом журнала WAL позволяет восстановиться на любой момент времени. Рассмотрим первый способ на таблице `measurements` из опыта с `EXPLAIN ANALYZE` в главе «Базы данных»:

```bash
$ psql -c 'BEGIN' -c 'DROP TABLE measurements' -c 'ROLLBACK'
BEGIN
DROP TABLE
ROLLBACK
$ psql -c 'SELECT count(*) FROM measurements'
  count
---------
 1000000
(1 row)
$ docker exec pg pg_dump -U postgres -Fc > lab.dump; wc -c lab.dump
8678593 lab.dump
$ psql -c 'DROP TABLE measurements'
DROP TABLE
$ docker exec pg createdb -U postgres restored
$ docker exec -i pg pg_restore -U postgres -d restored < lab.dump
$ psql -d restored -c 'SELECT count(*) FROM measurements'
  count
---------
 1000000
(1 row)
```

Первая команда открывает транзакцию, удаляет таблицу и откатывает транзакцию: в PostgreSQL даже изменения схемы транзакционны, и после `ROLLBACK` таблица на месте со всем миллионом строк. Затем `pg_dump` записывает логическую копию базы в сжатом формате `custom` в файл `lab.dump` размером около 8,3 МиБ. Команда `DROP TABLE` без транзакции выполняется с автофиксацией, и таблица удалена безвозвратно. Восстановление идёт в отдельную базу `restored`, где сначала проверяют данные. Нужную таблицу затем возвращают в рабочую базу командой `pg_restore -t measurements`, однако этот ключ восстанавливает только определение и данные таблицы: первичный ключ, индексы и последовательность для столбца `id` записаны в архиве отдельными элементами, список которых выводит `pg_restore -l`.

Хранят копии по правилу «три-два-один»: три копии на двух видах носителей, одна из них — вне здания. Главное правило — копия без проверенного восстановления копией не считается: восстановление репетируют по инструкции на отдельной машине и проверяют, что данные на месте, а инструкцию пишут так, чтобы её выполнил дежурный ночью, а не только автор.

### Журнал WAL, восстановление на момент и реплики

Журнал упреждающей записи (write-ahead log, WAL) является основой надёжности PostgreSQL: каждое изменение сначала записывается в журнал, и только потом меняются файлы таблиц, поэтому после сбоя сервер восстанавливается, проигрывая журнал от последней контрольной точки. Тот же журнал решает ещё три задачи.

Для восстановления на любой момент необходимы базовая физическая копия и непрерывный архив сегментов WAL: ночная копия и архив журнала возвращают таблицу, ошибочно удалённую вечером, в состояние за секунду до команды. Это восстановление на момент времени (point-in-time recovery, PITR). Архив включают параметры основного сервера `archive_mode` и `archive_command`, базовую копию снимает `pg_basebackup`, а для восстановления необходимо положить в каталог копии файл `recovery.signal` и задать команду чтения архива `restore_command` и момент `recovery_target_time`. Отрепетируем восстановление на отдельном сервере в контейнере. Каталог `$P` на машине с Docker, принадлежащий пользователю с номером 70 (так в образе обозначен пользователь `postgres`), служит хранилищем архива и копий; команды выполняются от имени root.

```bash
$ P=$PWD/pitr; mkdir -p $P/wal; chown -R 70:70 $P
$ docker run -d --name pitr -e POSTGRES_PASSWORD=lab -v $P:/pitr postgres:17-alpine \
      -c archive_mode=on -c archive_command='cp %p /pitr/wal/%f' > /dev/null
$ until docker exec pitr pg_isready -h 127.0.0.1 -q; do sleep 0.5; done
$ docker exec -u postgres pitr pg_basebackup -D /pitr/base -X stream -c fast
$ alias pq='docker exec -i -u postgres pitr psql -X -q'
$ pq -c "CREATE TABLE runs_log AS SELECT i AS id FROM generate_series(1, 1000) AS i"
$ pq -At -c "SELECT now()"
2026-10-03 03:45:54.2944+00
$ sleep 1; pq -c "DROP TABLE runs_log"
$ pq -At -c "SELECT pg_walfile_name(pg_switch_wal())"
000000010000000000000004
```

Сервер с архивом создаёт таблицу `runs_log` из 1000 строк, запоминается момент времени, через секунду таблица удаляется, а функция `pg_switch_wal()` закрывает текущий сегмент журнала, чтобы он попал в архив. Затем копия разворачивается в новый каталог, и на ней запускается второй сервер:

```bash
$ docker rm -f -v pitr > /dev/null
$ cp -a $P/base $P/restore; touch $P/restore/recovery.signal
$ cat >> $P/restore/postgresql.auto.conf << EOF
restore_command = 'cp /pitr/wal/%f %p'
recovery_target_time = '2026-10-03 03:45:54.2944+00'
recovery_target_action = 'promote'
EOF
$ docker run -d --name pitr2 -e PGDATA=/pitr/restore -v $P:/pitr postgres:17-alpine > /dev/null
$ sleep 5; docker logs pitr2 2>&1 | grep -E 'point-in-time|stopping|new timeline|archive recovery' | sed 's/.*LOG:  //'
starting point-in-time recovery to 2026-10-03 03:45:54.2944+00
recovery stopping before commit of transaction 740, time 2026-10-03 03:45:55.352384+00
selected new timeline ID: 2
archive recovery complete
$ docker exec -u postgres pitr2 psql -X -c "SELECT count(*) FROM runs_log"
 count
-------
  1000
(1 row)
```

Восстановление остановилось перед фиксацией транзакции 740, то есть перед командой `DROP TABLE`, сервер перешёл на новую линию времени (timeline) и вернул таблицу со всеми 1000 строками. Параметр `recovery_target_action = 'promote'` переводит сервер в обычный режим сразу после достижения цели. По умолчанию сервер останавливается на паузе, чтобы данные можно было проверить до продвижения, однако таблицу, которую удаляла незавершённая транзакция, на паузе держит её блокировка: в первом запуске опыта, без этого параметра, запрос к `runs_log` ждал её освобождения, которое наступает только после продвижения сервера вызовом `pg_wal_replay_resume()`.

Если передавать журнал потоком на другой сервер, получается физическая реплика, представляющая собой побайтовую копию всего сервера, доступную только для чтения; она требует той же основной версии PostgreSQL и той же архитектуры и служит для резервирования и разгрузки чтения. Логическая репликация расшифровывает журнал в изменения строк выбранных таблиц и передаёт их подписчику, который может работать на другой версии PostgreSQL; так переходят на новую версию с минимальным простоем, а сторонние средства логического декодирования тем же способом перекладывают изменения в аналитическую систему. Реплика не заменяет резервную копию: ошибочный `DROP TABLE` доходит до неё за доли секунды.

### Масштабирование

Один сервер PostgreSQL на современном оборудовании годами обслуживает базу лаборатории и даже института, и масштабирование начинают с дешёвых шагов. Пул соединений, например PgBouncer, позволяет тысячам клиентов работать через десятки серверных процессов. Реплики разгружают основной сервер от чтения: отчёты и графики строятся по реплике, хотя она может отставать на доли секунды. Секционирование делит большую таблицу на части по диапазону, например временной ряд датчиков по месяцам, и позволяет удалять данные старше срока хранения одной командой вместо медленного `DELETE`, а запросу за неделю — читать одну секцию.

```sql
CREATE TABLE readings (
    ts      timestamptz NOT NULL,
    channel text NOT NULL,
    value   real NOT NULL
) PARTITION BY RANGE (ts);
CREATE TABLE readings_2026_08 PARTITION OF readings
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE readings_2026_09 PARTITION OF readings
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
INSERT INTO readings
SELECT ts, 'P_vacuum', 1e-7 * (1 + random())
FROM generate_series(timestamptz '2026-08-01', '2026-09-30 23:59', '1 min') AS ts;
EXPLAIN (COSTS OFF)
SELECT avg(value) FROM readings
WHERE ts >= '2026-09-20' AND ts < '2026-09-27';
DROP TABLE readings_2026_08;          -- август удаляется одной командой
SELECT count(*) FROM readings;
```

```bash
$ psql < part.sql
CREATE TABLE
CREATE TABLE
CREATE TABLE
INSERT 0 87840
                                                                 QUERY PLAN
--------------------------------------------------------------------------------------------------------------------------------------------
 Aggregate
   ->  Seq Scan on readings_2026_09 readings
         Filter: ((ts >= '2026-09-20 00:00:00+00'::timestamp with time zone) AND (ts < '2026-09-27 00:00:00+00'::timestamp with time zone))
(3 rows)

DROP TABLE
 count
-------
 43200
(1 row)
```

План запроса за неделю сентября содержит только секцию `readings_2026_09`: условие на `ts` исключило августовскую секцию ещё при планировании. Августовские данные удалены командой `DROP TABLE` без перебора строк, и в таблице осталось 43 200 минутных отсчётов сентября.

Шардирование распределяет данные по нескольким серверам по ключу; запросы внутри одного шарда остаются быстрыми, а соединения и транзакции между шардами дороги, поэтому небольшие справочники копируют на каждый шард или денормализуют. Встроенное шардирование есть у ClickHouse, MongoDB и YDB, а в PostgreSQL его добавляет расширение Citus или реализует само приложение. Если заранее ясно, что данные не поместятся на один сервер, шардирование закладывают с самого начала: переделка работающей базы в десятки терабайт отнимает месяцы работы целой команды. Репликация, шардирование и кеширование подробнее рассматриваются в главе [«Системный дизайн»](./system-design.md).

### Мониторинг

СУБД наблюдают как любое приложение, но с поправкой на её особенности. Первая группа показателей — ресурсы: процессор, память, свободное место и число свободных индексных дескрипторов (inode) на диске, число операций ввода-вывода в секунду; диск для базы чаще всего оказывается узким местом. Вторая группа — запросы: их число в секунду, задержки по перцентилям p50 и p99, а не по среднему, которое скрывает медленные запросы, и распределение по типам; рост доли чтений указывает на отказ кеша перед базой, лавина `UPDATE` — на ошибку в приложении. Третья группа — ошибки. Под нагрузкой они в журнале бывают всегда, например при обрыве соединения клиентом, поэтому тревогу поднимают по превышению порога, а не по каждой записи. Необходимы и нижние пороги: если нагрузка на базу снизилась до нуля, это авария, хотя ни один верхний порог не превышен, — например, данные удалены, и запросам стало нечего делать.

Специфические признаки PostgreSQL дают системные представления. Самые дорогие запросы показывает расширение `pg_stat_statements`, загруженное при запуске контейнера в главе «Базы данных»:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
-- самые дорогие запросы с запуска сервера
SELECT calls, round(total_exec_time) AS total_ms,
       left(regexp_replace(query, '\s+', ' ', 'g'), 45) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 5;
```

```bash
$ psql < monitor.sql
CREATE EXTENSION
 calls | total_ms |                     query
-------+----------+-----------------------------------------------
     1 |     2276 | INSERT INTO measurements (run_id, channel, t,
     1 |     1127 | COPY public.measurements (id, run_id, channel
     1 |      710 | COPY public.measurements (id, run_id, channel
     1 |      146 | UPDATE runs_log SET energy = energy + $1
     1 |      100 | CREATE INDEX m_run_ch ON measurements (run_id
(5 rows)
```

Расширение складывает статистику по нормализованному тексту запроса, в котором константы заменены параметрами `$1`, `$2` и так далее. С запуска сервера, то есть за время опытов этой главы и главы «Базы данных», больше всего времени заняли заполнение таблицы скриптом `fill.sql` из опыта с `EXPLAIN ANALYZE` и команды `COPY`, которыми `pg_dump` и `pg_restore` переносят данные, а затем `UPDATE` всех строк в опыте с разрастанием таблицы и создание индекса `m_run_ch`.

Число мёртвых версий строк по таблицам показывает представление `pg_stat_user_tables`, отставание реплик — `pg_stat_replication`:

```sql
-- мёртвые версии строк по таблицам
SELECT relname, n_live_tup, n_dead_tup
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
```

Счётчики этих представлений обновляются асинхронно и являются оценками; точные числа даёт функция `pgstattuple` из опыта с разрастанием таблицы. Если выделенного администратора баз данных нет, первым вариантом рассматривают управляемую СУБД облачного провайдера, который берёт на себя копии, обновления и мониторинг.

## Нереляционные базы данных

Под конкретные профили нагрузки существуют специализированные базы, объединяемые общим названием «NoSQL». Их устройство и цена каждого компромисса подробно рассмотрены у Клеппмана [16].

Проще всех устроено хранилище пар «ключ → значение» [Redis](https://redis.io/) и его открытое ответвление [Valkey](https://valkey.io/). Данные располагаются в оперативной памяти, и операции занимают доли миллисекунды. Типичные роли: кеш (результат тяжёлого запроса или расчёта помещается под ключ с заданным временем жизни), очереди задач между процессами (Redis служит брокером очередей Celery), счётчики и уведомления по подписке (pub/sub). По умолчанию Redis периодически сохраняет снимок данных на диск; журнал всех записей (AOF) включается отдельно и сокращает потерю данных при сбое примерно до секунды, а для чистого кеша сохранение отключают. Команды выполняются в одном потоке, поэтому `KEYS` со звёздочкой, перебирающая все ключи, на время перебора блокирует сервер для всех клиентов, а перебор ведут командой `SCAN`. В 2024 году Redis сменил лицензию на несвободную, и сообщество под эгидой Linux Foundation продолжило открытый проект под названием Valkey; в 2025 году Redis 8 вышел и под свободной лицензией AGPLv3. Redis отвечает за скорость и не является главным хранилищем истины; типичные приёмы собраны у Карлсона [19].

Сервер для опытов запускается в контейнере так же, как PostgreSQL:

```bash
docker run -d --rm --name redis -p 127.0.0.1:6379:6379 redis:8-alpine
alias redis-cli='docker exec -i redis redis-cli'
```

```bash
$ redis-cli CONFIG GET save
save
3600 1 300 100 60 10000
$ redis-cli CONFIG GET appendonly
appendonly
no
$ redis-cli SET todos:page:0 '{"result": []}' EX 60
OK
$ redis-cli TTL todos:page:0
60
$ redis-cli INCR runs:counter
1
$ redis-cli SCAN 0 MATCH 'todos:page:*'
0
todos:page:0
```

Настройка `save` по умолчанию сохраняет снимок через час после первого изменения, через пять минут после ста изменений и через минуту после десяти тысяч, а `appendonly no` означает, что журнал AOF выключен. Ключ, записанный с параметром `EX 60`, живёт 60 секунд, `INCR` атомарно увеличивает счётчик, а `SCAN` перебирает ключи по шаблону порциями, не блокируя сервер надолго: первым числом он возвращает курсор следующей порции, и ноль означает, что перебор завершён.

Там, где у записей нет общей структуры, применяют документные базы наподобие [MongoDB](https://www.mongodb.com/). Единицей хранения является документ — вложенная структура наподобие JSON; документы собираются в коллекции, и жёсткой схемы нет, поэтому соседние документы могут иметь разные поля. Это удобно для разнородных метаданных, меняющих структуру от записи к записи. Схему MongoDB по умолчанию не навязывает, и проверяет её код; правила можно задать и в самой базе валидатором `$jsonSchema` на коллекции, который отклоняет или помечает нарушающие их документы. Практические следствия рассмотрены в руководстве по MongoDB [18].

Телеметрию установки (давление в вакуумной камере, токи магнитов, температуры), приходящую с сотен датчиков каждую секунду годами, в ускорительной технике называют slow control и хранят в базах временных рядов. [InfluxDB](https://www.influxdata.com/) предназначена для потока «метка времени → значение» с тегами. Такие базы позволяют автоматически прореживать и удалять устаревшие данные (retention policies), быстро агрегировать по окнам времени («среднее за каждую минуту последних суток») и стыкуются с [Grafana](https://grafana.com/) для панелей мониторинга. В мире PostgreSQL то же обеспечивает расширение TimescaleDB, построенное на секционировании по времени.

Наконец, для аналитики на миллиардах записей созданы колоночные базы, самой известной из которых является [ClickHouse](https://clickhouse.com/). Она хранит данные не по строкам, а по столбцам. Значения одного столбца располагаются рядом, хорошо сжимаются, и запрос «среднее value по миллиарду строк» читает с диска только нужные столбцы, укладываясь в секунды на обычном сервере вместо часов; диалект SQL привычный. Колоночные базы рассчитаны на дозапись и анализ. Вставляют данные крупными партиями: каждая вставка создаёт на диске новый кусок, который затем сливается с соседними, и поток вставок по одной строке приводит к ошибке `Too many parts`. Точечные `UPDATE` и `DELETE` в ClickHouse есть в лёгкой форме, но частые правки отдельных строк остаются дорогими.

### Выбор хранилища: пример реальной системы

Система хранения данных ускорительного комплекса использует сразу три базы. Такой подход называется **полиглотным хранением** (polyglot persistence): под каждый профиль данных выбирается своё хранилище.

В PostgreSQL помещается всё, что должно быть строгим: пользователи и их роли, конфигурация ускорителя и его элементов, метаданные экспериментов (что за эксперимент, когда, кто ответственный), расписание работы установки и журнал событий. Структура этих данных известна заранее, меняется редко, а целостность критична: если запись эксперимента ссылается на несуществующего оператора, это ошибка, обнаруживать которую должна база, а не код. Здесь необходимы схема, внешние ключи и ACID-транзакции.

В MongoDB помещается всё разнородное: результаты измерений, данные пучка (траектории, размеры, интенсивность), временные ряды параметров, результаты моделирования и оптимизации. У этих данных нет единой схемы: каждый новый тип эксперимента приносит свой набор полей. Требование миграции базы под каждую новую методику приводит к тому, что данные складывают мимо базы, в файлы на рабочем столе.

Redis хранит недолго живущее: кеш частых запросов, текущие состояния устройств, сессии пользователей веб-интерфейса, очереди сообщений между компонентами. Значение тока магнита *в текущий момент* запрашивается сотни раз в секунду, и обращаться за ним в дисковую базу бессмысленно. Потеря этих данных при перезапуске неприятна, но не катастрофична: истина хранится в двух других базах.

Выбор сводится к одному признаку на каждую базу.

| Признак данных | Подходящая база |
|---|---|
| Структура известна заранее, а нарушение связей недопустимо | PostgreSQL |
| Структура меняется от записи к записи | MongoDB |
| Данные нужны очень быстро, а их потеря допустима | Redis |

Цена полиглотного хранения: как только данные распределяются по трём базам, **исчезает транзакция, охватывающая их все**, и одним атомарным действием уже нельзя записать эксперимент в PostgreSQL вместе с его результатами в MongoDB. Согласованность необходимо обеспечивать вручную, распределёнными транзакциями или компенсирующими действиями, откатывающими то, что успело записаться. Эта сложность оправдана, только когда профили данных действительно различны.

### Выбор СУБД

Выбор СУБД начинают с вопроса, насколько технология «скучна» в смысле эссе Д. Маккинли «Choose Boring Technology» (2015): система, которая работает десятилетиями, имеет известные ошибки, документацию, сотни специалистов и платную поддержку, реже приводит к неожиданностям, чем новая база с несколькими выпусками. Далее проверяют, есть ли резервное копирование с восстановлением на момент времени и насколько просто проверить восстановление. Оценивают объём и рост данных: если ясно, что один сервер не справится, нужна система со встроенным шардированием или заранее спланированное собственное. Разные нагрузки разводят по разным системам: транзакционная база для записи и аналитическая копия для отчётов проще в эксплуатации, чем одна система для всего. Ищут описания неудач, а не только успехов: если в блоге разработчиков одни победы, а на форумах только вопросы о подключении, о слабых местах системы известно мало, и первым с ними столкнётся сам пользователь. Проверяют безопасность по умолчанию: у FoundationDB, например, сетевой доступ к порту без настроенного TLS даёт полные права, а встроенная авторизация помечена в документации как экспериментальная.

В студенческом проекте **целесообразно начинать с одной базы**. Данные одного исследователя и его скриптов хранит SQLite, общую базу группы — PostgreSQL. Одна PostgreSQL закрывает потребности лабораторного сервиса на годы вперёд, а для документов в ней есть тип `JSONB`, индексируемый по полям внутри документа. Вторую базу заводят не потому, что так делают в больших системах, а когда первая измеримо перестала справляться с конкретным профилем нагрузки.

## Одна задача в четырёх хранилищах

Рассмотрим учебный сервис, список записей с операциями «прочитать страницу», «добавить», «изменить», «удалить», и переложим его последовательно в четыре хранилища: текстовый файл со строками произвольной длины, файл с записями фиксированной длины, реляционную базу и кеш поверх неё.

Код почти не меняется от варианта к варианту; меняется то, где лежат данные и во что обходится каждая операция. Сложность операций рассматривалась в главе [«Основные структуры данных»](../cs/basic-structures.md).

Сервис написан на микрофреймворке [Flask](https://flask.palletsprojects.com/): декоратор `@app.route` привязывает функцию к URL и методу, объект `request` даёт доступ к параметрам и телу запроса, а словарь, возвращённый функцией, Flask отдаёт клиенту как JSON. Изменение и удаление несуществующей записи во всех вариантах отвечает кодом 404 Not Found (коды ответа HTTP рассмотрены в главе [«Веб-технологии»](./web.md)). Заголовочная часть общая для всех вариантов и далее не повторяется; варианты с базой и кешем добавляют к ней пул соединений и клиент Redis. Все четыре варианта проверены тестовым клиентом Flask 3.1 (`app.test_client()`) с PostgreSQL и Redis в контейнерах.

```python
import json
import os

from flask import Flask, Response, request

app = Flask(__name__)

FILE_PATH = 'data.txt'
PAGE_SIZE = 20
ELEMENT_SIZE = 64
FILL_CHAR = b'\0'          # заполнитель, которого нет в тексте записей
```

### Наивное решение. GET

Самый прямолинейный вариант — обычный текстовый файл, по строке на запись; запись с символом перевода строки разорвала бы файл на две строки, поэтому вариант годится только для однострочного текста. Чтобы отдать одну страницу, приходится прочитать весь файл, а при изменении и удалении ещё и переписать его заново: \\(O(n)\\) на каждую операцию. Пустой файл создаётся при запуске, чтобы чтение до первой записи не завершалось ошибкой.

```python
open(FILE_PATH, 'a').close()        # пустой файл, если его ещё нет


@app.route('/', methods=['GET'])
def paginated_get():
    page = int(request.args.get('page', '0'))
    first = page * PAGE_SIZE
    last = first + PAGE_SIZE
    result = []
    with open(FILE_PATH, 'r') as f:
        for i, line in enumerate(f.readlines()[first:last]):
            result.append({'id': first + i, 'data': line.rstrip('\n')})
    return {"result": result}
```

### Наивное решение. POST

```python
@app.route('/', methods=['POST'])
def post():
    data = request.json['data']
    with open(FILE_PATH, 'a') as f:
        f.write(data + '\n')
    return {}, 201
```

### Наивное решение. PUT

Номер записи совпадает с номером строки, и запись с номером за концом файла не существует: сервис отвечает 404, а не завершается исключением `IndexError`.

```python
@app.route('/<int:data_id>', methods=['PUT'])
def put(data_id):
    data = request.json['data']
    with open(FILE_PATH, 'r') as f:
        new_data = f.readlines()
    if not 0 <= data_id < len(new_data):
        return {}, 404
    new_data[data_id] = data + '\n'
    with open(FILE_PATH, 'w') as f:
        f.writelines(new_data)
    return {}, 204
```

### Наивное решение. DELETE

```python
@app.route('/<int:data_id>', methods=['DELETE'])
def delete(data_id):
    with open(FILE_PATH, 'r') as f:
        new_data = f.readlines()
    if not 0 <= data_id < len(new_data):
        return {}, 404
    del new_data[data_id]
    with open(FILE_PATH, 'w') as f:
        f.writelines(new_data)
    return {}, 204
```

### Фиксированные записи. GET

Если отвести каждой записи одинаковое число байт, файл превращается в массив, и нужная запись читается сразу, переходом к её смещению через `seek()`. Зато удаление дорожает: хвост файла за ней приходится сдвигать вручную. Запись, длинная для отведённых 64 байт, сдвинула бы все последующие, поэтому вставка и изменение проверяют длину и отвечают 400 Bad Request. Заполнитель — нулевой байт: в отличие от пробела, он не встречается в тексте и не срезается вместе с пробелами самой записи. Страница у конца файла содержит столько записей, сколько их осталось.

```python
open(FILE_PATH, 'a').close()        # пустой файл, если его ещё нет


def count():
    """Число записей в файле."""
    return os.path.getsize(FILE_PATH) // ELEMENT_SIZE


@app.route('/', methods=['GET'])
def paginated_get():
    page = int(request.args.get('page', '0'))
    first = page * PAGE_SIZE
    result = []
    with open(FILE_PATH, 'rb') as f:
        f.seek(first * ELEMENT_SIZE)
        data = f.read(PAGE_SIZE * ELEMENT_SIZE)   # у конца файла записей меньше
    for i in range(len(data) // ELEMENT_SIZE):
        record = data[i * ELEMENT_SIZE:(i + 1) * ELEMENT_SIZE]
        result.append({"id": first + i,
                       "data": record.rstrip(FILL_CHAR).decode('utf-8')})
    return {"result": result}
```

### Фиксированные записи. POST

```python
@app.route('/', methods=['POST'])
def post():
    raw = str(request.json['data']).encode('utf-8')
    if len(raw) > ELEMENT_SIZE:
        return {"error": f"запись длиннее {ELEMENT_SIZE} байт"}, 400
    with open(FILE_PATH, 'ab') as f:
        f.write(raw.ljust(ELEMENT_SIZE, FILL_CHAR))
    return {}, 201
```

### Фиксированные записи. PUT

```python
@app.route('/<int:data_id>', methods=['PUT'])
def put(data_id):
    raw = str(request.json['data']).encode('utf-8')
    if len(raw) > ELEMENT_SIZE:
        return {"error": f"запись длиннее {ELEMENT_SIZE} байт"}, 400
    if data_id >= count():
        return {}, 404
    with open(FILE_PATH, 'r+b') as f:
        f.seek(data_id * ELEMENT_SIZE)
        f.write(raw.ljust(ELEMENT_SIZE, FILL_CHAR))
    return {}, 204
```

### Фиксированные записи. DELETE

```python
@app.route('/<int:data_id>', methods=['DELETE'])
def delete(data_id):
    if data_id >= count():
        return {}, 404
    with open(FILE_PATH, 'r+b') as f:
        point = data_id * ELEMENT_SIZE
        while True:                       # хвост файла сдвигается на одну запись
            f.seek(point + ELEMENT_SIZE)
            next_record = f.read(ELEMENT_SIZE)
            f.seek(point)
            if not next_record:
                f.truncate()
                break
            f.write(next_record)
            point += ELEMENT_SIZE
    return {}, 204
```

### Реляционная база. GET

База данных скрывает эту механику за индексами: поиск по ключу, вставку и удаление она выполняет за логарифмическое время, как структуры данных из главы [«Основные структуры данных»](../cs/basic-structures.md). Записи хранятся в таблице `todos` базы `lab` (`docker exec pg createdb -U postgres lab`):

```sql
CREATE TABLE todos (
    id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    todo text NOT NULL
);
```

Соединения с сервером открывает пул один раз на процесс, а каждый обработчик берёт соединение на время своего блока `with`, по выходе из которого транзакция фиксируется.

```python
from psycopg_pool import ConnectionPool

# соединения открываются один раз на процесс и затем переиспользуются
pool = ConnectionPool('host=localhost dbname=lab user=postgres password=lab',
                      open=True)


@app.route('/', methods=['GET'])
def paginated_get():
    page = int(request.args.get('page', '0'))
    with pool.connection() as conn:       # при выходе — COMMIT и возврат в пул
        rows = conn.execute(
            'SELECT "id", "todo" FROM "todos" ORDER BY "id" OFFSET %s LIMIT %s',
            (page * PAGE_SIZE, PAGE_SIZE),
        ).fetchall()
    return {"result": [{"id": row[0], "data": row[1]} for row in rows]}
```

Постраничная выдача через `OFFSET` линейна по номеру страницы: чтобы отдать страницу с большим номером, база проходит и отбрасывает все предыдущие строки. На восстановленной копии таблицы `measurements` из раздела о резервных копиях разница хорошо видна:

```sql
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT id, value FROM measurements ORDER BY id OFFSET 900000 LIMIT 20;
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT id, value FROM measurements WHERE id > 900000 ORDER BY id LIMIT 20;
```

```bash
$ psql -d restored < offset.sql
                                      QUERY PLAN
---------------------------------------------------------------------------------------
 Limit (actual rows=20 loops=1)
   ->  Index Scan using measurements_pkey on measurements (actual rows=900020 loops=1)
 Planning Time: 0.204 ms
 Execution Time: 57.325 ms
(4 rows)

                                    QUERY PLAN
-----------------------------------------------------------------------------------
 Limit (actual rows=20 loops=1)
   ->  Index Scan using measurements_pkey on measurements (actual rows=20 loops=1)
         Index Cond: (id > 900000)
 Planning Time: 0.037 ms
 Execution Time: 0.028 ms
(5 rows)
```

Для страницы со смещением 900 000 база прочитала по индексу 900 020 строк и отбросила все, кроме двадцати, а выборка по ключу прочитала ровно 20 строк: 57,3 мс против 0,028 мс. Поэтому длинные списки листают выборкой по ключу, `WHERE "id" > %s ORDER BY "id" LIMIT %s`, где параметром служит последний `id` предыдущей страницы.

### Реляционная база. POST

```python
@app.route('/', methods=['POST'])
def post():
    data = str(request.json['data'])
    with pool.connection() as conn:
        new_id = conn.execute(
            'INSERT INTO "todos" ("todo") VALUES (%s) RETURNING "id"', (data,)
        ).fetchone()[0]
    return {"id": new_id}, 201
```

### Реляционная база. PUT

Число изменённых строк сообщает атрибут `rowcount` курсора: ноль означает, что записи с таким `id` нет.

```python
@app.route('/<int:data_id>', methods=['PUT'])
def put(data_id):
    data = str(request.json['data'])
    with pool.connection() as conn:
        cur = conn.execute(
            'UPDATE "todos" SET "todo" = %s WHERE "id" = %s', (data, data_id)
        )
        if cur.rowcount == 0:             # такой записи нет
            return {}, 404
    return {}, 204
```

### Реляционная база. DELETE

```python
@app.route('/<int:data_id>', methods=['DELETE'])
def delete(data_id):
    with pool.connection() as conn:
        cur = conn.execute('DELETE FROM "todos" WHERE "id" = %s', (data_id,))
        if cur.rowcount == 0:
            return {}, 404
    return {}, 204
```

### Кеш. GET

Наконец, самые частые запросы можно не доводить до базы: готовый ответ помещается в Redis и в следующий раз отдаётся из оперативной памяти. Клиент Redis, как и пул, создаётся один раз на процесс и сам держит пул соединений. Ключи страниц получают префикс `todos:page:`, чтобы сброс затрагивал только их, а не сессии и очереди, которые в полиглотной системе лежат в том же Redis. Ответ из кеша отдаётся с типом `application/json`, как и ответы остальных вариантов.

```python
import redis
from psycopg_pool import ConnectionPool

TTL = 60
pool = ConnectionPool('host=localhost dbname=lab user=postgres password=lab',
                      open=True)
cache = redis.Redis(host='localhost', port=6379)   # один клиент на процесс


def page_key(page):
    return f'todos:page:{page}'


def drop_pages(first=0):
    """Сбрасывает закешированные страницы с номером first и дальше."""
    stale = [key for key in cache.scan_iter(match='todos:page:*')
             if int(key.rsplit(b':', 1)[1]) >= first]
    if stale:
        cache.delete(*stale)


@app.route('/', methods=['GET'])
def paginated_get():
    page = int(request.args.get('page', '0'))
    cached_page = cache.get(page_key(page))
    if cached_page is not None:
        return Response(cached_page, mimetype='application/json')
    with pool.connection() as conn:
        rows = conn.execute(
            'SELECT "id", "todo" FROM "todos" ORDER BY "id" OFFSET %s LIMIT %s',
            (page * PAGE_SIZE, PAGE_SIZE),
        ).fetchall()
    result = json.dumps({"result": [{"id": row[0], "data": row[1]} for row in rows]})
    cache.set(page_key(page), result, ex=TTL)
    return Response(result, mimetype='application/json')
```

Обратная сторона кеша: клиент, выполнивший POST или PUT, не увидит собственной правки, пока не истечёт `TTL`, и чем длиннее время жизни ключа, тем дольше сервис отдаёт устаревшее. Поэтому каждая изменяющая операция обязана сбрасывать затронутые ключи, и трудность заключается в том, чтобы определить, какие именно: правка обесценивает ту страницу, на которой находится запись, а вставка и удаление сдвигают нумерацию и обесценивают всё последующее. Ключи ищет команда `SCAN` (метод `scan_iter`), а не `KEYS`, которая на время перебора блокирует сервер; другой способ — номер версии в имени ключа, увеличиваемый при каждом изменении, после чего старые страницы просто истекают.

У кеша есть и две тонкости, которых этот вариант не решает. Первая — лавина промахов: когда истекает популярная страница, все запросы, пришедшие до её повторного заполнения, одновременно идут в базу. Защитой служит один загрузчик, когда страницу читает из базы только первый запрос, а остальные ждут его результата, или выдача устаревшего значения, пока свежее загружается. Вторая — гонка со сбросом: чтение, начавшееся до изменения, может положить в кеш устаревшую страницу уже после того, как изменение сбросило её ключ, и такая страница проживёт до истечения `TTL`. Оба явления подробно разобраны в главе [«Системный дизайн»](./system-design.md); в опыте той главы 50 одновременных промахов без защиты обращаются к базе 50 раз, а с одним загрузчиком — один.

### Кеш. POST

Вставка попадает в конец списка, однако выяснять, где он заканчивается, дороже, чем сбросить все страницы.

```python
@app.route('/', methods=['POST'])
def post():
    data = str(request.json['data'])
    with pool.connection() as conn:
        new_id = conn.execute(
            'INSERT INTO "todos" ("todo") VALUES (%s) RETURNING "id"', (data,)
        ).fetchone()[0]
    drop_pages()
    return {"id": new_id}, 201
```

### Кеш. PUT

Правка не сдвигает нумерацию, поэтому номер страницы вычисляется по числу записей, лежащих перед изменённой, и сбрасывается один ключ. Сброс выполняется после выхода из блока `with`, то есть после фиксации: страница, сброшенная до фиксации, могла бы снова попасть в кеш со старыми данными.

```python
@app.route('/<int:data_id>', methods=['PUT'])
def put(data_id):
    data = str(request.json['data'])
    with pool.connection() as conn:
        cur = conn.execute(
            'UPDATE "todos" SET "todo" = %s WHERE "id" = %s', (data, data_id)
        )
        if cur.rowcount == 0:
            return {}, 404
        before = conn.execute(
            'SELECT count(*) FROM "todos" WHERE "id" < %s', (data_id,)
        ).fetchone()[0]
    cache.delete(page_key(before // PAGE_SIZE))   # после COMMIT
    return {}, 204
```

### Кеш. DELETE

После удаления всё последующее сдвигается на одну позицию вперёд, поэтому устаревают и страница удалённой записи, и каждая следующая за ней.

```python
@app.route('/<int:data_id>', methods=['DELETE'])
def delete(data_id):
    with pool.connection() as conn:
        before = conn.execute(
            'SELECT count(*) FROM "todos" WHERE "id" < %s', (data_id,)
        ).fetchone()[0]
        cur = conn.execute('DELETE FROM "todos" WHERE "id" = %s', (data_id,))
        if cur.rowcount == 0:
            return {}, 404
    drop_pages(before // PAGE_SIZE)
    return {}, 204
```

## Pandas и базы данных

Функция `read_sql` в pandas выполняет запрос и возвращает `DataFrame`, а `to_sql` записывает `DataFrame` в таблицу. Функция `read_sql` принимает соединение `sqlite3` или объект SQLAlchemy; для PostgreSQL используют `create_engine` с адресом `postgresql+psycopg://...`. Журнал для этого раздела создан заново скриптом `make_lab.py` из главы «Базы данных», без индексов.

```python
"""read_sql и to_sql: агрегация в базе, сводка в pandas, результат обратно в таблицу."""
import sqlite3

import numpy as np
import pandas as pd

con = sqlite3.connect("lab.db")
df = pd.read_sql(
    """SELECT r.run_number, r.energy_mev, AVG(m.value) AS mean_signal, COUNT(*) AS n
       FROM measurements AS m JOIN runs AS r ON r.id = m.run_id
       WHERE m.channel = 'BPM01' GROUP BY r.id""", con)
print(df.head(3))
k, b = np.polyfit(df.energy_mev, df.mean_signal, 1)
print(f"строк в DataFrame: {len(df)}; сигнал = {k:.4f} * E + {b:.4f}")
df.to_sql("run_summary", con, if_exists="replace", index=False)
print(con.execute("SELECT sql FROM sqlite_master WHERE name = 'run_summary'").fetchone()[0])
```

       run_number  energy_mev  mean_signal     n
    0           1         5.0     0.099996  5000
    1           2         5.5     0.110061  5000
    2           3         6.0     0.120023  5000
    строк в DataFrame: 40; сигнал = 0.0200 * E + 0.0000
    CREATE TABLE "run_summary" (
    "run_number" INTEGER,
      "energy_mev" REAL,
      "mean_signal" REAL,
      "n" INTEGER
    )

Фильтрация и агрегация выполнены в базе, и в pandas пришли 40 строк сводки вместо миллиона точек; подгонка прямой методом наименьших квадратов восстановила заложенный в модели наклон 0,0200 на мегаэлектронвольт с нулевым смещением. Таблицу `run_summary` функция `to_sql` создала сама, со столбцами по типам `DataFrame`, но без первичного ключа и ограничений: для постоянных данных схему описывают вручную, а `to_sql` дописывает строки в готовую таблицу. Тяжёлую фильтрацию и агрегацию передают базе (SQL с `WHERE` и `GROUP BY`), а в pandas загружают свёрнутый результат: память и время расходуются на порядки экономнее, чем при чтении всех данных и фильтрации в `DataFrame`. Связка «SQL-запрос → DataFrame → график» даёт простейшее приложение для визуализации данных; построение графиков рассматривается в главах про [обработку](python/numpy-and-pandas.md) и [визуализацию](python/visualization.md) данных.

Формат хранения выбирают по способу доступа. Оценим размеры файлов и время чтения: скрипт `formats.py` выгружает миллион измерений журнала в CSV и Parquet и сравнивает чтение с SQLite, беря медиану трёх запусков; для Parquet нужен пакет pyarrow.

```python
"""Миллион измерений в CSV, SQLite и Parquet: размер файла и время чтения."""
import os
import sqlite3
import statistics
import time

import pandas as pd
import pyarrow

con = sqlite3.connect("lab.db")
ALL = "SELECT run_id, channel, t, value FROM measurements"
ONE = ALL + " WHERE run_id = 7 AND channel = 'BPM01'"
df = pd.read_sql(ALL, con)
df.to_csv("m.csv", index=False)
df.to_parquet("m.parquet", index=False)
db_size = os.path.getsize("lab.db")              # размер до создания индекса
con.execute("CREATE INDEX idx_m_run_channel ON measurements (run_id, channel)")
print(f"pandas {pd.__version__}, pyarrow {pyarrow.__version__}, строк: {len(df)}")


def ms(func):
    times = []
    for _ in range(3):
        start = time.perf_counter()
        func()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def csv_one():
    d = pd.read_csv("m.csv")                     # прочитать всё, затем отфильтровать
    return d[(d.run_id == 7) & (d.channel == "BPM01")]


FILTER = [("run_id", "==", 7), ("channel", "==", "BPM01")]
ROWS = [
    ("CSV", os.path.getsize("m.csv"), lambda: pd.read_csv("m.csv"), csv_one),
    ("SQLite", db_size, lambda: pd.read_sql(ALL, con), lambda: pd.read_sql(ONE, con)),
    ("Parquet", os.path.getsize("m.parquet"), lambda: pd.read_parquet("m.parquet"),
     lambda: pd.read_parquet("m.parquet", filters=FILTER)),
]
print(f"{'формат':8s} {'МиБ':>6s} {'всё, мс':>9s} {'один канал, мс':>15s}")
for name, size, full, one in ROWS:
    print(f"{name:8s} {size / 2**20:6.1f} {ms(full):9.0f} {ms(one):15.1f}")
```

    pandas 3.0.6, pyarrow 25.0.1, строк: 1000000
    формат      МиБ   всё, мс  один канал, мс
    CSV        22.5       119           113.9
    SQLite     33.4       672             3.3
    Parquet     4.5        17            15.2

CSV является форматом обмена: его читает любая программа, но он хранит текст, а не типы, и для выборки одного канала читается целиком. SQLite подходит для журнала, который пополняется по записи и читается выборочно: всю таблицу модуль `sqlite3` отдаёт медленно, поскольку строки проходят через Python по одной, зато 5000 строк одного канала одного захода находятся по индексу за несколько миллисекунд. Parquet хранит таблицу по столбцам со сжатием и статистикой групп строк, поэтому занимает в пять раз меньше CSV и быстро читается целиком; при фильтре он пропускает группы строк, где нужного значения заведомо нет, но здесь весь файл умещается в одну группу, и фильтр почти не ускоряет чтение. Таким образом, Parquet является форматом архива для анализа.

SQL-запросы прямо к файлам Parquet и CSV, без загрузки в базу, выполняет встраиваемая аналитическая СУБД [DuckDB](https://duckdb.org/) (`pip install duckdb`); для запроса к файлу достаточно указать его имя в предложении `FROM`:

```python
import duckdb

rows = duckdb.sql("""
    SELECT run_id, round(avg(value), 4) AS mean_signal, count(*) AS n
    FROM 'm.parquet'
    WHERE channel = 'BPM01'
    GROUP BY run_id
    ORDER BY run_id DESC
    LIMIT 3
""").fetchall()
print(rows)
```

    [(40, 0.49, 5000), (39, 0.48, 5000), (38, 0.47, 5000)]

Строка на отсчёт годится для медленных каналов журнала, но не для осциллограмм и изображений с АЦП на мегагерцах: миллион строк журнала соответствует всего 40 заходам по 50 с при 100 Гц. Такие массивы хранят в файлах HDF5 или Parquet либо массивом в одной строке, а в базе держат метаданные и путь к файлу. Рассмотрим осциллограммы тока цилиндра Фарадея по 20 000 отсчётов при частоте оцифровки 100 МГц, по одной на заход (пакет h5py):

```python
import sqlite3

import h5py
import numpy as np

rng = np.random.default_rng(7)
t = np.arange(20_000) / 100e6                # 20 000 отсчётов АЦП на 100 МГц, с
con = sqlite3.connect("lab.db")
con.execute("PRAGMA foreign_keys = ON")
con.execute("""CREATE TABLE IF NOT EXISTS waveforms (
    run_id  INTEGER NOT NULL REFERENCES runs(id),
    channel TEXT NOT NULL,
    file    TEXT NOT NULL,                   -- файл HDF5 с осциллограммой
    dataset TEXT NOT NULL,                   -- путь к массиву внутри файла
    rate_hz REAL NOT NULL)""")
with h5py.File("waveforms.h5", "w") as f, con:
    for run_id, energy in con.execute("SELECT id, energy_mev FROM runs").fetchall():
        name = f"run{run_id:03d}/fcup"         # ток с цилиндра Фарадея, мА
        pulse = 0.4 * energy * np.exp(-((t - 100e-6) / 20e-6) ** 2)
        pulse += rng.normal(0, 0.05, t.size)
        f.create_dataset(name, data=pulse.astype(np.float32), compression="gzip")
        con.execute("INSERT INTO waveforms VALUES (?, 'FCUP', 'waveforms.h5', ?, 100e6)",
                    (run_id, name))

# поиск — по метаданным в базе, массив — из файла
file, dataset = con.execute(
    "SELECT w.file, w.dataset FROM waveforms AS w JOIN runs AS r ON r.id = w.run_id "
    "WHERE r.run_number = 31").fetchone()
with h5py.File(file) as f:
    pulse = f[dataset][:]
print(dataset, pulse.shape, pulse.dtype, f"максимум {pulse.max():.2f} мА")
```

    run031/fcup (20000,) float32 максимум 8.11 мА

Поиск по-прежнему выполняет SQL — здесь по номеру захода, — а сам массив читается из файла HDF5 одним обращением, со сжатием и без разбиения на строки.

## С чего начать в своей лаборатории

Рецепт перехода от тысячи CSV к одной базе включает следующие шаги:

1. Завести один файл `lab.db` и описать схему по образцу журнала из главы [«Базы данных»](./bd.md). Минимально необходимы таблицы вида `experiments`, `runs`, `measurements` с первичными и внешними ключами и `NOT NULL` на важных полях; время записывается в UTC. Схема служит документацией, проверяющей сама себя.
2. Импортировать накопленные CSV одним скриптом:

    ```python
    from pathlib import Path
    import sqlite3

    import pandas as pd

    con = sqlite3.connect("lab.db")

    frames = []
    for csv_path in sorted(Path("data").rglob("*.csv")):   # порядок обхода задан явно
        df = pd.read_csv(csv_path)
        df["source_file"] = str(csv_path)                  # происхождение данных
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)             # объединение всех столбцов
    raw.to_sql("measurements_raw", con, if_exists="replace", index=False)
    print(len(raw), "строк:", ", ".join(raw.columns))
    ```

    Файлы обходятся в отсортированном порядке, собираются в один `DataFrame` и записываются одним вызовом `to_sql`. Дописывать каждый файл отдельно (`if_exists="append"`) нельзя: если в каком-то файле есть столбец, которого не было в первом, загрузка обрывается на середине ошибкой `table measurements_raw has no column named ...`, а какой файл окажется первым, зависит от порядка обхода. На трёх пробных файлах, в последнем из которых есть лишний столбец `temperature`, скрипт печатает:

       7 строк: channel, t, value, source_file, temperature

    В строках из файлов без этого столбца `temperature` равна `NULL`. Далее «сырую» таблицу можно разложить по нормализованной схеме SQL-запросами.
3. Новые данные записывать сразу в базу, применяя в скрипте сбора `executemany` группами точек и `commit` раз в несколько секунд, а не файл на каждый заход.
4. Включить `PRAGMA journal_mode=WAL`: в этом режиме SQLite позволяет читать базу (строить графики) параллельно с записью. Режим сохраняется в самой базе, но работает, только когда все процессы на одной машине: на сетевом диске (NFS, SMB) WAL неприменим. Пишущая транзакция по-прежнему одна.
5. Просматривать данные удобно в DB Browser for SQLite, а резервную копию делает `Connection.backup()` из Python или команда `VACUUM INTO 'backup.db'`; простое копирование файла допустимо, только когда к базе никто не подключён, а в режиме WAL — вместе с файлом `-wal`. Восстановление из копии проверяют заранее.

Когда данными начнёт пользоваться вся группа с нескольких машин, схема переносится в PostgreSQL; SQL и почти весь код при этом остаются прежними, меняются знак параметра, драйвер и тип времени — `timestamptz` вместо строки.

## Полезные ссылки

- [Модуль sqlite3 в стандартной библиотеке Python](https://docs.python.org/3/library/sqlite3.html)
- [Документация psycopg 3](https://www.psycopg.org/psycopg3/docs/)
- [Документация SQLAlchemy 2.1](https://docs.sqlalchemy.org/en/21/)
- [Резервное копирование и восстановление в документации PostgreSQL 17](https://www.postgresql.org/docs/17/backup.html)
- [Рогов Е. В. PostgreSQL 18 изнутри](https://postgrespro.ru/education/books/internals)
- [Документация Valkey](https://valkey.io/docs/)
- [Документация DuckDB](https://duckdb.org/docs/)


> **Задание.** Собрать и развернуть всё вместе, приложение, контейнеры, сеть и базу: [«Деплой стартапа»](../practicum/kitty-startup-task.md).
