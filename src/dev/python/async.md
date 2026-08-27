# Асинхронное API

## Введение в асинхронное программирование

Асинхронное программирование стало неотъемлемой частью современной Python-разработки и продолжает набирать популярность среди веб-разработчиков.

## Основные темы

### Итераторы, генераторы и корутины

#### Итераторы

Итераторы - фундаментальная концепция Python, которую разработчики используют ежедневно, часто не задумываясь об их работе. Любая коллекция в Python (списки, словари, множества, строки, файлы) является итерабельной.

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

#### Генераторы

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

#### Корутины

Корутины - основные строительные блоки асинхронного программирования, появившиеся как решение проблемы GIL (Global Interpreter Lock).

**Пример корутины для финансовых расчетов:**

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

### Асинхронность в Python и asyncio

#### Типы задач

- **CPU bound-задачи** - интенсивное использование процессора (математические модели, нейросети, рендеринг)
- **I/O bound-задачи** - основная работа с вводом/выводом (файловая система, сеть)
- **Memory bound-задачи** - интенсивная работа с оперативной памятью

#### Проблема блокирующих операций

```python
import requests

def do_some_logic(data):
    pass

def save_to_database(data):
    pass

# Блокирующий код
data = requests.get('https://data.aggregator.com/films')
processed_data = do_some_logic(data)
save_to_database(data)
```

#### Event Loop - сердце асинхронных программ

**Базовая реализация планировщика:**

```python
import logging
from typing import Generator
from queue import Queue

class Scheduler:
    def __init__(self):
        self.ready = Queue()
        self.task_map = {}
    
    def add_task(self, coroutine: Generator) -> int:
        new_task = Task(coroutine)
        self.task_map[new_task.tid] = new_task
        self.schedule(new_task)
        return new_task.tid
    
    def exit(self, task: Task):
        del self.task_map[task.tid]
    
    def schedule(self, task: Task):
        self.ready.put(task)
    
    def _run_once(self):
        task = self.ready.get()
        try:
            result = task.run()
        except StopIteration:
            self.exit(task)
            return
        self.schedule(task)
    
    def event_loop(self):
        while self.task_map:
            self._run_once()
```

**Реализация задачи (Task):**

```python
import types
from typing import Generator, Union

class Task:
    task_id = 0
    
    def __init__(self, target: Generator):
        Task.task_id += 1
        self.tid = Task.task_id
        self.target = target
        self.sendval = None
        self.stack = []
    
    def run(self):
        while True:
            try:
                result = self.target.send(self.sendval)
                
                if isinstance(result, types.GeneratorType):
                    self.stack.append(self.target)
                    self.sendval = None
                    self.target = result
                else:
                    if not self.stack:
                        return
                    self.sendval = result
                    self.target = self.stack.pop()
            
            except StopIteration:
                if not self.stack:
                    raise
                self.sendval = None
                self.target = self.stack.pop()
```

#### Asyncio

С версии Python 3.5 появился синтаксис async/await для нативных корутин.

**Простая программа с asyncio:**

```python
import random
import asyncio

async def func():
    r = random.random()
    await asyncio.sleep(r)
    return r

async def value():
    result = await func()
    print(result)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(value())
    loop.close()
```

**Основные функции asyncio:**

- `gather` - одновременное выполнение корутин
- `sleep` - приостановка выполнения
- `wait` / `wait_for` - ожидание выполнения корутин

**Основные функции event_loop:**

- `get_event_loop` - получение объекта цикла событий
- `run_until_complete` / `run` - запуск асинхронных функций
- `shutdown_asyncgens` - корректное завершение
- `call_soon` - планирование выполнения

### Асинхронные фреймворки

#### Twisted

Один из старейших асинхронных фреймворков с собственной реализацией event-loop.

**Основные концепции:**

1. **Protocol** - описание получения и отправки данных
2. **Factory** - управление созданием объектов протокола
3. **Reactor** - собственная реализация event-loop
4. **Deferred-объекты** - цепочки обратных вызовов

**Пример Deferred-объекта:**

```python
from twisted.internet import defer

def toint(data):
    return int(data)

def increment_number(data):
    return data + 1

def print_result(data):
    print(data)

def handleFailure(f):
    print("OOPS!")

def get_deferred():
    d = defer.Deferred()
    return d.addCallbacks(toint, handleFailure)\
           .addCallbacks(increment_number, handleFailure)\
           .addCallback(print_result)
```

#### Aiohttp

Асинхронные HTTP-клиент и сервер, построенные поверх asyncio.

**Пример приложения:**

```python
import aiohttp
from aiohttp import web

async def get_phrase():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://fish-text.ru/get', 
                             params={'type': 'title'}) as response:
            result = await response.json(content_type='text/html; charset=utf-8')
            return result.get('text')

async def index_handler(request):
    return web.Response(text=await get_phrase())

async def response_signal(request, response):
    response.text = response.text.upper()
    return response

async def make_app():
    app = web.Application()
    app.on_response_prepare.append(response_signal)
    app.add_routes([web.get('/', index_handler)])
    return app

web.run_app(make_app())
```

#### FastAPI

Современный фреймворк для быстрой разработки API, построенный на Starlette и Pydantic.

**Простой пример API:**

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI(title="Простые математические операции")

class Add(BaseModel):
    first_number: int = Field(title='Первое слагаемое')
    second_number: Optional[int] = Field(title='Второе слагаемое')

class Result(BaseModel):
    result: int = Field(title='Результат')

@app.post("/add", response_model=Result)
async def create_item(item: Add):
    return {
        'result': item.first_number + (item.second_number or 1)
    }
```

## Заключение

Ты познакомились с основами асинхронного программирования в Python, изучили ключевые концепции итераторов, генераторов и корутин, освоили работу с asyncio и популярными асинхронными фреймворками.

## Полезные ссылки

1. https://dbader.org/blog/python-iterators
2. https://www.techbeamers.com/python-iterator/
3. https://realpython.com/introduction-to-python-generators/
4. https://www.python.org/dev/peps/pep-0255
5. https://ru.wikipedia.org/wiki/Ленивые_вычисления
6. https://medium.com/@chandansingh_99754/python-generators-and-coroutines-d54ed9c343ae
7. https://www.youtube.com/watch?v=AXkOli6BsBY
8. https://realpython.com/python-sockets/#reference
9. https://snarky.ca/how-the-heck-does-async-await-work-in-python-3-5/