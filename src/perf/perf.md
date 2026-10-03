# Скорость выполнения программ

В настоящей главе рассматривается последовательное ускорение одной задачи, при котором результат проверяется и измеряется на каждом шаге.

В качестве задачи выбрано умножение матриц — операция, встречающаяся в любом физическом расчёте, на которой видны все типичные способы оптимизации.

Начнём с наивной реализации на чистом Python, измерим её, найдём с помощью профилировщика узкое место, а затем последовательно применим четыре подхода: приёмы самого языка, компиляцию через Numba, компиляцию через Cython и готовую библиотеку. Разница между первой и последней версией составит несколько порядков. Все замеры выполнены в IPython на одной машине — виртуальной машине с двумя ядрами под Python 3.12, на которой записаны демонстрации лекции «Оптимизация и параллельные вычисления».

> **Слайды к главе.** Компиляция через Numba и Cython, пространственный заряд и NumPy изложены также в пятой и шестой частях лекции «Оптимизация и параллельные вычисления» с демонстрациями в терминале; слайды лекции доступны [на сайте книги](https://phys-dev.github.io/soft-dev-book/slides/lecture-09.html#/sec-jit) и [в PDF](https://github.com/phys-dev/soft-dev-book/releases/latest/download/soft-dev-book-lecture-09.pdf).

<iframe src="../slides/lecture-09.html#/sec-jit" title="Слайды лекции «Оптимизация и параллельные вычисления»: компиляция" loading="lazy" allowfullscreen style="width:100%; aspect-ratio:16/10; border:0; border-radius:6px"></iframe>

## Класс `Matrix`

Матрица описана как список списков с парой конструкторов:


```python
import random

class Matrix(list):
    @classmethod
    def zeros(cls, shape):
        n_rows, n_cols = shape
        return cls([[0] * n_cols for i in range(n_rows)])

    @classmethod
    def random(cls, shape):
        M, (n_rows, n_cols) = cls(), shape
        for i in range(n_rows):
            M.append([random.randint(-255, 255)
                      for j in range(n_cols)])
        return M

    def transpose(self):
        return self.__class__(zip(*self))

    @property
    def shape(self):
        return ((0, 0) if not self else
                (len(self), len(self[0])))
```


```python
def matrix_product(X, Y):
    """Вычисляет матричное произведение X и Y.

    >>> X = Matrix([[1], [2], [3]])
    >>> Y = Matrix([[4, 5, 6]])
    >>> matrix_product(X, Y)
    [[4, 5, 6], [8, 10, 12], [12, 15, 18]]
    >>> matrix_product(Y, X)
    [[32]]
    """
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    # верим, что с размерностями всё хорошо
    Z = Matrix.zeros((n_xrows, n_ycols))
    for i in range(n_xrows):
        for j in range(n_xcols):
            for k in range(n_ycols):
                Z[i][k] += X[i][j] * Y[j][k]
    return Z
```


Примеры из строки документации проверяются модулем `doctest`: он выполняет каждую строку с приглашением `>>>` и сравнивает напечатанное с ожидаемым.


```python
import doctest

test = doctest.DocTestFinder().find(matrix_product, globs=globals())[0]
doctest.DocTestRunner().run(test)
```

    TestResults(failed=0, attempted=4)


Все четыре проверки прошли. Корректность проверяется и после каждого шага ускорения: быстрая, но неверная функция бесполезна. Для этого результат первой версии сохраняется как эталон, и каждая следующая версия сравнивается с ним.

## Измерение времени выполнения

Скорость измеряется магической командой `%timeit`, описанной в главе [«Причины низкой скорости Python»](../dev/python/optimization.md).


```python
shape = 64, 64
X, Y = Matrix.random(shape), Matrix.random(shape)
reference = matrix_product(X, Y)

%timeit matrix_product(X, Y)
```

    17.7 ms ± 17.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Умножение двух матриц 64×64 занимает около 18 миллисекунд: за секунду выполняется лишь около 56 таких умножений. Найдём причину.

Определим вспомогательную функцию `bench`, генерирующую случайные матрицы указанного размера и `n_iter` раз перемножающую их в цикле.


```python
def bench(shape=(64, 64), n_iter=16):
    X = Matrix.random(shape)
    Y = Matrix.random(shape)
    for _ in range(n_iter):
        matrix_product(X, Y)
```


Рассмотрим происходящее подробнее с помощью `line_profiler`, описанного в той же главе. Пакет устанавливается отдельно (`pip install line_profiler`), а в IPython подключается как расширение: команда `%lprun -f функция выражение` выполняет выражение и печатает время каждой строки указанной функции.


```python
%load_ext line_profiler
%lprun -f matrix_product bench()
```

    Timer unit: 1e-09 s

    Total time: 1.27521 s
    File: <ipython-input-2-29ee3956b63c>
    Function: matrix_product at line 1

    Line #      Hits         Time  Per Hit   % Time  Line Contents
    ==============================================================
         1                                           def matrix_product(X, Y):
         2                                               """Вычисляет матричное произведение X и Y.
         3                                           
         4                                               >>> X = Matrix([[1], [2], [3]])
         5                                               >>> Y = Matrix([[4, 5, 6]])
         6                                               >>> matrix_product(X, Y)
         7                                               [[4, 5, 6], [8, 10, 12], [12, 15, 18]]
         8                                               >>> matrix_product(Y, X)
         9                                               [[32]]
        10                                               """
        11        16      21915.0   1369.7      0.0      n_xrows, n_xcols = X.shape
        12        16      11210.0    700.6      0.0      n_yrows, n_ycols = Y.shape
        13                                               # верим, что с размерностями всё хорошо
        14        16      79334.0   4958.4      0.0      Z = Matrix.zeros((n_xrows, n_ycols))
        15      1040     117873.0    113.3      0.0      for i in range(n_xrows):
        16     66560    7629317.0    114.6      0.6          for j in range(n_xcols):
        17   4259840  487990774.0    114.6     38.3              for k in range(n_ycols):
        18   4194304  779354293.0    185.8     61.1                  Z[i][k] += X[i][j] * Y[j][k]
        19        16       9794.0    612.1      0.0      return Z


Время в отчёте дано в наносекундах (`Timer unit: 1e-09 s`). Почти всё оно приходится на две строки внутреннего цикла: тело `Z[i][k] += X[i][j] * Y[j][k]` и сам цикл `for k`, выполненные по четыре миллиона раз. Под профилировщиком функция работает в несколько раз медленнее, чем без него, поэтому абсолютные значения из отчёта не сравнивают с замерами `%timeit`, сравнивают только доли.

## Ускорение средствами языка

Операция `list.__getitem__` не является бесплатной, поэтому поменяем местами вложенные циклы `for` и будем накапливать сумму в локальной переменной, чтобы код выполнял меньше обращений по индексу.


```python
def matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = Matrix.zeros((n_xrows, n_ycols))
    for i in range(n_xrows):
        Xi = X[i]
        for k in range(n_ycols):
            acc = 0
            for j in range(n_xcols):
                acc += Xi[j] * Y[j][k]
            Z[i][k] = acc
    return Z

assert matrix_product(X, Y) == reference
%timeit matrix_product(X, Y)
```

    11.2 ms ± 6.02 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%lprun -f matrix_product bench()
```

    Timer unit: 1e-09 s

    Total time: 1.20595 s
    File: <ipython-input-7-003c7298659e>
    Function: matrix_product at line 1

    Line #      Hits         Time  Per Hit   % Time  Line Contents
    ==============================================================
         1                                           def matrix_product(X, Y):
         2        16      22251.0   1390.7      0.0      n_xrows, n_xcols = X.shape
         3        16      11126.0    695.4      0.0      n_yrows, n_ycols = Y.shape
         4        16      79626.0   4976.6      0.0      Z = Matrix.zeros((n_xrows, n_ycols))
         5      1040     120653.0    116.0      0.0      for i in range(n_xrows):
         6      1024     148625.0    145.1      0.0          Xi = X[i]
         7     66560    7746232.0    116.4      0.6          for k in range(n_ycols):
         8     65536    8092070.0    123.5      0.7              acc = 0
         9   4259840  493775272.0    115.9     40.9              for j in range(n_xcols):
        10   4194304  686977762.0    163.8     57.0                  acc += Xi[j] * Y[j][k]
        11     65536    8971998.0    136.9      0.7              Z[i][k] = acc
        12        16       8211.0    513.2      0.0      return Z


Время сократилось примерно на треть, однако заметная доля по-прежнему уходит на строку внутреннего цикла `for j in range(n_xcols)`: на каждой итерации интерпретатор получает следующее число из `range` и связывает его с именем. Заменим внутренний цикл выражением `sum` по генератору.


```python
def matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = Matrix.zeros((n_xrows, n_ycols))
    for i in range(n_xrows):
        Xi, Zi = X[i], Z[i]
        for k in range(n_ycols):
            Zi[k] = sum(Xi[j] * Y[j][k] for j in range(n_xcols))
    return Z

assert matrix_product(X, Y) == reference
%timeit matrix_product(X, Y)
```

    12.4 ms ± 331 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%lprun -f matrix_product bench()
```

    Timer unit: 1e-09 s

    Total time: 0.793878 s
    File: <ipython-input-9-a5e1d26d5e4a>
    Function: matrix_product at line 1

    Line #      Hits         Time  Per Hit   % Time  Line Contents
    ==============================================================
         1                                           def matrix_product(X, Y):
         2        16      17875.0   1117.2      0.0      n_xrows, n_xcols = X.shape
         3        16      10917.0    682.3      0.0      n_yrows, n_ycols = Y.shape
         4        16      70000.0   4375.0      0.0      Z = Matrix.zeros((n_xrows, n_ycols))
         5      1040     118811.0    114.2      0.0      for i in range(n_xrows):
         6      1024     164327.0    160.5      0.0          Xi, Zi = X[i], Z[i]
         7     66560    7997148.0    120.1      1.0          for k in range(n_ycols):
         8     65536  785492252.0  11985.7     98.9              Zi[k] = sum(Xi[j] * Y[j][k] for j in range(n_xcols))
         9        16       6457.0    403.6      0.0      return Z


Под профилировщиком эта версия выглядит быстрее предыдущей, но доверять этому нельзя: строки генераторного выражения `line_profiler` не отслеживает и своих накладных расходов на них не начисляет. Замер `%timeit` без профилировщика показывает обратное: функция стала медленнее. Тело генератора по-прежнему исполняется интерпретатором для каждого элемента, а к нему добавляется возобновление генератора. Отсюда правило: версии сравнивают замером без профилировщика, а профилировщик применяют для поиска места, требующего внимания.

Обращения по индексу во внутреннем цикле убирает транспонирование второй матрицы: строки `X` и строки транспонированной `Y` перебираются парами через `zip`.


```python
def matrix_product(X, Y):
    Yt = Y.transpose()
    return Matrix([[sum(x * y for x, y in zip(Xi, Ytk)) for Ytk in Yt]
                   for Xi in X])

assert matrix_product(X, Y) == reference
%timeit matrix_product(X, Y)
```

    8.99 ms ± 15.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Генератор остаётся и здесь. Ускорение даёт только перенос всего внутреннего цикла в код на C: функция `operator.mul`, применённая через `map`, и `sum` работают без единой инструкции байт-кода на элемент, а в Python 3.12 и новее для скалярного произведения есть готовая функция `math.sumprod`.


```python
import operator

def matrix_product(X, Y):
    Yt = Y.transpose()
    return Matrix([[sum(map(operator.mul, Xi, Ytk)) for Ytk in Yt]
                   for Xi in X])

assert matrix_product(X, Y) == reference
%timeit matrix_product(X, Y)
```

    6.38 ms ± 7.01 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
import math

def matrix_product(X, Y):
    Yt = Y.transpose()
    return Matrix([[math.sumprod(Xi, Ytk) for Ytk in Yt] for Xi in X])

assert matrix_product(X, Y) == reference
%timeit matrix_product(X, Y)
```

    3.25 ms ± 10.9 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Приёмы самого языка ускорили умножение в несколько раз, однако каждое число по-прежнему остаётся объектом, а каждое умножение проходит через общий механизм выбора операции по типам. Дальше этот путь не ведёт.

## Numba

Списки Python Numba поддерживает лишь частично: однородный плоский список принимается с предупреждением об устаревании этого механизма, а список списков, как в классе `Matrix`, и список с элементами разных типов приводят к ошибке `TypeError`. Для генерации машинного кода необходим массив известного типа, поэтому перепишем `matrix_product` через ndarray, хранящий числа одного типа подряд.


```python
import numba
import numpy as np


@numba.njit
def jit_matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = np.zeros((n_xrows, n_ycols), dtype=X.dtype)
    for i in range(n_xrows):
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


Декоратор `@numba.njit` компилирует функцию при первом вызове под типы аргументов. Матрицы создаются генератором случайных чисел NumPy, `integers` которого по умолчанию возвращает 64-битные целые на любой платформе.


```python
import time

rng = np.random.default_rng(0)
Xa = rng.integers(-255, 255, shape)
Ya = rng.integers(-255, 255, shape)

t0 = time.perf_counter()
jit_matrix_product(Xa, Ya)                 # первый вызов: компиляция
print(f"первый вызов: {time.perf_counter() - t0:.3f} с")

assert (jit_matrix_product(np.array(X), np.array(Y)) == np.array(reference)).all()
%timeit jit_matrix_product(Xa, Ya)
```

    первый вызов: 0.165 с
    79.7 μs ± 53.1 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)


Первый вызов длится в тысячи раз дольше последующих: в него входит компиляция. Команда `%timeit` без ключей сначала подбирает число запусков, и компиляция приходится на этот подбор, а не на замер. Если же число запусков задано ключом `-n` или время одного вызова измеряется вручную, компиляция попадает в результат: среднее завышается, среднеквадратичное отклонение превышает само среднее, а IPython предупреждает, что самый медленный прогон оказался во много раз дольше самого быстрого. Поэтому функцию Numba перед замерами вызывают один раз. Параметр `cache=True` сохраняет скомпилированный код на диск, и при следующем запуске программы компиляция не повторяется.


## Настоящая задача: пространственный заряд

Умножение матриц является учебным примером; рассмотрим, что Numba даёт на реальной задаче. В коде REDPIC, которому посвящена [отдельная глава](../examples/redpic.md), пучок представлен ансамблем макрочастиц, а наиболее затратной функцией расчёта является суммирование кулоновских сил между частицами. Это эффект пространственного заряда, из-за которого сильноточный пучок расталкивает сам себя:

\\[ \vec F_i = \sum_{j \ne i} \frac{\vec r_i - \vec r_j}{|\vec r_i - \vec r_j|^3}. \\]

Каждая частица взаимодействует с каждой, поэтому сложность составляет \\(O(N^2)\\), где \\(N\\) — число частиц. Цикл, записанный напрямую, допускает и JIT-компиляцию, и распараллеливание, поскольку слагаемые для разных \\(i\\) вычисляются независимо.

```python
import numpy as np
from numba import njit, prange

def space_charge(x, y, z, Fx, Fy, Fz):
    for i in range(len(x)):
        for j in range(len(x)):
            if i != j:
                r3 = ((x[j]-x[i])**2 + (y[j]-y[i])**2 + (z[j]-z[i])**2)**1.5
                Fx[i] += (x[i]-x[j]) / r3
                Fy[i] += (y[i]-y[j]) / r3
                Fz[i] += (z[i]-z[j]) / r3
```


Для параллельной версии достаточно заменить внешний `range` на `prange`: таким образом Numba узнаёт, какой из вложенных циклов можно распределить по ядрам:

```python
def space_charge_par(x, y, z, Fx, Fy, Fz):
    for i in prange(len(x)):       # <-- единственное отличие
        for j in range(len(x)):
            if i != j:
                r3 = ((x[j]-x[i])**2 + (y[j]-y[i])**2 + (z[j]-z[i])**2)**1.5
                Fx[i] += (x[i]-x[j]) / r3
                Fy[i] += (y[i]-y[j]) / r3
                Fz[i] += (z[i]-z[j]) / r3

jit_version = njit(space_charge)                      # JIT
par_version = njit(parallel=True)(space_charge_par)   # JIT + ядра CPU
```


Запись `njit(func)` вместо `@njit` над определением удобна, когда одну функцию необходимо измерить в нескольких режимах: исходный код один, обёрток несколько. Функция `space_charge` без обёртки работает и со списками, и с массивами NumPy; измерим её в обоих случаях вместе с двумя скомпилированными версиями. Обе версии Numba компилируются заранее, вызовом на двух частицах, чтобы компиляция не попала в замер.

```python
def clock(f, n, lists=False):
    """Время одного вызова f для n случайных частиц, мс."""
    rng = np.random.default_rng(0)
    x, y, z = rng.random((3, n))
    F = np.zeros((3, n))
    if lists:
        x, y, z, F = x.tolist(), y.tolist(), z.tolist(), F.tolist()
    t0 = time.perf_counter()
    f(x, y, z, *F)
    return (time.perf_counter() - t0) * 1e3

warm = np.random.default_rng(1).random((3, 2))
jit_version(*warm, *np.zeros((3, 2)))
par_version(*warm, *np.zeros((3, 2)))

print("    N  списки, мс  массивы, мс  @njit, мс  parallel, мс")
for n in (256, 512, 1024, 2048, 4096):
    tl = f"{clock(space_charge, n, lists=True):11.1f}" if n <= 2048 else f"{'—':>11}"
    ta = f"{clock(space_charge, n):12.1f}" if n <= 1024 else f"{'—':>12}"
    print(f"{n:5d} {tl} {ta} {clock(jit_version, n):10.2f} "
          f"{clock(par_version, n):13.2f}")
```

        N  списки, мс  массивы, мс  @njit, мс  parallel, мс
      256        12.4         64.4       0.41          0.23
      512        51.6        276.5       1.64          0.88
     1024       233.4       1108.5       6.52          3.35
     2048       841.5            —      26.10         13.28
     4096           —            —     106.91         53.39


Из таблицы следуют три вывода.

Квадратичность видна в числах. При каждом удвоении \\(N\\) время растёт вчетверо, что и означает \\(O(N^2)\\). JIT-компиляция сложность не меняет: она сокращает время в десятки раз, но кривая остаётся квадратичной. Ускорение констант и улучшение асимптотики являются разными вещами.

Один декоратор даёт ускорение примерно в тридцать раз относительно цикла Python над списками и более чем в сто раз относительно того же цикла над массивами NumPy. Цикл над массивами в Python медленнее, чем над списками: каждое обращение `x[j]` создаёт объект `numpy.float64`, арифметика над которым дороже, чем над `float`. Переписывать не потребовалось ни одной строки: функция как была написана на Python, так и осталась.

Параллелизм на двух ядрах виртуальной машины добавляет ещё вдвое; на десятиядерном процессоре Apple M4 та же версия опережает последовательную в 4–5 раз, но не в десять. Часть ядер такого процессора производительные, часть — энергоэффективные; к этому добавляются накладные расходы на распределение работы, поглощающие на малых \\(N\\) почти весь выигрыш. Линейного масштабирования по числу ядер на практике почти не встречается.

С точки зрения физики важно следующее. Расчёт с 4096 макрочастицами на чистом Python занимает несколько секунд на один вызов функции, а в моделировании таких вызовов десятки тысяч, по одному на каждый шаг интегрирования. При двадцати тысячах шагов это около двадцати часов счёта против получаса у версии с `@njit`. Именно эта разница делает возможным численное моделирование динамики пучка на обычном сервере, без суперкомпьютера.

## Cython

Второй путь к машинному коду — Cython, язык, представляющий собой Python с объявлениями типов C: код транслируется в C и компилируется в модуль расширения. Ручной работы больше, однако и контроля больше. В IPython ячейку компилирует магическая команда `%%cython`, вне IPython — команда `cythonize -i файл.pyx`; в обоих случаях нужен компилятор C, а в Python 3.12 и новее — ещё и пакет setuptools.


```python
%load_ext cython
```


Скомпилируем без изменений версию с перестановкой циклов и накопителем, работающую со списками.


```python
%%cython
def cy_matrix_product(X, Y):
    n_xrows, n_xcols = len(X), len(X[0])
    n_ycols = len(Y[0])
    Z = [[0] * n_ycols for i in range(n_xrows)]
    for i in range(n_xrows):
        Xi = X[i]
        for k in range(n_ycols):
            acc = 0
            for j in range(n_xcols):
                acc += Xi[j] * Y[j][k]
            Z[i][k] = acc
    return Z
```


```python
assert cy_matrix_product(X, Y) == reference
%timeit cy_matrix_product(X, Y)
```

    9.44 ms ± 14.9 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Без объявлений типов Cython ускоряет код лишь на полтора десятка процентов (9,4 мс против 11,2 мс у той же функции на Python): каждая операция по-прежнему выполняется через C API интерпретатора, с объектами чисел и проверкой типов. Перепишем функцию для массивов NumPy, пока без типов.


```python
%%cython
import numpy as np

def cy_matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = np.zeros((n_xrows, n_ycols), dtype=X.dtype)
    for i in range(n_xrows):
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


```python
%timeit cy_matrix_product(Xa, Ya)
```

    68.8 ms ± 1.52 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)


Результат ухудшился: каждое обращение `X[i, j]` к массиву из скомпилированного кода по-прежнему идёт через Python и создаёт объект числа. Объявим типы. Современный способ работы с массивами в Cython — типизированные представления памяти (memoryviews): запись `const long long[:, ::1]` объявляет двумерный непрерывный массив 64-битных целых, доступный только для чтения. Такой код не требует `cimport numpy` и заголовков NumPy при сборке и принимает любой объект с буферным протоколом.


```python
%%cython
import numpy as np

def cy_matrix_product(const long long[:, ::1] X, const long long[:, ::1] Y):
    cdef Py_ssize_t n = X.shape[0], m = X.shape[1], p = Y.shape[1]
    cdef Py_ssize_t i, j, k
    cdef long long acc
    Z = np.zeros((n, p), dtype=np.int64)
    cdef long long[:, ::1] Zv = Z
    for i in range(n):
        for k in range(p):
            acc = 0
            for j in range(m):
                acc += X[i, j] * Y[j, k]
            Zv[i, k] = acc
    return Z
```


```python
assert (cy_matrix_product(Xa, Ya) == jit_matrix_product(Xa, Ya)).all()
%timeit cy_matrix_product(Xa, Ya)
```

    122 μs ± 73.9 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)


Объявленные типы позволяют Cython обращаться к числам напрямую, без объектов, и функция ускоряется в сотни раз по сравнению с версией без типов и в 27 раз — по сравнению с самой быстрой версией на чистом Python, использующей `math.sumprod`. Переменные цикла `i`, `j`, `k` объявлены типом `Py_ssize_t`, и цикл по `range` превращается в обычный цикл на C. В старых руководствах вместо представлений памяти встречается буферный синтаксис `np.ndarray[np.int64_t, ndim=2]` с `cimport numpy`; он работает, но документация Cython рекомендует представления памяти.

Отключим проверку выхода за границы массива и поддержку отрицательных индексов. Проверку переполнения целых отключать не требуется: в Cython она и так выключена по умолчанию.


```python
%%cython
import numpy as np
cimport cython

@cython.boundscheck(False)
@cython.wraparound(False)
def cy_matrix_product(const long long[:, ::1] X, const long long[:, ::1] Y):
    cdef Py_ssize_t n = X.shape[0], m = X.shape[1], p = Y.shape[1]
    cdef Py_ssize_t i, j, k
    cdef long long acc
    Z = np.zeros((n, p), dtype=np.int64)
    cdef long long[:, ::1] Zv = Z
    for i in range(n):
        for k in range(p):
            acc = 0
            for j in range(m):
                acc += X[i, j] * Y[j, k]
            Zv[i, k] = acc
    return Z
```


```python
assert (cy_matrix_product(Xa, Ya) == jit_matrix_product(Xa, Ya)).all()
%timeit cy_matrix_product(Xa, Ya)
```

    70.9 μs ± 83.3 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)


Взамен ошибка в индексе перестанет возбуждать `IndexError` и приведёт к обращению в чужую память без какого-либо сообщения, поэтому границы такого цикла необходимо выверять вручную. Какие строки по-прежнему обращаются к C API интерпретатора, показывает HTML-отчёт: `%%cython -a` в IPython или `cython -a файл.pyx` в терминале отмечают такие строки жёлтым.

## NumPy


```python
Xf, Yf = Xa.astype(np.float64), Ya.astype(np.float64)

%timeit Xf @ Yf
```

    21 μs ± 689 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)


```python
%timeit Xf.dot(Yf)
```

    21 μs ± 657 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)


```python
%timeit Xa @ Ya
```

    79 μs ± 109 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)


Оператор `@` вызывает функцию `np.matmul`, а `X.dot(Y)` — функцию `np.dot`. Для двумерных массивов их результаты совпадают, и обе функции передают вычисление одной и той же процедуре BLAS — библиотеки линейной алгебры, использующей векторные инструкции процессора и оптимально работающей с кешем, — поэтому совпадают и замеры. Различия проявляются в других случаях: `matmul` не допускает умножения на скаляр и для массивов большей размерности перемножает стопки матриц, тогда как `dot` суммирует произведения по последней оси первого аргумента и предпоследней оси второго.

Тип данных на входе определяет больше, чем выбор между `dot` и `@`. BLAS поддерживает только вещественные и комплексные типы; на целых матрицах NumPy выполняет расчёт собственным циклом, без блочной обработки и без нескольких ядер, и тратит на то же умножение в несколько раз больше времени, а с ростом размера матриц разрыв увеличивается.

Наивная реализация на чистом Python вычисляла произведение матриц 64×64 около 18 миллисекунд, NumPy с BLAS справляется за 21 микросекунду: ускорение более чем в восемьсот раз без единой строки на C со стороны разработчика.

**Прежде чем компилировать Python, имеет смысл попытаться не писать циклы вообще.** Numba и Cython необходимы там, где задача не векторизуется; в остальных случаях правильно применённый NumPy опережает их без сборки и объявленных типов.
