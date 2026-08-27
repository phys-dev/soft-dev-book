# Декораторы и модуль `functools`

Декораторы в Python — это мощный инструмент для модификации поведения функций и методов, позволяющий писать чистый, повторно используемый и легко читаемый код. В этой главе мы глубоко погрузимся в мир декораторов, изучим их синтаксис, создание, применение, а также познакомимся с полезными инструментами из модуля `functools`.

## Синтаксис декораторов

Декоратор — это функция, которая принимает другую функцию и возвращает новую функцию (или любой другой объект). Синтаксис декоратора — это «синтаксический сахар», который делает код более понятным.

```python
@decorator
def foo(x):
    return 42
```

Эквивалентно:

```python
def foo(x):
    return 42

foo = decorator(foo)
```

Таким образом, после применения декоратора имя `foo` будет ссылаться на результат вызова `decorator(foo)`.

## «Теория» декораторов: создание простого декоратора

Рассмотрим пример декоратора `trace`, который логирует вызовы функции:

```python
def trace(func):
    def inner(*args, **kwargs):
        print(func.__name__, args, kwargs)
        return func(*args, **kwargs)
    return inner
```

Применим его:

```python
@trace
def identity(x):
    "I do nothing useful."
    return x

identity(42)  # Вывод: identity (42,) {} → 42
```

### Проблема атрибутов функции

После применения декоратора исходные атрибуты функции (такие как `__name__`, `__doc__`) теряются:

```python
identity.__name__  # 'inner'
help(identity)     # Справка о inner, а не identity
```

### Решение: `functools.wraps`

Модуль `functools` предоставляет декоратор `wraps`, который копирует метаданные исходной функции в декорированную:

```python
import functools

def trace(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        print(func.__name__, args, kwargs)
        return func(*args, **kwargs)
    return inner
```

Теперь `identity.__name__` и `help(identity)` работают корректно.

## Декораторы с аргументами

Иногда нужно параметризовать декоратор. Например, указать файл для вывода в `trace`:

```python
def trace(handle):
    def decorator(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            print(func.__name__, args, kwargs, file=handle)
            return func(*args, **kwargs)
        return inner
    return decorator

@trace(sys.stderr)
def identity(x):
    return x
```

Эквивалентно:

```python
decorator = trace(sys.stderr)
identity = decorator(identity)
```

## Декораторы с опциональными аргументами

Чтобы декоратор можно было использовать как с аргументами, так и без них, применяют следующий паттерн:

```python
def trace(func=None, *, handle=sys.stdout):
    if func is None:
        return lambda func: trace(func, handle=handle)

    @functools.wraps(func)
    def inner(*args, **kwargs):
        print(func.__name__, args, kwargs, file=handle)
        return func(*args, **kwargs)
    return inner
```

Использование:

```python
@trace
def foo(): ...

@trace(handle=sys.stderr)
def bar(): ...
```

**Зачем только ключевые аргументы?** Это предотвращает неоднозначность при вызове и делает код чище.

## Практика: полезные декораторы

### @timethis — замер времени выполнения

```python
import time

def timethis(func=None, *, n_iter=100):
    if func is None:
        return lambda func: timethis(func, n_iter=n_iter)

    @functools.wraps(func)
    def inner(*args, **kwargs):
        print(func.__name__, end=" ... ")
        acc = float("inf")
        for i in range(n_iter):
            tick = time.perf_counter()
            result = func(*args, **kwargs)
            acc = min(acc, time.perf_counter() - tick)
        print(acc)
        return result
    return inner
```

### @once — выполнить не более одного раза

```python
def once(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        if not inner.called:
            inner.result = func(*args, **kwargs)
            inner.called = True
        return inner.result
    inner.called = False
    return inner
```

### @memoized — мемоизация

```python
def memoized(func):
    cache = {}
    @functools.wraps(func)
    def inner(*args, **kwargs):
        key = args + tuple(sorted(kwargs.items()))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    return inner
```

**Проблема:** Словари нехэшируемы. Для универсального решения можно сериализовать аргументы в строку (например, через `pickle`).

### @deprecated — пометить функцию как устаревшую

```python
import warnings

def deprecated(func):
    code = func.__code__
    warnings.warn_explicit(
        f"{func.__name__} is deprecated.",
        category=DeprecationWarning,
        filename=code.co_filename,
        lineno=code.co_firstlineno + 1
    )
    return func
```

## Контрактное программирование с декораторами

Реализуем простые контракты `@pre` и `@post`:

```python
def pre(cond, message):
    def decorator(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            assert cond(*args, **kwargs), message
            return func(*args, **kwargs)
        return inner
    return decorator

def post(cond, message):
    def decorator(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            result = func(*args, **kwargs)
            assert cond(result), message
            return result
        return inner
    return decorator
```

Использование:

```python
@pre(lambda x: x >= 0, "negative argument")
@post(lambda r: not math.isnan(r), "result is NaN")
def log_positive(x):
    return math.log(x)
```

## Цепочки декораторов

Порядок применения декораторов имеет значение:

```python
@deco1
@deco2
def foo(): ...
```

Эквивалентно:

```python
foo = deco1(deco2(foo))
```

## Модуль `functools`

### `lru_cache` — мемоизация с ограничением

```python
@functools.lru_cache(maxsize=128)
def expensive_func(x):
    return x * x
```

- `maxsize=None` — неограниченный кеш (опасно при большом количестве вызовов!).
- `cache_info()` — статистика использования кеша.

### `partial` — частичное применение

```python
f = functools.partial(sorted, key=lambda x: x[1])
f([('a', 4), ('b', 2)])  # [('b', 2), ('a', 4)]
```

### `singledispatch` — обобщённые функции

Позволяет определять разные реализации функции для разных типов:

```python
@functools.singledispatch
def pack(obj):
    raise TypeError(f"Unsupported type: {type(obj)}")

@pack.register(int)
def _(obj):
    return b"I" + hex(obj).encode("ascii")

@pack.register(list)
def _(obj):
    return b"L" + b",".join(map(pack, obj))
```

### `reduce` — свёртка последовательности

```python
functools.reduce(lambda acc, x: acc * x, [1, 2, 3, 4])  # 24
```

Хотя `reduce` популярен в функциональных языках, в Python его используют редко, предпочитая явные циклы для ясности.

## Заключение

Декораторы — это не просто «синтаксический сахар», а фундаментальный инструмент метапрограммирования в Python. Они позволяют:

- Модифицировать поведение функций без изменения их кода.
- Реализовывать аспектно-ориентированное программирование.
- Создавать выразительные и легко читаемые API.

Модуль `functools` предоставляет готовые решения для многих задач, связанных с функциональным программированием и декорированием.

**Дополнительные материалы:**
- [Python Decorator Library](https://wiki.python.org/moin/PythonDecoratorLibrary)
- [PEP 443 – Single-dispatch generic functions](https://peps.python.org/pep-0443/)
- [PEP 318 – Decorators for Functions and Methods](https://peps.python.org/pep-0318/)