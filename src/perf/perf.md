# Скорость выполнения программ

Разговор об ускорении легко превратить в набор разрозненных советов. Мы пойдём другим путём: возьмём одну задачу и будем разгонять её шаг за шагом, каждый раз замеряя результат.

Задача — умножение матриц. Выбрана она не случайно: это самая обычная операция линейной алгебры, которая встречается в любом физическом расчёте, и одновременно удобный полигон, где видны все типичные приёмы оптимизации.

Начнём с наивной реализации на чистом Python, измерим её, найдём профилировщиком узкое место, а дальше последовательно применим четыре подхода: перестановку циклов, компиляцию через Numba, компиляцию через Cython и, наконец, готовую библиотеку. Забегая вперёд: разница между первой и последней версией составит несколько порядков.

## Класс `Matrix`

Для опытов понадобится сама матрица. Опишем её как список списков, добавив пару удобных конструкторов:


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
        n_rows, n_cols = self.shape
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


```python
%doctest_mode
```

    Exception reporting mode: Plain
    Doctest mode is: ON



```python
>>> X = Matrix([[1], [2], [3]])
>>> Y = Matrix([[4, 5, 6]])
>>> matrix_product(X, Y)
[[4, 5, 6], [8, 10, 12], [12, 15, 18]]
>>> matrix_product(Y, X)

[[32]]
```




    [[32]]




```python
%doctest_mode
```

    Exception reporting mode: Context
    Doctest mode is: OFF


# Измерение времени выполнения

Вроде бы всё работает, но насколько быстро? Проверь с помощью магической команды `timeit`.


```python
%%timeit shape = 64, 64; X = Matrix.random(shape); Y = Matrix.random(shape)
matrix_product(X, Y)
```

    86.6 ms ± 1.52 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)


Итого: умножение двух матриц 64x64 занимает почти 0.1 секунды. Почему так медленно?!

Определим вспомогательную функцию `bench`, которая генерирует случайные матрицы указанного размера, а затем `n_iter` раз перемножает их в цикле.


```python
def bench(shape=(64, 64), n_iter=16):
    X = Matrix.random(shape)
    Y = Matrix.random(shape)
    for iter in range(n_iter):
        matrix_product(X, Y)    
```

Попробуем присмотреться к происходящему повнимательнее с помощью модуля `line_profiler`.


```python
#!pip install line_profiler
```


```python
%load_ext line_profiler
%lprun -f matrix_product bench()
```

Обрати внимание: операция `list.__getitem__` не бесплатна. Поменяем местами циклы `for` так, чтобы код делал меньше обращений по индексу.


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
```


```python
%lprun -f matrix_product bench()
```

На 2 секунды быстрее, но всё ещё слишком медленно: больше 30% времени уходит исключительно на итерацию! Исправим это.


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
```


```python
%lprun -f matrix_product bench()
```

Функция `matrix_product` заметно похорошела. Но, кажется, это ещё не предел. Попробуем ещё раз убрать лишние обращения по индексу из самого внутреннего цикла.


```python
def matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = Matrix.zeros((n_xrows, n_ycols))
    Yt = Y.transpose()  # <--
    for i, (Xi, Zi) in enumerate(zip(X, Z)):
        for k, Ytk in enumerate(Yt):
            Zi[k] = sum(Xi[j] * Ytk[j] for j in range(n_xcols))
    return Z
```

# Numba

Numba не умеет работать со встроенными списками. Перепишем функцию `matrix_product` с использованием ndarray.


```python
import numba
import numpy as np


@numba.jit
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

Посмотрим, что получилось.


```python
shape = 64, 64
X = np.random.randint(-255, 255, shape)
Y = np.random.randint(-255, 255, shape)

%timeit -n100 jit_matrix_product(X, Y)
```

    The slowest run took 21.46 times longer than the fastest. This could mean that an intermediate result is being cached.
    495 µs ± 900 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


# Cython


```python
%load_ext cython
```


```python
%%capture
%%cython -a
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
        n_rows, n_cols = self.shape
        return self.__class__(zip(*self))

    @property
    def shape(self):
        return ((0, 0) if not self else
                (int(len(self)), int(len(self[0]))))

    
def cy_matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = Matrix.zeros((n_xrows, n_ycols))
    Yt = Y.transpose()
    for i, Xi in enumerate(X):
        for k, Ytk in enumerate(Yt):
            Z[i][k] = sum(Xi[j] * Ytk[j] for j in range(n_xcols))
    return Z
```


```python
X = Matrix.random(shape)
Y = Matrix.random(shape)
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    21.4 ms ± 1.36 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)


Проблема в том, что Cython не умеет эффективно оптимизировать работу со списками, в которых могут лежать элементы разных типов, поэтому перепишем `matrix_product` с использованием *ndarray*.


```python
X = np.random.randint(-255, 255, size=shape)
Y = np.random.randint(-255, 255, size=shape)
```


```python
%%capture
%%cython -a
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
%timeit -n100 cy_matrix_product(X, Y)
```

    176 ms ± 4.65 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)


Как же так! Стало только хуже: большая часть кода по-прежнему использует вызовы Python. Избавимся от них, аннотировав код типами.


```python
%%capture
%%cython -a
import numpy as np
cimport numpy as np

def cy_matrix_product(np.ndarray X, np.ndarray Y):
    cdef int n_xrows = X.shape[0]
    cdef int n_xcols = X.shape[1]
    cdef int n_yrows = Y.shape[0]
    cdef int n_ycols = Y.shape[1]
    cdef np.ndarray Z
    Z = np.zeros((n_xrows, n_ycols), dtype=X.dtype)
    for i in range(n_xrows):
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    173 ms ± 4 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)


К сожалению, аннотации типов не изменили время работы, потому что тело вложенного цикла Cython так и не смог оптимизировать. Время для фаталити: укажем тип элементов в *ndarray*.


```python
%%capture
%%cython -a
import numpy as np
cimport numpy as np

def cy_matrix_product(np.ndarray[np.int64_t, ndim=2] X,
                      np.ndarray[np.int64_t, ndim=2] Y):
    cdef int n_xrows = X.shape[0]
    cdef int n_xcols = X.shape[1]
    cdef int n_yrows = Y.shape[0]
    cdef int n_ycols = Y.shape[1]
    cdef np.ndarray[np.int64_t, ndim=2] Z = \
        np.zeros((n_xrows, n_ycols), dtype=np.int64)
    for i in range(n_xrows):
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    541 µs ± 5.14 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Попробуем пойти дальше и отключить проверки выхода за границы массива и переполнения целочисленных типов.


```python
%%capture
%%cython -a
import numpy as np

cimport cython
cimport numpy as np

@cython.boundscheck(False)
@cython.overflowcheck(False)
def cy_matrix_product(np.ndarray[np.int64_t, ndim=2] X, 
                      np.ndarray[np.int64_t, ndim=2] Y):
    cdef int n_xrows = X.shape[0]
    cdef int n_xcols = X.shape[1]
    cdef int n_yrows = Y.shape[0]
    cdef int n_ycols = Y.shape[1]
    cdef np.ndarray[np.int64_t, ndim=2] Z = \
        np.zeros((n_xrows, n_ycols), dtype=np.int64)
    for i in range(n_xrows):        
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    226 µs ± 2.84 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


# Numpy


```python
import numpy as np

X = np.random.randint(-255, 255, shape)
Y = np.random.randint(-255, 255, shape)
```


```python
%timeit -n100 X.dot(Y)
```

    151 µs ± 4.01 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit -n100 X@Y
```

    215 µs ± 3.8 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Профит. Оператор `@` — это то же самое матричное умножение, что и `X.dot(Y)`, только записанное короче; разница в замерах здесь на уровне шума.

Обрати внимание на масштаб: наивная реализация на чистом Python считала произведение матриц 64×64 около 0.1 секунды, NumPy справляется за сотни микросекунд — ускорение в сотни раз. И это без единой строчки на C с твоей стороны: под капотом NumPy вызывает BLAS — вылизанную десятилетиями библиотеку линейной алгебры, которая использует векторные инструкции процессора и оптимально работает с кешем.

Отсюда главный вывод раздела: **прежде чем компилировать Python, попробуй не писать циклы вообще**. Numba и Cython нужны там, где задача принципиально не векторизуется; во всех остальных случаях правильно применённый NumPy обгонит их без всякой возни со сборкой и типами.
