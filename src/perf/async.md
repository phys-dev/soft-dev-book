# Асинхронность

Сколько бы потоков ни было запущено, GIL пропускает через интерпретатор только один из них, а запускать больше одновременно вычисляющих процессов, чем ядер, не имеет смысла.

Существует класс задач, в которых процессор не является узким местом. Программа, скачивающая тысячу файлов или опрашивающая сотню приборов по сети, почти всё время **ожидает**. Запрос, отправленный по сети, ушёл, ответ не пришёл, работы нет. Выделять под каждое такое ожидание отдельный поток расточительно, поскольку поток, отданный под простой, требует памяти и переключений контекста, а полезной работы не выполняет.

Асинхронность поручает одному потоку тысячу ожиданий сразу: пока один запрос ожидает ответа, выполняется другой. Механику обеспечивают генераторы и корутины, разобранные в главе [«Итераторы, генераторы и корутины»](../dev/python/async.md): планировщику необходима функция, способная приостановиться и продолжить с того же места.

> **Слайды к главе.** Основы асинхронности изложены также в пятой части лекции «Итераторы, генераторы и корутины» (цикл событий на генераторах, async и await, задачи и тайм-ауты, асинхронная итерация) с демонстрациями в интерактивной оболочке; слайды лекции доступны [на сайте книги](https://phys-dev.github.io/soft-dev-book/slides/lecture-07.html#/sec-aio) и [в PDF](https://github.com/phys-dev/soft-dev-book/releases/latest/download/soft-dev-book-lecture-07.pdf).

<iframe src="../slides/lecture-07.html#/sec-aio" title="Слайды лекции «Итераторы, генераторы и корутины»: async и await" loading="lazy" allowfullscreen style="width:100%; aspect-ratio:16/10; border:0; border-radius:6px"></iframe>

## Работа с разными типами задач

Долгое время природу нагрузки внутри программы можно было не учитывать, поскольку приложения писались большими и монолитными, а проблемы с производительностью решались грубой силой: добавленными потоками, дополнительными процессами или ещё одной машиной, установленной в стойку.

Сегодня одних процессов и потоков недостаточно, и выбор инструмента начинается с вопроса, чем занята программа. Задачи разделяют на три типа:

- **CPU bound-задачи.** Задачи, требующие интенсивного использования процессора, среди которых сложные математические модели, обучение нейронных сетей, рендеринг графики и вычисление хешей.

- **I/O bound-задачи (non-RAM I/O bound).** Задачи, в которых основная часть работы приходится на ввод/вывод информации *I/O* или *input/output*, относящиеся в основном к работе с файловой системой и с сетью. 

- **Memory bound-задачи (RAM I/O bound).** Задачи с интенсивной работой с оперативной памятью, возникающие, как правило, в сложных математических моделях. Из-за медленной работы с оперативной памятью всё больше моделей обрабатывается на видеокартах, устроенных иначе. Другим примером служит обработка огромного объёма данных в *Map-Reduce*-системах, например таких как *Spark*, выполняющаяся тем быстрее, чем больше оперативной памяти.

Подробнее об этом рассказано в англоязычных статьях [о значении терминов CPU bound и I/O bound](https://stackoverflow.com/questions/868568/what-do-the-terms-cpu-bound-and-i-o-bound-mean) и [о производительности](https://link.springer.com/chapter/10.1007/978-1-4842-4932-1_15).

Из-за массового перехода на микросервисы количество сетевого взаимодействия между системами многократно возросло, а вместе с ним и нагрузка, приходящаяся на базы данных. Проблемы работы с сетью или с доступом к БД относятся к I/O bound-задачам, сводящимся к ожиданию ответа на запрос, отправленный во внешнюю систему. Такой класс задач в монолитных системах решался пулом потоков, [thread pool](https://en.wikipedia.org/wiki/Thread_pool), которого с ростом сетевой нагрузки между множеством сервисов стало недостаточно.

Классическим ответом на I/O bound-нагрузку является добавление ресурсов, однако приобретать серверы вместо того, чтобы разбираться с кодом, способны лишь компании с большими бюджетами. В лаборатории этот путь закрыт, и остаётся писать код, рассчитанный на такую нагрузку.

Рассмотрим приложение, обращающееся к некоторому сайту-агрегатору за данными по фильмам и сохраняющее полученное в БД (ссылка на сайт вымышленная):


```python
import requests

def do_some_logic(data):
    pass
  
def save_to_database(data):
    pass

data = requests.get('https://data.aggregator.com/films')
processed_data = do_some_logic(data)
save_to_database(processed_data)
```

Код линейный, и пока запрос один, проблем нет, однако как только приложению приходится обслуживать многих клиентов одновременно, время ответа возрастает. Бо́льшую часть времени интерпретатор не выполняет ничего полезного, а ожидает запроса от клиента, ожидает ответа от внешнего сайта, ожидает записи, подтверждённой базой. А клиенты в это время ожидают его.

Схема выполнения программы:

![1_1_AsyncAPI_1_1629286149.png](1_1_AsyncAPI_1_1629286149.png)

Тип задачи в каждой ячейке:

![1.1_3_AsyncAPI_1_1629286157.png](1.1_3_AsyncAPI_1_1629286157.png)

Интуитивно представляется, что время распределено между ячейками примерно поровну, однако в действительности картина иная:

![1_2_AsyncAPI_2_1629286153.png](1_2_AsyncAPI_2_1629286153.png)

Бо́льшую часть времени программа ожидает ввода/вывода, а полезная работа теряется на этом фоне.
Код можно распараллелить на процессы и потоки. Это поможет, но ненадолго: расходы ресурсов сервера возрастут, а число процессов и потоков ограничено, поскольку закончится либо оперативная память под потоки, либо ядра под процессы. Добавляется `GIL`, пропускающий через интерпретатор только один поток за раз: массовый параллелизм на потоках он делает бессмысленным и добавляет собственные накладные расходы, пусть и небольшие.

Выполнение программы с потоками:

![S1.1_4_AsyncAPI_1_1629286161.png](S1.1_4_AsyncAPI_1_1629286161.png)

На I/O bound-задачах два потока работают почти вдвое лучше. Однако два потока, обращающиеся к одним и тем же данным, порождают проблему [«состояния гонок»](https://ru.wikipedia.org/wiki/Состояние_гонки), а многопоточный код требует от разработчика большей внимательности, чем линейный. Кроме того, создать неограниченное число потоков невозможно: памяти под каждый стек они потребляют несравнимо больше, чем корутины.

Интерпретатор по-прежнему бо́льшую часть времени ничего не выполняет, а лишь запрашивает у операционной системы, завершилась ли операция ввода-вывода, запущенная минуту назад. Процессы и потоки этого не меняют. Простаивать будет каждый из них, зато добавятся накладные расходы на переключение контекста и на память, выделенную под стеки, из-за чего положение может даже ухудшиться.


Решение состоит не в увеличении числа исполнителей, а в том, чтобы один исполнитель не простаивал. Эту задачу решает асинхронный код.

## Event-loop

Цикл событий является ядром асинхронных программ в Python. Разберём простую реализацию, предложенную Дэвидом Бизли (David Beazley) [в 2009 году](https://web.archive.org/web/20250108084634/http://www.dabeaz.com/coroutines/Coroutines.pdf): в ней отсутствуют конструкции, которыми с тех пор дополнились промышленные реализации, и устройство просматривается полностью. [Код Бизли](https://web.archive.org/web/20240119054015/http://www.dabeaz.com/coroutines/pyos8.py) приведён к современной версии Python.

Архитектура цикла событий:

![1_Event_Loop_1629282397.png](1_Event_Loop_1629282397.png)

Рассмотрим блоки:

- **Планировщик (Scheduler)**. Корень всей программы. Обрабатывает задачи, собранные в очереди, и следит за их правильным переключением между собой.
- **Очередь задач (Task queue)**. Здесь накапливаются новые задачи, поставленные на исполнение.
- **Задача (Task)**. Основной блок работы цикла событий. В задачах хранится информация о выполняемой корутине. Способна обрабатывать цепочку вложенных корутин.
- **Корутина (Coroutine)**. Исполняемый код, которым оперирует планировщик задач.
- **Системный вызов (SystemCall)**. Блоки кода, расширяющие функциональность планировщика.
- **Корутина для выполнения работы с I/O (I/O-tasks)**. В планировщик добавляется специальная задача (Task), предназначенная для обработки I/O-событий от ОС.
- **Селектор (Selector)**. Он принимает события от ОС и передаёт работу корутинам, ожидающим обработки I/O-сообщений.

Планировщик принимает задачи и справедливо обрабатывает накопленный список.


```python
from __future__ import annotations

from collections import deque
from collections.abc import Generator


class Scheduler:
    def __init__(self):
        self.ready = deque()
        self.task_map = {}

    def add_task(self, coroutine: Generator) -> int:
        new_task = Task(coroutine)
        self.task_map[new_task.tid] = new_task
        self.schedule(new_task)
        return new_task.tid

    def exit(self, task: Task):
        del self.task_map[task.tid]

    def schedule(self, task: Task):
        self.ready.append(task)

    def _run_once(self):
        task = self.ready.popleft()
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


Вся работа происходит в функции `event_loop()`, извлекающей задачи одну за другой. В функции `_run_once()` осуществляется обработка одной итерации цикла событий, где поочерёдно извлекаются и запускаются задачи, поставленные в очередь. Если задача не завершилась, то она возвращается в очередь `self.ready`. Очередь — `collections.deque`: планировщик работает в одном потоке, и синхронизированная `queue.Queue` с блокирующим `get` здесь не нужна. Выполненные задачи удаляет из планировщика функция `exit()`.

Задачу добавляет функция `add_task()`: она принимает корутину и создаёт с ней задачу в планировщике. Уже созданную задачу ставит в планировщик функция `schedule()`.

Устройство задачи:


```python
import types
from collections.abc import Generator

class Task:
    task_id = 0

    def __init__(self, target: Generator):
        Task.task_id += 1
        self.tid = Task.task_id  # Task ID
        self.target = target  # Target coroutine
        self.sendval = None  # Value to send
        self.stack = []  # Call stack

    # Run a task until it hits the next yield statement
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

Задача представляет собой обёртку вокруг корутины. У каждой задачи есть свой `id`, учитываемый в планировщике в словаре `task_map`. По его заполненности планировщик определяет, остались ли невыполненные задачи.

Задача выполняет корутины методом `run()`. Пусть имеется корутина, вызывающая другую корутину, а та вызывает третью:


```python
def square(x):
    yield x * x

def add(x, y):
    yield from square(x + y)

def main():
    result = yield add(1, 2)
    print(result)
    yield
```

Это несколько изменённый [код Бизли](https://web.archive.org/web/20240119054021/http://www.dabeaz.com/coroutines/trampoline.py) из его выступления. Выполним эту цепочку корутин внутри `Task`.


```python
task = Task(main())
task.run()
```

    9


Аналогично выполняются и остальные корутины, вложенные в цепочку. Остаётся научить планировщик работать с вводом-выводом.

Для этого ему потребуется селектор, обёртка над механизмом операционной системы, способным ожидать событий одновременно на многих файловых дескрипторах, зарегистрированных программой.


```python
import logging
from collections import deque
from collections.abc import Generator
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE


logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self.ready = deque()
        self.selector = DefaultSelector()
        self.task_map = {}

    def add_task(self, coroutine: Generator) -> int:
        new_task = Task(coroutine)
        self.task_map[new_task.tid] = new_task
        self.schedule(new_task)
        return new_task.tid

    def exit(self, task: Task):
        logger.info('Task %d terminated', task.tid)
        del self.task_map[task.tid]

    # I/O waiting
    def wait_for_read(self, task: Task, fd: int):
        try:
            key = self.selector.get_key(fd)
        except KeyError:
            self.selector.register(fd, EVENT_READ, (task, None))

        else:
            mask, (reader, writer) = key.events, key.data
            self.selector.modify(fd, mask | EVENT_READ, (task, writer))

    def wait_for_write(self, task: Task, fd: int):
        try:
            key = self.selector.get_key(fd)
        except KeyError:
            self.selector.register(fd, EVENT_WRITE, (None, task))

        else:
            mask, (reader, writer) = key.events, key.data
            self.selector.modify(fd, mask | EVENT_WRITE, (reader, task))

    def _remove_reader(self, fd: int):
        try:
            key = self.selector.get_key(fd)
        except KeyError:
            pass
        else:
            mask, (reader, writer) = key.events, key.data
            mask &= ~EVENT_READ
            if not mask:
                self.selector.unregister(fd)
            else:
                self.selector.modify(fd, mask, (None, writer))

    def _remove_writer(self, fd: int):
        try:
            key = self.selector.get_key(fd)
        except KeyError:
            pass
        else:
            mask, (reader, writer) = key.events, key.data
            mask &= ~EVENT_WRITE
            if not mask:
                self.selector.unregister(fd)
            else:
                self.selector.modify(fd, mask, (reader, None))

    def io_poll(self, timeout: float | None):
        if not self.selector.get_map():
            return              # ожидающих ввода-вывода нет: блокироваться не на чем
        events = self.selector.select(timeout)
        for key, mask in events:
            fileobj, (reader, writer) = key.fileobj, key.data
            if mask & EVENT_READ and reader is not None:
                self.schedule(reader)
                self._remove_reader(fileobj)
            if mask & EVENT_WRITE and writer is not None:
                self.schedule(writer)
                self._remove_writer(fileobj)

    def io_task(self) -> Generator:
        while True:
            if not self.ready:
                self.io_poll(None)
            else:
                self.io_poll(0)
            yield

    def schedule(self, task: Task):
        self.ready.append(task)

    def _run_once(self):
        task = self.ready.popleft()
        try:
            result = task.run()
        except StopIteration:
            self.exit(task)
            return
        self.schedule(task)

    def event_loop(self):
        self.add_task(self.io_task())
        while len(self.task_map) > 1:   # кроме самой io_task
            self._run_once()
```

Перед стартом цикла событий планировщик создаёт одну особую, бесконечную задачу `io_task`. Её бесконечный цикл забирает у селектора накопившиеся события и немедленно возвращает управление планировщику. Цикл событий работает, пока кроме `io_task` остаются другие задачи; сама она никогда не завершается, поэтому условие `while self.task_map` не остановилось бы никогда.

Если очередь задач пуста, селектор ожидает событий без тайм-аута, до появления новых. В противном случае тайм-аут равен 0, чтобы сразу забрать все события, накопленные операционной системой. Когда ни один дескриптор не зарегистрирован, `io_poll` сразу возвращается: ожидание без тайм-аута на пустом селекторе заблокировало бы программу навсегда.

Поступившие из селектора события обрабатываются, а отработанные файловые дескрипторы удаляются. Одна и та же задача может ожидать присланных данных и одновременно пытаться записать свои, поэтому в поле `data` хранится кортеж `(reader, writer)`.

`event_loop` предоставляет интерфейс для работы с сокетами, четыре метода:
- `wait_for_read`,
- `wait_for_write`,
- `_remove_reader`,
- `_remove_writer`.

Эти методы позволяют работать с циклом событий, встроенным в ОС.

Основным назначением цикла событий является переключение корутин, а обращаются ли те к сети, к диску или ничего не ожидают, для него безразлично.

Остаётся конструкция `SystemCall`. Цикл событий напоминает работу ОС, и механизм прерываний, передающий управление наверх, заимствован у неё: в асинхронном коде прерывание обеспечивает `yield`. После переключения контекста может вызываться системная функция, запрошенная корутиной. Например, для создания новых задач:


```python
class SystemCall:
    def handle(self, sched: Scheduler, task: Task):
        pass


class NewTask(SystemCall):
    def __init__(self, target: Generator):
        self.target = target

    def handle(self, sched: Scheduler, task: Task):
        tid = sched.add_task(self.target)
        task.sendval = tid
        sched.schedule(task)
```

В `Scheduler` добавляется фрагмент:


```python
class Scheduler:
    ...
    def _run_once(self):
        task = self.ready.get()
        try:
            result = task.run()
            if isinstance(result, SystemCall):
                result.handle(self, task)
                return
        except StopIteration:
            self.exit(task)
            return
        self.schedule(task)
```

А в `Task` — условие при выполнении корутин:


```python
class Task:
    ...
    def run(self):
        while True:
            try:
                result = self.target.send(self.sendval)
                if isinstance(result, SystemCall):
                    return result
                ...
```


`NewTask` предоставляет интерфейс для создания новых задач в цикле событий и абстрагирует клиентский код. Это эмуляция защищённой среды ОС, предоставляющей безопасные методы для работы с ядром, чтобы клиентский код не мешал другим программам, запущенным в системе. Аналогичным образом можно реализовать `KillTask` или `WaitTask`.

Последней проблемой являются блокирующие операции. Пока запущенная операция не завершится, цикл событий останавливается вместе с ней. Решается это на уровне сокетов: вызов `socket.setblocking(False)` переводит сокет в неблокирующий режим, и вместо ожидания он немедленно сообщает, что данных пока нет. Ожидать их будет селектор, сразу за всех.

## Asyncio

`asyncio` является основной встроенной библиотекой для асинхронного программирования.

С версии Python 3.5 в языке присутствует синтаксис async/await (PEP 492). Он предоставляет «нативные» корутины — отдельную сущность языка, а не повторно использованный генератор: вызов `async def` возвращает объект типа `coroutine`, перебрать который циклом `for` нельзя, а `await` допустим только внутри `async def`. Разделение позволило отличать корутины от генераторов на уровне синтаксиса и типов; в Python 3.6 к ним добавились асинхронные генераторы (PEP 525) и асинхронные включения (PEP 530), а генераторные корутины с декоратором `@asyncio.coroutine` удалены в Python 3.11.


Простая программа с async/await:


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
    asyncio.run(value())
```

Функция `asyncio.run` создаёт планировщик задач, устроенный по разобранным выше принципам, и закрывает его по завершении. Переключением между корутинами управляет `await`.

Основные функции `asyncio`:

- `gather(*aws)` запускает переданные корутины как задачи и ожидает все, возвращая результаты в порядке аргументов; корутины передаются отдельными аргументами, список — через распаковку `gather(*coros)`, иначе возникает `TypeError`. Выполнение конкурентное: ожидания перекрываются в одном потоке.
- `sleep` приостанавливает корутину на определённое количество секунд, отдавая управление циклу событий.
- `wait_for(aw, timeout)` ограничивает время ожидания одного объекта и отменяет его по истечении (с Python 3.11 для этого служит `asyncio.timeout`); `wait` ожидает набор задач по условию `return_when` и с Python 3.11 принимает только задачи и `Future`, но не корутины.

Основные функции `event_loop`:

- `get_event_loop` возвращает цикл событий текущего потока; с Python 3.12 вызов без текущего цикла выдаёт `DeprecationWarning` и создаёт цикл, а если цикл уже снят, например после `asyncio.run`, возбуждает `RuntimeError`; в 3.14 неявное создание цикла убрано. Внутри корутины цикл получают функцией `get_running_loop`, а в новом коде вместо связки `get_event_loop` и `run_until_complete` используется одна строка `asyncio.run(...)`.
- `run_until_complete` выполняет цикл до завершения переданной корутины или `Future`; `asyncio.run` (Python 3.7) — точка входа программы: создаёт цикл, выполняет корутину и закрывает цикл.
- `shutdown_asyncgens` закрывает незавершённые асинхронные генераторы вызовом `aclose`; `asyncio.run` вызывает его сам, а при ручном управлении циклом о нём часто забывают.
- `call_soon` ставит обычную функцию (не корутину) в очередь на ближайшую итерацию цикла и не ожидает её выполнения. Поставленная таким образом функция может бесконечно переставлять саму себя.

Ключевым отличием asyncio от предложенной реализации является то, что asyncio работает на функциях обратного вызова, колбэках (callback). Этот механизм распределяет время между задачами справедливее. Каждая корутина встаёт в очередь и дожидается исполнения, тогда как в простом планировщике переключения не произойдёт, пока вся цепочка корутин не выполнится, а остальные задачи, поставленные в очередь, всё это время простаивают. Недостатком колбэков является callback hell, когда после вызова каждой функции необходимо вызвать ещё одну функцию и ещё одну:


```python
func1.add_callback(
    func2.add_callback(
                func3.add_callback(func4)
        )
) 
```


Синтаксис async/await позволяет этого избежать.


```python
await func4()
await func3()
await func2()
await func1() 
```


Это возможно благодаря классу `Future`, скрывающему колбэки и делающему код линейным. Создавать `Future` вручную в современном коде почти не приходится: это выполняют `create_task` и `gather`.

### Задачи, тайм-ауты и группы задач

Корутины выполняются одновременно, только если каждая обёрнута в задачу (`Task`): последовательные `await a()` и `await b()` выполняют их по очереди. Задачи создают `gather`, `create_task` и группы задач.

| Средство `asyncio` | Назначение |
|---|---|
| `run(main())` | цикл событий для программы |
| `await gather(a, b, c)` | одновременное ожидание; результаты в порядке аргументов |
| `create_task(c)` | запуск корутины в фоне; ссылку на задачу сохраняют |
| `TaskGroup()` (Python 3.11) | группа задач; при ошибке одной отменяются остальные |
| `timeout(s)` (Python 3.11) | ограничение времени блока: `TimeoutError` |
| `to_thread(f, ...)` (Python 3.9) | блокирующая функция в отдельном потоке |

`create_task` ставит корутину в цикл событий и возвращает объект `Task`, который можно ожидать позже; ссылку на задачу сохраняют, иначе её может уничтожить сборщик мусора. С Python 3.11 предпочтительна группа задач `TaskGroup`: задачи, созданные в блоке `async with`, ожидаются при выходе из блока, а ошибка одной из них отменяет остальные и выходит наружу как `ExceptionGroup`, которую разбирает конструкция `except*`. После выхода из блока незавершённых задач не остаётся. Опрос нескольких приборов с отказом одного:

```python
import asyncio

async def poll(name, delay):
    await asyncio.sleep(delay)
    return name, delay

async def broken(name, delay):
    await asyncio.sleep(delay)
    raise ConnectionError(f'{name}: нет ответа')

async def survey():
    try:
        async with asyncio.TaskGroup() as tg:
            a = tg.create_task(poll('A', 0.3))
            tg.create_task(broken('B', 0.1))
    except* ConnectionError as eg:
        print('ошибки:', [str(e) for e in eg.exceptions])
    print('A отменена:', a.cancelled())

asyncio.run(survey())
```

```text
ошибки: ['B: нет ответа']
A отменена: True
```

`asyncio.timeout` ограничивает время блока: при превышении отменяется текущая задача, а вместе с ней — задачи, которые она ожидает через `gather` или `TaskGroup`, и блок завершается `TimeoutError`.

```python
async def limited():
    try:
        async with asyncio.timeout(0.6):
            return await asyncio.gather(poll('A', 0.3), poll('C', 0.8))
    except TimeoutError:
        return 'тайм-аут 0,6 с'

asyncio.run(limited())   # 'тайм-аут 0,6 с'
```

Блокирующую функцию из синхронной библиотеки, которую нельзя ожидать, выполняют в отдельном потоке через `asyncio.to_thread`, не останавливая цикл событий. Так же поступают с чтением и записью обычных файлов: асинхронного доступа к ним у `asyncio` нет, и даже сторонние пакеты вроде `aiofiles` работают через пул потоков. Общее время опроса нескольких приборов с общим тайм-аутом равно времени самого медленного прибора, а не сумме задержек.

### Асинхронная итерация

Протокол итерации имеет асинхронный вариант для источников, следующий элемент которых приходится ожидать: сообщений из сети, отсчётов прибора, строк из базы данных.

| Синхронно | Асинхронно |
|---|---|
| `__iter__`, `__next__` | `__aiter__`, `__anext__` |
| `StopIteration` | `StopAsyncIteration` |
| `for`, `with` | `async for`, `async with` |
| `iter()`, `next()` | `aiter()`, `anext()` (Python 3.10) |
| `def` с `yield` | `async def` с `yield` (Python 3.6) |

Асинхронный итерируемый объект определяет `__aiter__`, асинхронный итератор — `__anext__`, возвращающий ожидаемый объект, а окончание сообщается исключением `StopAsyncIteration`. Цикл `async for` вызывает эти методы и ожидает результат `__anext__`; если источник при этом ожидает данных, цикл событий тем временем выполняет другие задачи, а источник без `await` управление не отдаёт. Асинхронный генератор (PEP 525) — функция `async def` с `yield` — реализует протокол автоматически, как обычный генератор реализует синхронный.

```python
async def readings(dt, n):
    for i in range(n):
        await asyncio.sleep(dt)
        yield round((i + 1) * dt, 1)

async def consume():
    async for t in readings(0.1, 3):
        print('отсчёт', t)       # отсчёт 0.1, отсчёт 0.2, отсчёт 0.3

asyncio.run(consume())
```

Поток отсчётов прибора, поступающих с заданным интервалом, описывается асинхронным генератором, а потребитель обрабатывает отсчёты по мере поступления, не блокируя опрос других устройств. Асинхронное включение `[x async for x in source]` собирает элементы асинхронного источника внутри `async def`.

## Асинхронные фреймворки

Поверх `asyncio` (а иногда и в обход него) сформировалась экосистема. Физику она необходима, когда вокруг готового расчёта требуется построить сервис: принимать данные с прибора, передавать результаты коллегам, обращаться к базе лаборатории. Ниже приведены три характерных представителя.

### Twisted

Один из старейших асинхронных фреймворков, построенный на собственной реализации event-loop.

**Основные концепции:**

1. **Protocol**, описание получения и отправки данных
2. **Factory**, управление созданием объектов протокола
3. **Reactor**, собственная реализация event-loop
4. **Deferred-объекты**, цепочки обратных вызовов

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

### Aiohttp

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

### FastAPI

Современный фреймворк для быстрой разработки API, построенный на Starlette и Pydantic.

**Простой пример API:**

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Простые математические операции")

class Add(BaseModel):
    first_number: int = Field(title='Первое слагаемое')
    second_number: int = Field(0, title='Второе слагаемое')

class Result(BaseModel):
    result: int = Field(title='Результат')

@app.post("/add", response_model=Result)
async def create_item(item: Add):
    return {
        'result': item.first_number + item.second_number
    }
```

## Резюме

Асинхронность не является универсальным ускорителем; это инструмент, предназначенный для задач, в которых программа ожидает. Для расчётов она бесполезна. Одна корутина, надолго занявшая процессор, остановит весь цикл событий вместе с очередью, накопленной к этому моменту: поток по-прежнему один.

Выбор инструмента определяется следующим образом:

* **задача ожидает сеть или прибор** — применяется асинхронность, выигрыш может составлять десятки раз; чтение и запись файлов выносятся в поток через `asyncio.to_thread`, поскольку асинхронного доступа к обычным файлам у `asyncio` нет;
* **задача вычисляет** — применяются процессы (`multiprocessing`), векторизация NumPy или компиляция, разобранные в предыдущих главах;
* **и то и другое** — применяется цикл событий для ожиданий в сочетании с пулом процессов для расчётов через `loop.run_in_executor`.

**В асинхронном коде не должно быть блокирующих вызовов.** Одна `time.sleep()` или синхронный запрос к базе останавливает не свою корутину, а всю программу.
