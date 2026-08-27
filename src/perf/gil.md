# Многопоточность и GIL

## Необходимый минимум: процессы и потоки

### Процесс

**Процесс** — это запущенная программа. Операционная система выделяет каждому процессу собственное, изолированное от остальных состояние:

* виртуальное адресное пространство — своя память, в которую другие процессы заглянуть не могут;
* указатель на исполняемую инструкцию;
* стек вызовов;
* системные ресурсы, например открытые файловые дескрипторы.

Если нужно выполнять несколько задач одновременно, их можно раздать разным процессам. Изоляция здесь и достоинство, и недостаток: процессы не мешают друг другу, но и обмениваться данными им сложно — общей памяти у них нет.

### Поток

**Поток** исполняется независимо от других потоков, как и процесс, но живёт *внутри* процесса и делит с ним адресное пространство и системные ресурсы. Отсюда главное различие: двум потокам одного процесса ничего не стоит работать с общими данными — они просто видят одни и те же объекты.

Это удобно ровно до тех пор, пока два потока не полезут в одни данные одновременно. Тогда начинаются гонки, о которых мы поговорим чуть ниже.

Порядком исполнения и процессов, и потоков распоряжается операционная система: она поочерёдно выдаёт каждому по нескольку тактов процессора.

## Модуль `threading`

Поток в Python — это самый обычный системный поток: его исполнением управляет операционная система, а не интерпретатор. Создать поток можно классом `Thread` из модуля стандартной библиотеки `threading`.


```python
import time
from threading import Thread

def countdown(n):
    for i in range(n):
        print(n - i - 1, "left")
        time.sleep(1)
```


```python
t = Thread(target=countdown, args=(3,))
```


```python
t.start()
```

    2 left


Альтернативный способ создать поток — наследование:


```python
class CountdownThread(Thread):
    def __init__(self, n):
        super().__init__()
        self.n = n
        
    def run(self): # вызывается методом start
        for i in range(self.n):
            print(self.n - i - 1, "left")
            time.sleep(1)
```


```python
t = CountdownThread(3)
```


```python
t.start()
```

    2 left


Недостаток этого подхода в том, что он ограничивает переиспользование кода: функциональность класса `CountdownThread` можно использовать только в отдельном потоке.

* При создании потока можно указать имя. По умолчанию это **'Thread-N'**:


```python
Thread().name
```




    'Thread-6'




```python
Thread(name="NumberCruncher").name
```




    'NumberCruncher'



* У каждого активного потока есть идентификатор — неотрицательное число, уникальное среди всех активных потоков.


```python
t = Thread()
t.start()
t.ident
```




    123145519448064



* Метод `join` позволяет дождаться завершения потока.
    * Исполнение вызывающего потока приостановится, пока поток t не завершится.
    * Повторные вызовы метода `join` не имеют эффекта.


```python
t = Thread(target=time.sleep, args=(5, )) 
t.start()
t.join() # блокирует на 5 секунд
t.join() # выполняется мгновенно
```

    1 left
    1 left
    0 left
    0 left


* Проверить, работает ли поток, можно с помощью метода `is_alive`:


```python
t = Thread(target=time.sleep, args=(5, )) 
t.start()
```


```python
t.is_alive() # False через 5 секунд
```




    True



* Демон — это поток, созданный с аргументом `daemon=True`:

* Отличие потока-демона от обычного потока в том, что потоки-демоны **автоматически** уничтожаются при выходе из интерпретатора.


```python
t = Thread(target=time.sleep, args=(5,), daemon=True)
t.start()
```


```python
t.daemon
```




    True



* В Python нет встроенного механизма завершения потоков — это не случайность, а осознанное решение разработчиков языка.
* Корректное завершение потока часто связано с освобождением ресурсов, например:
    * поток может работать с файлом, дескриптор которого нужно закрыть,
    * или захватить примитив синхронизации.
* Для завершения потока обычно используют флаг:


```python
class Task:
    def __init__(self):
        self._running = True
    
    def terminate(self):
        self._running = False
    
    def run(self, n):
        while self._running:
            ...
```

Набор примитивов синхронизации в модуле `threading` стандартный:
* `Lock` — обычный мьютекс, используется для организации эксклюзивного доступа к разделяемому состоянию.
* `RLock` — рекурсивный мьютекс, который разрешает потоку, владеющему мьютексом, захватывать его больше одного раза.
* `Semaphore` — вариация мьютекса, которую можно захватить не более фиксированного числа раз.
* `BoundedSemaphore` — семафор, который следит за тем, чтобы его захватывали и освобождали одинаковое число раз.

Все примитивы синхронизации реализуют единый интерфейс:
* метод `acquire` захватывает примитив синхронизации,
* а метод `release` освобождает его.


```python
class SharedCounter:
    def __init__(self, value):
        self._value = value
        self._lock = Lock()
    
    def increment(self, delta=1):
        self._lock.acquire()
        self._value += delta
        self._lock.release()
    
    def get(self):
        return self._value
```

## Модуль `queue`

Модуль `queue` реализует несколько потокобезопасных очередей:
* `Queue` — очередь FIFO,
* `LifoQueue` — очередь LIFO, то есть стек,
* `PriorityQueue` — очередь элементов — пар (priority, item).
* Никаких особых изысков в реализации очередей нет: все изменяющие состояние методы работают «внутри» мьютекса.
* Класс `Queue` использует в качестве контейнера `deque`, а классы `LifoQueue` и `PriorityQueue` — список.


```python
def worker(q):
    while True:
        item = q.get() # блокирующе ждёт следующий
        do_something(item) # элемент
        q.task_done() # уведомляет очередь о выполнении
        
def master(q):
    for item in source():
        q.put(item)
        
        # блокирующе ждёт, пока все элементы
        # очереди не будут обработаны
        q.join()
```

## Модуль `futures`

* Модуль `concurrent.futures` содержит абстрактный класс `Executor` и его реализацию в виде пула потоков — `ThreadPoolExecutor`.
* Интерфейс исполнителя состоит всего из трёх методов:


```python
from concurrent.futures import *
```


```python
executor = ThreadPoolExecutor(max_workers=4)
```


```python
executor.submit(print, "Hello, world!")
```

    Hello, world!




    <Future at 0x1043b1d90 state=running>



    



```python
list(executor.map(print, ["Knock?", "Knock!"]))
```

    Knock?
    Knock!





    [None, None]




```python
executor.shutdown()
```

* Исполнители поддерживают протокол менеджеров контекста:


```python
with ThreadPoolExecutor(max_workers=4) as executor:
    ...
```

* Метод `Executor.submit` возвращает экземпляр класса `Future`, который инкапсулирует асинхронное вычисление.

Что можно сделать с `Future`?


```python
with ThreadPoolExecutor(max_workers=4) as executor:
    f = executor.submit(sorted, [4, 3, 1, 2])
```

* Спросить о статусе вычисления:


```python
f.running(), f.done(), f.cancelled()
```




    (False, True, False)



* Блокирующе дождаться результата вычисления:


```python
print(f.result())
```

    [1, 2, 3, 4]



```python
print(f.exception())
```

    None


* Добавить функцию, которая будет вызвана после завершения вычисления:


```python
f.add_done_callback(print)
```

    <Future at 0x1043b7f10 state=finished returned list>


## Пример с модулем `futures`: `integrate`


```python
import math

def integrate(f, a, b, *, n_iter=1000):
    acc = 0
    step = (b - a) / n_iter
    for i in range(n_iter):
        acc += f(a + i * step) * step
    return acc
```


```python
integrate(math.cos, 0, math.pi / 2)
```




    1.0007851925466296




```python
from functools import partial

def integrate_async(f, a, b, *, n_jobs, n_iter=1000):
    executor = ThreadPoolExecutor(max_workers=n_jobs)
    spawn = partial(executor.submit, integrate, f,
                    n_iter=n_iter // n_jobs)
    step = (b-a)/n_jobs
    fs=[spawn(a+i*step,a+(i+1)*step)
        for i in range(n_jobs)]
    return sum(f.result() for f in as_completed(fs))
```


```python
integrate_async(math.cos, 0, math.pi / 2, n_jobs=2)
```




    1.0007851925466305



## Параллелизм и конкурентность

Сравни производительность последовательной и параллельной версий функции `integrate` с помощью «магической» команды `timeit`:


```python
%%timeit -n100
integrate(math.cos, 0, math.pi / 2, n_iter=10**6)
```

    154 ms ± 2.28 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%%timeit -n100
integrate_async(math.cos, 0, math.pi / 2, n_iter=10**6, n_jobs=2)
```

    142 ms ± 2.11 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)


### GIL

* GIL (global interpreter lock, глобальная блокировка интерпретатора) — это мьютекс, который гарантирует, что в каждый момент времени доступ к внутреннему состоянию интерпретатора имеет только один поток.
* Python C API позволяет освободить GIL, но это безопасно только при работе с объектами, которые не зависят от интерпретатора Python.

### Плох ли GIL?
* Ответ зависит от задачи.
* Наличие GIL делает невозможным использование потоков в Python для параллелизма: несколько потоков не ускоряют, а иногда даже замедляют программу.
* GIL не мешает использовать потоки для конкурентности при работе с вводом-выводом.

### C и Cython — лекарство от GIL


```python
%load_ext Cython
```


```cython
%%cython

from libc.math cimport cos

def integrate(f, double a, double b, long n_iter):
    cdef double acc = 0
    cdef double step=(b-a)/n_iter
    cdef long i
    with nogil:
        for i in range(n_iter):
            acc += cos(a + i * step) * step
    return acc
```


```python
%%timeit -n100
integrate_async(math.cos, 0, math.pi / 2, n_iter=10**6, n_jobs=2)
```

    5.88 ms ± 126 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


## Модуль `multiprocessing`
### Процессы — ещё одно лекарство от GIL

* Вместо потоков можно использовать процессы.
* У каждого процесса будет свой GIL, но он не помешает им работать параллельно.
* За работу с процессами в Python отвечает модуль `multiprocessing`:


```python
import multiprocessing as mp
```


```python
p = mp.Process(target=countdown, args=(5, ))
```


```python
p.start()
```

    4 left
    3 left
    2 left
    1 left
    0 left


* В модуле реализованы основные примитивы синхронизации: мьютексы, семафоры, условные переменные.
* Для организации взаимодействия между процессами можно использовать `Pipe` — основанное на сокетах соединение между двумя процессами:


```python
def ponger(conn):
    conn.send("pong")
```


```python
parent_conn, child_conn = mp.Pipe()
p = mp.Process(target=ponger, args=(child_conn, ))
```


```python
p.start()
```


```python
parent_conn.recv()
```




    'pong'




```python
p.join()
```

## Процессы и производительность

Реализация функции `integrate_async` на основе пула потоков работала долго, попробуем использовать пул процессов:


```python
from concurrent.futures import ProcessPoolExecutor
```


```python
def integrate_async(f, a, b, *, n_jobs, n_iter=1000):
    executor = ProcessPoolExecutor(max_workers=n_jobs)
    spawn = partial(executor.submit, integrate, f,
                    n_iter=n_iter // n_jobs)

    step = (b - a) / n_jobs
    fs=[spawn(a + i * step, a + (i + 1) * step)
        for i in range(n_jobs)]
    
    return sum(f.result() for f in as_completed(fs))
```


```python
%%timeit -n100
integrate_async(math.cos, 0, math.pi / 2, n_iter=10**6, n_jobs=2)
```

    16.6 ms ± 144 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


## Пакет `joblib`

Пакет `joblib` реализует параллельный аналог цикла `for`, который удобен для параллельного выполнения независимых задач.


```python
from joblib import Parallel, delayed

def integrate_async(f, a, b, *, n_jobs, n_iter=1000, backend=None):
    step = (b - a) / n_jobs
    with Parallel(n_jobs=n_jobs, backend=backend) as parallel:
        fs = (delayed(integrate)(f, a + i * step,
                                 a + (i + 1) * step, 
                                 n_iter=n_iter // n_jobs)
              for i in range(n_jobs))
    return sum(parallel(fs))
```


```python
%%timeit -n100
integrate_async(math.cos, 0, math.pi / 2, n_iter=10**6, n_jobs=2, backend="threading")
```

    104 ms ± 280 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%%timeit -n100
integrate_async(math.cos, 0, math.pi / 2, n_iter=10**6, n_jobs=2, backend="multiprocessing")
```

    290 ms ± 1.13 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)


## Резюме

* GIL — это глобальный мьютекс, который ограничивает использование потоков для параллелизма в программах на Python.
* Программам, которые в основном занимаются вводом-выводом, GIL не страшен: в CPython эти операции освобождают GIL.
* Для программ, которым нужен параллелизм, есть варианты повышения производительности:
    * написать критичную функциональность на C или Cython;
    * или использовать модуль `multiprocessing`.

## JIT-компилятор `numba`


```python
import math
from numba import jit, prange

@jit(nopython=True, parallel=True, fastmath=True, cache=True)
def integrate(a, b, *, n_iter=1000):
    acc = 0
    step = (b - a) / n_iter
    for i in prange(n_iter):
        acc += math.cos(a + i * step) * step
    return acc
```


```python
%%timeit -n100
integrate(0, math.pi / 2, n_iter=10**6)
```

    5.11 ms ± 983 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Профит.
