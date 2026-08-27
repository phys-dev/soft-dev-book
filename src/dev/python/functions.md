# Функции в Python

Функция — первый инструмент борьбы со сложностью: она позволяет спрятать кусок логики за именем и дальше о нём не думать. Синтаксис `def` ты наверняка уже знаешь, поэтому здесь мы пойдём глубже.

Разберём, как Python обходится с аргументами (а он умеет заметно больше, чем «передать по порядку»), где живут переменные и по какому правилу интерпретатор их ищет, чем распаковка отличается от обычного присваивания и какие ловушки подстерегают в значениях по умолчанию.

## Синтаксис объявления функций

### Базовый синтаксис

Имя функции в Python может содержать буквы, цифры и символ подчеркивания `_`, но не может начинаться с цифры:

```python
def foo():
    return 42

foo()  # возвращает 42
```

**Важно:** оператор `return` не обязателен. Если его нет, функция возвращает `None`:

```python
def foo():
    42

print(foo())  # выводит None
```

### Документирование функций

Для документирования используются строковые литералы (docstring):

```python
def foo():
    """I return 42."""
    return 42
```

Документация доступна через атрибут `__doc__` или функцию `help()`:

```python
print(foo.__doc__)  # 'I return 42.'
help(foo)           # показывает документацию
```

## Работа с аргументами

### Позиционные и именованные аргументы

```python
def min(x, y):
    return x if x < y else y

min(-5, 12)        # -5
min(x=-5, y=12)    # -5
min(y=12, x=-5)    # -5 (порядок не важен)
```

### Упаковка позиционных аргументов

Для работы с произвольным количеством аргументов используется `*args`:

```python
def min(*args):
    res = float("inf")
    for arg in args:
        if arg < res:
            res = arg
    return res

min(-5, 12, 13)  # -5
min()            # inf
```

**Обязательный первый аргумент:**

```python
def min(first, *args):
    res = first
    for arg in args:
        if arg < res:
            res = arg
    return res

min()  # TypeError: missing required argument 'first'
```

### Распаковка аргументов

Синтаксис распаковки работает с любыми итерируемыми объектами:

```python
xs = {-5, 12, 13}
min(*xs)           # -5
min(*[-5, 12, 13]) # -5
min(*(-5, 12, 13)) # -5
```

### Ключевые аргументы и значения по умолчанию

```python
def bounded_min(first, *args, lo=float("-inf"), hi=float("inf")):
    res = hi
    for arg in (first,) + args:
        if arg < res and lo < arg < hi:
            res = arg
    return max(res, lo)

bounded_min(-5, 12, 13, lo=0, hi=255)  # 12
```

### Опасность изменяемых значений по умолчанию

**Неправильно:**

```python
def unique(iterable, seen=set()):
    acc = []
    for item in iterable:
        if item not in seen:
            seen.add(item)
            acc.append(item)
    return acc

xs = [1, 1, 2, 3]
unique(xs)  # [1, 2, 3]
unique(xs)  # [] 😱
```

**Правильно:**

```python
def unique(iterable, seen=None):
    seen = set(seen or [])  # None - falsy значение
    acc = []
    for item in iterable:
        if item not in seen:
            seen.add(item)
            acc.append(item)
    return acc

xs = [1, 1, 2, 3]
unique(xs)  # [1, 2, 3]
unique(xs)  # [1, 2, 3] ✅
```

### Только ключевые аргументы

Можно требовать, чтобы некоторые аргументы передавались только по имени:

```python
def flatten(xs, *, depth=None):
    pass

flatten([1, [2], 3], depth=1)  # ✅
flatten([1, [2], 3], 1)        # TypeError
```

### Упаковка ключевых аргументов

```python
def runner(cmd, **kwargs):
    if kwargs.get("verbose", True):
        print("Logging enabled")

runner("mysqld", limit=42)                    # ✅
runner("mysqld", **{"verbose": False})        # ✅
options = {"verbose": False}
runner("mysqld", **options)                   # ✅
```

## Распаковка и присваивание

### Базовая распаковка

```python
x, y, z = [1, 2, 3]           # ✅
x, y, z = {1, 2, 3}           # ✅ (но порядок не гарантирован!)
x, y, z = "xyz"               # ✅

# Распаковка вложенных структур
rectangle = (0, 0), (4, 4)
(x1, y1), (x2, y2) = rectangle
```

### Расширенная распаковка (Python 3.0+)

```python
first, *rest = range(1, 5)           # first=1, rest=[2, 3, 4]
first, *rest, last = range(1, 5)     # first=1, rest=[2, 3], last=4

# Можно использовать в любом месте
*_, (first, *rest) = [range(1, 5)] * 5
```

**Особенность:** при недостатке значений возникает ошибка:

```python
first, *rest, last = [42]  # ValueError
```

### Распаковка в цикле for

```python
for a, *b in [range(4), range(2)]:
    print(b)
# Вывод:
# [1, 2, 3]
# [1]
```

## Области видимости (Scopes)

### Функции внутри функций

Функции в Python — объекты первого класса:

```python
def wrapper():
    def identity(x):
        return x
    return identity

f = wrapper()
f(42)  # 42
```

### Правило LEGB

Поиск имен осуществляется в четырех областях видимости:

- **L**ocal (локальная)
- **E**nclosing (объемлющая)
- **G**lobal (глобальная) 
- **B**uilt-in (встроенная)

```python
min = 42  # global

def f(*args):
    min = 2  # enclosing
    def g():
        min = 4  # local
        print(min)
```

### Замыкания и позднее связывание

Замыкания используют переменные из внешних областей видимости во время выполнения:

```python
def f():
    print(i)

for i in range(4):
    f()
# Вывод:
# 0
# 1
# 2
# 3
```

### Присваивание и области видимости

По умолчанию присваивание создает локальную переменную:

```python
min = 42

def f():
    min += 1  # UnboundLocalError!
    return min
```

### Оператор global

Позволяет изменять глобальные переменные:

```python
min = 42

def f():
    global min
    min += 1
    return min

f()  # 43
f()  # 44
```

### Оператор nonlocal (Python 3+)

Позволяет изменять переменные из объемлющей области видимости:

```python
def cell(value=None):
    def get():
        return value
    def set(update):
        nonlocal value
        value = update
    return get, set

get, set = cell()
set(42)
get()  # 42
```

## Функциональное программирование

### Анонимные функции (lambda)

```python
lambda arguments: expression

# Эквивалентно:
def <lambda>(arguments):
    return expression
```

Примеры:

```python
lambda x: x ** 2
lambda foo, *args, bar=None, **kwargs: 42
```

### Функции map, filter, zip

**map** — применяет функцию к каждому элементу:

```python
list(map(lambda x: x % 7, [1, 9, 16, -1, 2, 5]))  # [1, 2, 2, 6, 2, 5]
```

**filter** — оставляет элементы, удовлетворяющие условию:

```python
list(filter(lambda x: x % 2 != 0, range(10)))  # [1, 3, 5, 7, 9]

# С None - оставляет только truthy значения
xs = [0, None, [], {}, set(), "", 42]
list(filter(None, xs))  # [42]
```

**zip** — объединяет элементы нескольких последовательностей:

```python
list(zip("abc", range(3), [42j, 42j, 42j]))
# [('a', 0, 42j), ('b', 1, 42j), ('c', 2, 42j)]
```

### Генераторы коллекций

**Генераторы списков:**

```python
[x ** 2 for x in range(10) if x % 2 == 1]  # [1, 9, 25, 49, 81]

# Эквивалент с map/filter:
list(map(lambda x: x ** 2, filter(lambda x: x % 2 == 1, range(10))))

# Вложенные генераторы:
nested = [range(5), range(8, 10)]
[x for xs in nested for x in xs]  # [0, 1, 2, 3, 4, 8, 9]
```

**Генераторы множеств и словарей:**

```python
{x % 7 for x in [1, 9, 16, -1, 2, 5]}  # {1, 2, 5, 6}

date = {'year': 2014, "month": "September", "day": ""}
{k: v for k, v in date.items() if v}  # {'year': 2014, 'month': 'September'}

{x: x ** 2 for x in range(4)}  # {0: 0, 1: 1, 2: 4, 3: 9}
```

## PEP 8: стиль кода

### Базовые рекомендации

- 4 пробела для отступов
- Максимум 79 символов в строке кода
- `lower_case_with_underscores` для переменных и функций
- `UPPER_CASE_WITH_UNDERSCORES` для констант

### Выражения и операторы

**Правильно:**
```python
exp = -1.05
value = (item_value / item_count) * offset / exp

if bar:
    x += 1

if method == 'md5':
    pass

if key not in d:
    pass
```

**Неправильно:**
```python
if bar: x += 1

if 'md5' == method:
    pass

if not key in d:
    pass
```

### Функции

```python
def something_useful(arg, **options):
    """One-line summary.

    Optional longer description.
    """
    pass
```

## Резюме

- Функции могут принимать произвольное количество позиционных (`*args`) и ключевых (`**kwargs`) аргументов
- Синтаксис распаковки работает в вызовах функций, присваивании и циклах
- Поиск имен осуществляется по правилу LEGB
- Присваивание создает локальные переменные (можно изменить через `global`/`nonlocal`)
- Python поддерживает элементы ФП: lambda, map, filter, zip, генераторы коллекций
- PEP 8 содержит стилистические рекомендации для написания читаемого кода