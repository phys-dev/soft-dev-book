# Оптимизация средствами самого Python

> Глава опирается на главу [«Причины низкой скорости Python»](../dev/python/optimization.md): прежде чем ускорять, необходимо измерить, а прежде чем измерять, необходимо понимать, откуда берётся медлительность.

В настоящей главе рассматриваются приёмы, не требующие ничего, кроме самого языка; компиляторы и векторизация рассматриваются в следующей главе. Выигрыш обычно скромнее, зато цена нулевая: код остаётся обычным Python, доступным для чтения любому коллеге.

> **Слайды к главе.** Приёмы языка и экономия памяти изложены также в третьей и четвёртой частях лекции «Оптимизация» с демонстрациями в терминале; слайды лекции доступны [на сайте книги](https://phys-dev.github.io/soft-dev-book/slides/lecture-09.html#/sec-lang) и [в PDF](https://github.com/phys-dev/soft-dev-book/releases/latest/download/soft-dev-book-lecture-09.pdf).

<iframe src="../slides/lecture-09.html#/sec-lang" title="Слайды лекции «Оптимизация»: приёмы языка" loading="lazy" allowfullscreen style="width:100%; aspect-ratio:16/10; border:0; border-radius:6px"></iframe>

## Объекты оптимизации

Оптимизация не сводится к правке кода, так как уровней, пригодных для ускорения уже написанной программы, несколько.

### 1. Общая архитектура

Устройство системы в целом: какие данные она обрабатывает, каким способом, в каком объёме и где их хранит.

### 2. Алгоритмы и структуры данных

Выбор алгоритма и структуры данных под конкретную обработку.

### 3. Реализация (код)

Способ записи выбранного алгоритма на языке.

### 4. Оптимизации во время компиляции

Преобразования, которые компилятор или JIT способен выполнить над уже написанным кодом.

### 5. Оптимизации во время исполнения

Настройки, которые можно изменить в уже работающей программе, включая кеши, ленивые вычисления и специализацию под найденный профилировщиком горячий путь.

Ниже рассматриваются уровни 3–5, хотя у первых двух потенциал ускорения наибольший, как и цена ошибки: переделывать выбранную архитектуру посреди работы дорого.

Оптимизировать можно не только скорость, но и память, место на диске и число обращений к нему, сетевой трафик, потребление энергии; в настоящей главе рассматриваются только скорость и память.

За оптимизацию всегда приходится платить.

1. Она отнимает время без гарантии, что потраченные часы принесут результат.
1. Система в целом становится сложнее, а код, написанный ради нескольких процентов, — менее понятным.
1. Легко выиграть в скорости и крупно проиграть в памяти.

## Рекомендации по написанию кода на Python

Третий уровень, реализация: дюжина рекомендаций, каждая с замером, выполненным на одной машине. Выигрыш дают не все.

### Совет 1. Встроенные функции

Подсчитаем количество элементов в заранее созданном списке.


```python
one_million_elements = [i for i in range(1000000)]

def calc_total(elements):
    total = 0
    for item in elements:
        total += 1
    
%timeit calc_total(one_million_elements)
```

    9.67 ms ± 130 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit len(one_million_elements)
```

    12.4 ns ± 0.0762 ns per loop (mean ± std. dev. of 7 runs, 100,000,000 loops each)


Пример является учебным, однако если необходимое уже присутствует в `builtins`, почти всегда быстрее использовать готовое: встроенные функции, написанные на C, обходятся без цикла на уровне интерпретатора.

### Совет 2. Правильная фильтрация

Отберём из списка нечётные элементы, в соответствии с предыдущей рекомендацией использовав встроенный `filter`.


```python
def my_filter1(elements):
    result = []
    for item in elements:
        if item % 2:
            result.append(item)
    return result
            
def my_filter2(elements):
    return list(filter(lambda x: x % 2, elements))
```


```python
%timeit my_filter1(one_million_elements)
```

    11.8 ms ± 63.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit my_filter2(one_million_elements)
```

    22.9 ms ± 66.6 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Замедление объясняется накладными расходами: `filter` создаёт итератор, к каждому элементу применяется Python-функция `lambda`, а полученный итератор ещё необходимо преобразовать в список.

Запишем то же самое выражением, создающим требуемый список сразу.


```python
def my_filter3(elements):
    return [item for item in elements if item % 2]

%timeit my_filter3(one_million_elements)
```

    10.6 ms ± 40 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
one_million_elements_str = [str(i) for i in range(1000000)]

def str_filter1(elements):
    return [item for item in elements if item.isdigit()]

def str_filter2(elements):
    return list(filter(str.isdigit, elements))
```


```python
%timeit str_filter1(one_million_elements_str)
```

    13.4 ms ± 16.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit str_filter2(one_million_elements_str)
```

    12.6 ms ± 242 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


`builtins` и генераторы не ускоряют код сами по себе: достаточно было заменить `lambda` на метод `str.isdigit`, написанный на C, и `filter` оказался быстрее. Каждый конкретный случай проверяется замером.

### Совет 3. Правильная проверка вхождений

> Разница между `in` по списку и по множеству разобрана в главе [«Сложность операций с коллекциями»](../dev/python/o-notation.md). Здесь рассматриваются цена построения множества и расход памяти.

Запишем код, проверяющий наличие элемента.


```python
def check_in1(elements, number):
    for item in elements:
        if item == number:
            return True
    return False

%timeit check_in1(one_million_elements, 500000)
```

    3.56 ms ± 13.2 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit 500000 in one_million_elements
```

    2.02 ms ± 4.06 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Однако время поиска зависит от положения элемента: список просматривается последовательно, пока не будет найдено заданное значение.


```python
%timeit 42 in one_million_elements
```

    159 ns ± 1.72 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)


Для такой задачи в Python предусмотрено множество `set`, проверка вхождения в которое осуществляется по хешу, то есть за \\(O(1)\\) вместо \\(O(n)\\).


```python
one_million_elements_set = set(one_million_elements)
%timeit 500000 in one_million_elements_set
```

    11.3 ns ± 0.00214 ns per loop (mean ± std. dev. of 7 runs, 100,000,000 loops each)


```python
%timeit 42 in one_million_elements_set
```

    8.08 ns ± 0.00693 ns per loop (mean ± std. dev. of 7 runs, 100,000,000 loops each)


За это приходится платить временем на построение множества.


```python
%timeit set(one_million_elements)
```

    11 ms ± 23.8 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Платить приходится и памятью, поскольку множество содержит хеш-таблицу с запасом, а не уложенные подряд элементы. Строить его ради одной проверки бессмысленно, а ради миллиона проверок необходимо.

### Совет 4. Сортировка


```python
import random

data = [random.random() for _ in range(1_000_000)]
%timeit sorted(data)
```

    128 ms ± 199 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


```python
%timeit (lambda a: a.sort())(data[:])
```

    128 ms ± 191 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Данные взяты случайные, и это существенно: на уже отсортированном списке Timsort вырождается в один линейный проход, и время сортировки снижается примерно в семь раз (18 мс против 128 мс). Копирование выполняют оба варианта: `sorted` создаёт копию внутри себя, а во втором варианте её создаёт срез, стоимость которого составляет около 2 мс. Поэтому на случайных данных варианты совпадают по времени в пределах погрешности: алгоритм один и тот же, и копию делают оба. Метод `sort` выигрывает, когда исходный порядок не нужен и сортируется сам список, без копии: тогда не тратятся ни время на копирование, ни память под второй список.

### Совет 5. Условия if

Условие в `if` можно записать по-разному, и выбор записи влияет на время, затрачиваемое в цикле.


```python
count = 100000

def check_false1(flag):
    for i in range(count):
        if flag == False:
            pass
    
def check_false2(flag):
    for i in range(count):
        if flag is False:
            pass

def check_false3(flag):
    for i in range(count):
        if not flag:
            pass
```


```python
%timeit check_false1(True)
```

    1.14 ms ± 25.9 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit check_false2(True)
```

    888 μs ± 1.31 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit check_false3(True)
```

    775 μs ± 799 ns per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


Сравним три варианта проверки на пустоту и определим, какой из них быстрее.
1. `if len(elements) == 0:`
2. `if elements == []:`
3. `if not elements:`


```python
def check_empty1(elements):
    for i in range(count):
        if len(elements) == 0:
            pass
    
def check_empty2(elements):
    for i in range(count):
        if elements == []:
            pass

def check_empty2_new(elements):
    for i in range(count):
        if elements == list():
            pass
        
def check_empty3(elements):
    for i in range(count):
        if not elements:
            pass
```


```python
%timeit check_empty1(one_million_elements)
```

    1.78 ms ± 600 ns per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit check_empty2(one_million_elements)
```

    1.78 ms ± 1.45 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit check_empty2_new(one_million_elements)
```

    2.57 ms ± 11.5 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit check_empty3(one_million_elements)
```

    1.02 ms ± 401 ns per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


Самым быстрым оказался и самый идиоматичный вариант `if not elements`, рекомендуемый любым руководством по стилю. Такое совпадение встречается нечасто.

### Совет 6. Спрашивать разрешения или обрабатывать последствия

Предположим, что код должен работать как с объектами, у которых требуемый атрибут есть, так и с объектами, у которых его нет.


```python
class Foo:
    attr1 = 'hello'
    
foo = Foo()
```


```python
def check_attr1(obj):
    for i in range(count):
        if hasattr(obj, 'attr1'):
            obj.attr1
            
def check_attr2(obj):
    for i in range(count):
        try:
            obj.attr1
        except AttributeError:
            pass
```


```python
%timeit check_attr1(foo)
```

    2.56 ms ± 13.1 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit check_attr2(foo)
```

    1.49 ms ± 28.5 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


Разница становится ещё больше, если атрибутов, требующих проверки, несколько.

Предположим теперь, что у объектов, поступающих в функцию, требуемый атрибут в основном отсутствует.


```python
class Bar:
    pass

bar = Bar()
```


```python
%timeit check_attr1(bar)
```

    1.85 ms ± 668 ns per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit check_attr2(bar)
```

    16.3 ms ± 74.2 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Исключение, возбуждённое один раз, обходится дёшево, а сто тысяч раз подряд — дорого. Выбор между `hasattr` и `try/except` определяется тем, какая ситуация встречается чаще.

### Совет 7. Особенности определения словаря и списка

Словарь и список можно объявить двумя способами, дающими одинаковый результат.


```python
def create_list1():
    for i in range(count):
        a = []

def create_list2():
    for i in range(count):
        a = list()
        
def create_dict1():
    for i in range(count):
        a = {}

def create_dict2():
    for i in range(count):
        a = dict()

def create_list3():
    new_list = list
    for i in range(count):
        a = new_list()
```


Способы через `[]` и `{}` быстрее `list()` и `dict()` соответственно.


```python
%timeit create_list1()
```

    1.45 ms ± 2.44 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit create_list2()
```

    2.2 ms ± 5.1 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit create_dict1()
```

    1.53 ms ± 36.4 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit create_dict2()
```

    2.35 ms ± 68.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Разница обусловлена в основном вызовом: литерал компилируется в одну инструкцию `BUILD_LIST`, тогда как `list()` требует найти имя и вызвать тип через общий механизм вызова. Поиск имени в версиях 3.11 и новее обходится дёшево благодаря специализированной инструкции, поэтому вызов через локальную переменную почти не быстрее:


```python
%timeit create_list3()
```

    2.18 ms ± 12.2 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Различие в составе инструкций показывает байт-код, разобранный модулем `dis`.


```python
import dis

dis.dis("[]")
```

      0           0 RESUME                   0

      1           2 BUILD_LIST               0
                  4 RETURN_VALUE


```python
import dis

dis.dis("list()")
```

      0           0 RESUME                   0

      1           2 PUSH_NULL
                  4 LOAD_NAME                0 (list)
                  6 CALL                     0
                 14 RETURN_VALUE


### Совет 8. Вызов функции

Если вызова функции можно избежать, его следует избежать: на каждый вызов создаётся кадр стека, и затраты времени на него заметны.


```python
def square(num):
    return num ** 2
```


```python
%timeit [square(num) for num in range(10000)]
```

    307 μs ± 2.64 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit [num ** 2 for num in range(10000)]
```

    215 μs ± 1.27 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


### Совет 9. Отказ от активной работы с глобальными переменными


```python
count = 100000

some_global = 0
def work_with_global():
    global some_global
    for i in range(count):
        some_global += 1
        
def work_with_local():
    some_local = 0
    for i in range(count):
        some_local += 1
```


```python
%timeit work_with_global()
```

    2.34 ms ± 56.2 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit work_with_local()
```

    1.5 ms ± 4.68 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
some_global = 0
def work_with_global_optimized():
    global some_global
    some_local = some_global
    for i in range(count):
        some_local += 1
    some_global = some_local
```


```python
%timeit work_with_global_optimized()
```

    1.5 ms ± 496 ns per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


### Совет 10. Специализированные библиотеки для математики

Численные расчёты нецелесообразно записывать циклами на Python, поскольку для этого существуют библиотеки на C и Фортране, дающие разницу в десятки раз.


```python
def list_slow():
    a = range(10000)
    return [i ** 2 for i in a]

%timeit list_slow()
```

    214 μs ± 859 ns per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
import numpy as np

def list_fast():
    a = np.arange(10000)
    return a ** 2

%timeit list_fast()
```

    5.57 μs ± 15.9 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)


### Приёмы ценой читаемости

Приёмы, приведённые ниже, ухудшают читаемость кода ради нескольких процентов; применять их имеет смысл только в том случае, если профилировщик показал, что эти проценты необходимы.

### Совет 11. Множественное присваивание


```python
def create_variables1():
    for i in range(10000):
        a = 0
        b = 1
        c = 2
        d = 3
        e = 4
        f = 5
        g = 6
        h = 7
        i = 8
        j = 9
        
def create_variables2():
    for i in range(10000):
        a, b, c, d, e, f, g, h, i, j = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
```


```python
%timeit create_variables1()
```

    174 μs ± 239 ns per loop (mean ± std. dev. of 7 runs, 10,000 loops each)


```python
%timeit create_variables2()
```

    149 μs ± 1.37 μs per loop (mean ± std. dev. of 7 runs, 10,000 loops each)


Объявление в одну строку быстрее: распаковка кортежа обходится дешевле десяти отдельных присваиваний. Однако читаемость такой строки крайне низка, и выигрыш в 25 микросекунд на десять тысяч итераций её не оправдывает.

### Совет 12. Поиск функций и атрибутов

Поиск атрибута в Python не является бесплатным: за ним стоит `__getattribute__`, а если тот не нашёл атрибута, то и `__getattr__`. Естественным решением представляется найти атрибут один раз и сохранить его в локальную переменную, не разыскивая заново на каждой итерации. Функции ниже копируют список поэлементно: первая вызывает метод `append` на каждой итерации, вторая заранее сохраняет его в локальную переменную.


```python
def copy_append(elements):
    result = []
    for item in elements:
        result.append(item)
    return result

def copy_cached(elements):
    result = []
    append = result.append
    for item in elements:
        append(item)
    return result
```


```python
%timeit copy_append(one_million_elements)
```

    6.18 ms ± 12.5 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


```python
%timeit copy_cached(one_million_elements)
```

    7.7 ms ± 10.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Рекомендация, годами переходящая из одной подборки об оптимизации в другую, проигрывает: начиная с версии 3.11 CPython специализирует вызов метода списка в байт-коде, и обычный `result.append(item)` оказывается быстрее вызова через заранее сохранённую ссылку.

Подобные рекомендации необходимо проверять замером на используемой версии интерпретатора.

### Прочее

Три проекта за пределами CPython решают ту же задачу иначе.

1. [nimpy](https://github.com/yglukhov/nimpy) позволяет вызывать функции на языке Nim из Python.
2. [Pythran](https://pythran.readthedocs.io/en/latest/) предлагает ещё один подход к компиляции Python-кода.
3. [Pyston](https://github.com/pyston/pyston) — альтернативный интерпретатор с JIT-компилятором, начатый в Dropbox; с 2022 года проект не развивается. Действующей альтернативой CPython с JIT-компилятором остаётся [PyPy](https://pypy.org/).

## Оптимизация памяти

Расчёт, не помещающийся в оперативную память, не выполняется вовсе или многократно замедляется: выделение памяти завершается ошибкой `MemoryError`, а при подкачке данные читаются с диска.

<iframe src="../slides/lecture-09.html#/sec-mem" title="Слайды лекции «Оптимизация»: память" loading="lazy" allowfullscreen style="width:100%; aspect-ratio:16/10; border:0; border-radius:6px"></iframe>

### Измерение памяти

Измерение памяти в Python затруднено, и первый способ, подсказанный документацией, вводит в заблуждение.


```python
import sys

print(sys.getsizeof([i for i in range(1000000)]))
print(sys.getsizeof([i for i in range(100000)]))
```

    8448728
    800984


На первый взгляд, всё работает корректно. Однако рассмотрим полученные числа внимательнее.


```python
class SomeClass:
    def __init__(self, i):
        self.i = i
        self.j = i * 2
        
sys.getsizeof([SomeClass(i) for i in range(1000000)])
```

    8448728


Список объектов `SomeClass` занимает столько же, сколько список целых чисел: `sys.getsizeof` измеряет размер самого списка, то есть массива указателей, а не объектов, на которые эти указатели ведут, и надёжно работает только для простых типов и встроенных структур, размещённых в непрерывном участке памяти.

Остаётся воспользоваться трассировкой выделений памяти. В стандартной библиотеке для этого предусмотрен модуль `tracemalloc`: он учитывает каждое выделение памяти интерпретатором, в том числе буферы массивов NumPy, и сообщает текущий и пиковый объём. Определим вспомогательную функцию, возвращающую объём памяти, выделенной при создании объекта:


```python
import tracemalloc

def traced_mib(make):
    """Объём памяти, выделенной при вызове make(), в МиБ."""
    tracemalloc.start()
    obj = make()
    size = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    return round(size / 2**20, 1)

traced_mib(lambda: [SomeClass(i) for i in range(1000000)])
```

    145.4


```python
traced_mib(lambda: [n for n in range(1000000)])
```

    38.6


Вместе с объектами список экземпляров `SomeClass` занимает 145 МиБ, почти в двадцать раз больше, чем показывает `getsizeof`, а список целых чисел — 38,6 МиБ, почти впятеро больше: каждое число является отдельным объектом (`sys.getsizeof(1)` даёт 28 байт, а аллокатор выделяет под него 32), к которому добавляется 8-байтовая ссылка из списка.

Пакет `memory_profiler` с магической командой `%memit`, встречающийся в старых руководствах, с 2022 года не сопровождается и требует отдельной установки. Он наблюдает потребление памяти процессом целиком в отдельные моменты времени, и его результаты заметно меняются от запуска к запуску: интерпретатор и аллокатор удерживают освобождённые страницы про запас и размещают в них новые объекты.

### Утечки памяти в Python

> Подсчёт ссылок, циклические ссылки и поколенческий сборщик разбирались в главе [«Объекты и память»](../dev/python/objects.md); там же рассмотрена ловушка с изменяемым аргументом по умолчанию. Здесь речь идёт о том, что утекает в долго живущей программе.

В смысле C++ утечек в Python почти нет: объект освобождается, как только на него не остаётся ссылок, а недостижимые циклы находит сборщик мусора; потерять память можно разве что нарушив счётчик ссылок в расширении, написанном на C. Подробнее об этом рассказано в [разборе устройства сборщика](https://rushter.com/blog/python-garbage-collector/).

Долгоживущие бесполезные объекты получить легко, и на практике утечкой обычно называют именно их. Классических способов три: изменяемый аргумент по умолчанию, забытая переменная, живущая всё время работы длинной функции, и заведённый на атрибуте класса кеш, из которого ничего не удаляется.


```python
def mutable_argument(arr=[]):
    arr.append(42)
    return arr
```


```python
def unused_variable_in_long_process(arg1, arg2, arg3, unused_variable):
    pass
```


```python
class ClassCaching:
    cache = {}                      # общий на весь класс, а не на экземпляр

    def calc(self, arg):
        result = self.cache.get(arg)
        if result is not None:
            return result
        result = do_calc(arg)
        self.cache[arg] = result    # записи отсюда никто не удаляет
        return result
```


В старых версиях Python (2.7 и все версии до 3.4) сборщик не умел разбирать циклические ссылки между объектами с `__del__`, и образованные ими циклы существовали до конца работы программы.

### Array

Модуль `array` хранит числа примитивных типов подряд, без отдельного объекта на каждый элемент.


```python
import array

traced_mib(lambda: array.array('q', range(10000000)))
```

    78.1


[Полный список кодов типов](https://docs.python.org/3/library/array.html) приведён в документации.

### np.array

`np.array` устроен аналогично, с фиксированным типом и уложенными подряд элементами, и занимает существенно меньше памяти, чем стандартный список. В отличие от `array`, он поддерживает вычисления.


```python
np.arange(10000000).nbytes / 2**20
```

    76.2939453125


```python
traced_mib(lambda: np.arange(10000000))
```

    76.3


`tracemalloc` учитывает и буфер массива NumPy, а точный размер данных известен и без замеров: атрибут `nbytes` возвращает `len * itemsize`.


### tuple vs list

Кортеж несколько компактнее списка: ему не требуется запас под рост. Разница невелика, зато видно, во что обходится списковое включение, создающее список с запасом места под будущие `append`.


```python
sys.getsizeof([i for i in one_million_elements])
```

    8448728


```python
sys.getsizeof(tuple(one_million_elements))
```

    8000040


```python
sys.getsizeof(list(one_million_elements))
```

    8000056


### Slots

Атрибут `__slots__` отменяет у экземпляров словарь `__dict__` и размещает объявленные поля в фиксированных ячейках, за счёт чего экономится память.


```python
class SomeClass:
    def __init__(self, i):
        self.a = i
        self.b = 2 * i
        self.c = 3 * i
        self.d = 4 * i
        self.e = 5 * i
```


```python
traced_mib(lambda: [SomeClass(i) for i in range(1000000)])
```

    259.8


```python
class SomeClassSlots:
    __slots__ = ('a', 'b', 'c', 'd', 'e',)
    def __init__(self, i):
        self.a = i
        self.b = 2 * i
        self.c = 3 * i
        self.d = 4 * i
        self.e = 5 * i
                
traced_mib(lambda: [SomeClassSlots(i) for i in range(1000000)])
```

    229.3


Экономия здесь около 12 %: большую часть памяти занимают пять целых чисел каждого экземпляра, а не сам экземпляр. Чем меньше памяти занимают значения полей, тем заметнее выигрыш от `__slots__`.

Обычно `__slots__` ускоряет и обращение к атрибуту, но не всегда.


```python
d1 = SomeClass(0)
d2 = SomeClassSlots(0)

def attr_work(obj):
    count = 0
    for i in range(10000):
        count += obj.a + obj.b + obj.c + obj.d + obj.e
```


```python
%timeit attr_work(d1)
```

    265 μs ± 886 ns per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


```python
%timeit attr_work(d2)
```

    260 μs ± 760 ns per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


Здесь разница оказалась в пределах шума: современный CPython кеширует поиск атрибута и в обычном `__dict__`.

С наследованием `__slots__` неудобен: указывать его приходится в каждом классе иерархии, иначе `__dict__` возвращается и экономия исчезает.

### bitarray

Пакет [bitarray](https://github.com/ilanschnell/bitarray) хранит булевы значения по одному биту на элемент, а не по указателю на объект, и на десяти миллионах флагов разница заметна.


```python
import bitarray.util as bu

bu.zeros(10000000).nbytes / 2**20
```

    1.1920928955078125


```python
traced_mib(lambda: [False for i in range(10000000)])
```

    85.0


Платой является время: упакованный флаг необходимо извлечь из байта.

### `range` и вычисление вместо хранения

Иногда последовательность не требуется хранить: `range` не держит элементы в памяти, а вычисляет требуемый по индексу, и `len` также вычисляется по формуле.


```python
a = range(1, 100000, 3)
print(a[10])
print(len(a))
```

    31
    33333


Тот же приём, вычисление вместо хранения, применим и к более сложным последовательностям, а промежуточным вариантом служит расчёт, сохраняющий в кеше наиболее часто запрашиваемые значения.

## Другой полезный инструментарий

Для исследования памяти полезны ещё два инструмента, работающих с живой кучей.

1. [objgraph](https://github.com/mgedmin/objgraph) строит граф ссылок и помогает установить, какой объект удерживает другой объект живым.
2. [guppy3](https://github.com/zhuyifei1999/guppy3) собирает подробную статистику по куче.


## Резюме

* Оптимизировать имеет смысл только измеренное: интуиция о том, где программа проводит время, систематически ошибается, поэтому сначала применяется профилировщик, затем вносятся правки.
* Оптимизация всегда имеет цену, отнимая время разработки, читаемость кода, а иногда и корректность, поэтому, прежде чем ускорять, необходимо убедиться, что медленная работа действительно составляет проблему.
* Самый дешёвый выигрыш обычно даёт не микрооптимизация, а смена структуры данных или алгоритма, когда замена списка на множество в проверке вхождения меняет \\(O(n)\\) на \\(O(1)\\).
* Для памяти существуют свои средства, такие как `__slots__`, `array` и генераторы вместо списков, не ускоряющие код, зато позволяющие обработать данные, которые иначе не поместились бы.
* **Сначала правильно, потом быстро.** Ускоренный неверный расчёт остаётся неверным.
