# Итераторы, генераторы и корутины

Эта глава — о трёх родственных механизмах языка, которые связывает одна идея: **не вычислять всё сразу**. Итератор выдаёт элементы по одному, генератор умеет приостанавливать выполнение функции и возвращаться в неё, а корутина вдобавок умеет принимать значения снаружи.

Механизмы полезны сами по себе — они позволяют обрабатывать файлы, которые не помещаются в память, и описывать бесконечные последовательности. Но главное, ради чего мы их разбираем: на генераторах построена вся асинхронность Python. Разобравшись здесь, ты без труда поймёшь `asyncio` в главе про [асинхронность](../../perf/async.md).


## Итераторы

Итераторы — фундаментальная концепция Python, которую разработчики используют ежедневно, часто не задумываясь об их работе. Любая коллекция в Python (списки, словари, множества, строки, файлы) является итерабельной.

**Реализация аналога функции range():**

```python
class Range:
    def __init__(self, stop_value: int):
        self.current = -1
        self.stop_value = stop_value - 1
    
    def __iter__(self):
        return RangeIterator(self)

class RangeIterator:
    def __init__(self, container):
        self.container = container
    
    def __next__(self):
        if self.container.current < self.container.stop_value:
            self.container.current += 1
            return self.container.current
        raise StopIteration
```

**Упрощенная версия:**

```python
class Range2:
    def __init__(self, stop_value: int):
        self.current = -1
        self.stop_value = stop_value - 1
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.current < self.stop_value:
            self.current += 1
            return self.current
        raise StopIteration
```

**Как работает цикл for под капотом:**

```python
iterable = Range2(5)
iterator = iter(iterable)

while True:
    try:
        value = next(iterator)
        print(value)
    except StopIteration:
        break
```

## Генераторы

Генераторы работают на принципе запоминания контекста выполнения функции с помощью ключевого слова `yield`.

**Простой пример генератора:**

```python
def simple_generator():
    yield 1
    yield 2
    return 3

gen = simple_generator()
print(next(gen))  # 1
print(next(gen))  # 2
print(next(gen))  # StopIteration: 3
```

**Генераторные выражения:**

```python
gen_exp = (x for x in range(100000))
print(gen_exp)  # <generator object <genexpr> at 0x...>
```

**Синтаксический сахар yield from:**

```python
numbers = [1, 2, 3]

# Стандартный подход
def func():
    for item in numbers:
        yield item

# Упрощенный подход
def func():
    yield from numbers
```

## Корутины

Корутины — основные строительные блоки асинхронного программирования, появившиеся как решение проблемы GIL (Global Interpreter Lock).

**Пример корутины для финансовых расчётов:**

```python
import math

def cash_return_coro(percent: float, years: int) -> float:
    value = math.pow(1 + percent / 100, years)
    while True:
        try:
            deposit = (yield)
            yield round(deposit * value, 2)
        except GeneratorExit:
            print('Выход из корутины')
            raise

# Использование
coro = cash_return_coro(5, 5)
next(coro)
values = [1000, 2000, 5000, 10000, 100000]
for item in values:
    print(coro.send(item))
    next(coro)
coro.close()
```

## Что дальше

Мы разобрали механику: итератор отдаёт элементы по одному, генератор приостанавливает функцию на `yield` и продолжает с того же места, корутина умеет ещё и принимать значения через `send()`.

Именно на этом фундаменте построена асинхронность в Python. Цикл событий — это, по сути, планировщик, который переключается между приостановленными генераторами, отдавая процессорное время тому, кто готов работать, пока остальные ждут ответа от сети или диска. Как это устроено внутри и как этим пользоваться через `asyncio`, разбирается в главе про асинхронность в разделе «Ускоряем код».
