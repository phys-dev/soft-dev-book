# Почему Python не очень быстрый

Python - очень гибкий язык. Однако именно эта гибкость не позволяет делать многие оптимизации. <br>
Эффективные оптимизации закладываются на предположения и ограничения. <br>
Меньше ограничений - меньше простора для оптимизации.

## 1. Динамическая типизация

Чему это мешает:
* Много проверяем в Runtime. Тратим время.
* Не знаем точно с чем работаем - должны все время честно исполнять весь код

## 2. Изменяемость всего и вся

Несколько примеров:


```python
import builtins

print(len("abc"))
len = lambda obj: "mock!"
print(len("abc"))
len = builtins.len
```

    3
    mock!



```python
def my_func(a, b):
    return a + b

print(my_func(1, 2))

def new_func(a, b):
    return a * b

my_func.__code__ = new_func.__code__
print(my_func(1, 2))
```

    3
    2



```python
import sys
import ctypes

def change_local_variable():
    # Get prev frame object from the caller
    frame = sys._getframe(1)
    frame.f_locals['my_var'] = "hello"
    # Force update
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame),
                                          ctypes.c_int(0))

def do_smth():
    my_var = 1
    change_local_variable()
    print(my_var)

    
do_smth()
```

    hello


**Следствие: честно исполняем код**


```python
def do1():
    a = [-1] * 1000
    for i in range(len(a)):
        if i == 0:
            a[i] = 1
        else:
            a[i] = i
            
def do2():
    a = [-1] * 1000
    a[0] = 1
    for i in range(1, len(a)):
        a[i] = i
```


```python
%timeit -n100 do1()
%timeit -n100 do2()
```

    42.2 μs ± 970 ns per loop (mean ± std. dev. of 7 runs, 100 loops each)
    30.6 μs ± 1.14 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


## 3. CPython

1. Старый проект, написан задолго до многоядерных процессоров и т.д.
2. Производительность - не самая главная цель
3. Необходимость поддерживать совместимость с C API (особенности внутреннего дизайна)

Но есть и хорошое:

https://docs.python.org/3/whatsnew/3.11.html#summary-release-highlights

https://docs.python.org/3/whatsnew/3.11.html#faster-cpython
   

Будущее:
1. https://github.com/faster-cpython/
1. Multithreaded Python without the GIL - https://docs.google.com/document/d/18CXhDb1ygxg-YXNBJNzfzZsDFosB5e6BfnXLlejd9l0/edit#

# Когда оптимизировать

### *Premature optimization is the root of all evil*
Так ли это?

**Утверждение:**

В первую очередь мы пишим работающий код, а потом быстрый. Мы будем заниматься оптимизацией, когда функционал будет готов.

**Следствие:**

Производительность будет одна и та же все время, пока кто-то не найдет легко исправимые вещи, которые сделаю программу быстрее без неоходимости переделки большого количества кода.

Может повезти, а может не повезти.

**Правильный путь:**

Если вам нужна быстрая программа - сразу обращайте внимание на производительность. <br>
Ваш прототип должен быть быстрый - может даже быстрее, чем финальная версия.

Лучше начать с производительного решения и поддерживать его, чем надеятся, что получится оптимизировать медленное решение.

**Антипаттерн: большой комок грязи**
```
If you think good architecture is expensive, try bad architecture.
```


http://www.laputan.org/mud/mud.html
https://ru.wikipedia.org/wiki/%D0%91%D0%BE%D0%BB%D1%8C%D1%88%D0%BE%D0%B9_%D0%BA%D0%BE%D0%BC%D0%BE%D0%BA_%D0%B3%D1%80%D1%8F%D0%B7%D0%B8

## Мантра оптимизаций

1. Не делай
2. Делай это позже
3. Делай это оптимально

# Как оптимизировать

<center><img src="http://lh6.ggpht.com/_AALI9OaE6pk/Sjio4NqVK0I/AAAAAAAAAEM/9xwU-xHtEBY/s800/premature2.PNG">
<a href="https://dl.acm.org/citation.cfm?doid=356635.356640"> Knuth, D. E. 1974. Structured Programming with go to Statements</a>, ACM Comput. Surv. 6, 4 (Dec. 1974), 261-301.</center>


**Нужно найти место, куда прикладывать усилия!**

## Правило 1. Профилируй код

Возможно вы оптимизируете какую-то функцию в 10 раз. <br>
Однако она исполняется всего в 1% случаев.  <br>
В итоге польза от такой оптимизации довольно маленькая.

Не надо гадать какая часть чаще всего используется и дольше всего работает. <br>
Профилирование позволяет понять какая именно часть нужно оптимизировать.


## Правило 2. Не забывай про корректность

Ваши оптимизации вполне могут сломать код. <br>
Стоит покрыть дополнительными тестами те части, которые вы хотите поменять.

# Профилирование

Основной инструментарий:
1. cProfile
2. pstats
3. SnakeViz

Profile demo

Дополнительно хочется выделить два инструмента:
1. <a href="https://github.com/benfred/py-spy">py-spy</a> - позволяет снять профиль с работающей программы, без изменений кода
2. <a href="https://github.com/pyutils/line_profiler">line_profiler</a> - профилирование по строчкам (показывает количество времени проведенную в каждой строчке)

# Измерение времени

Иногда хочется просто замерить время, а не снимать полноценный профиль. <br>
Например, когда мы оптимизируем одну конкретную функцию.
Для этого есть модуль `timeit`


```python
import timeit

setup = '''
s='abcdefghijklmnopqrstuvwxyz'

def reverse_0(s: str) -> str:
    reversed_output = ''
    s_length = len(s)
    for i in range(s_length-1, 0-1, -1):
        reversed_output = reversed_output + s[i]
    return reversed_output

def reverse_5(s: str) -> str:
    return s[::-1]
'''
```


```python
timeit.timeit('reverse_0(s)', setup, number=10000)
```




    0.020173080999484228




```python
timeit.timeit('reverse_5(s)', setup, number=10000)
```




    0.001456363000215788



Функция `timeit` замеряет время с помощью функции `time.perf_counter`. <br>
На время измерений отключается сборщик мусора. <br>
При этом замеряется общее время нужное для `N` запусков, а не среднее.

Q: Почему все в строках?

A: Сам код `timeit` сделан в виде <a href="https://github.com/python/cpython/blob/master/Lib/timeit.py#L69">шаблоннонй строки</a>, куда подставляются параметры. <br>
Это позволяет сэкономить время на вызове функции, если бы мы ее передавали в виде объекта. <br>
В `timeit` можно передавать и функции по честному.

В IPython есть упрощение работы с функцией `timeit` - специальная команда `%timeit`. <br>
В отличии от функции эта команда выводит среднее время работы и стандартное отклонение.


```python
def reverse_0(s: str) -> str:
    reversed_output = ''
    s_length = len(s)
    for i in range(s_length-1, 0-1, -1):
        reversed_output = reversed_output + s[i]
    return reversed_output

%timeit -n100 reverse_0('abcdefghijklmnopqrstuvwxyz')
```

    2.09 μs ± 130 ns per loop (mean ± std. dev. of 7 runs, 100 loops each)


# Оптимизация

## Часть 1. Что оптимизировать

Оптимизация - это не только изменение кода. <br>
Можно выделить следующие уровни оптимизации:

### 1. Общая архитектура

То как система работает. Какие данные обрабатываются, как обрабатываются, объем данных, хранение и т.д.

### 2. Алгоритмы и структуры данных

Выбор того или иного алгоритма/структуры данных при обработке.

### 3. Реализация (код)

Непосредственная реализация алгоритма/структуры данных

### 4. Оптимизации во время компиляции

### 5. Оптимизации во время исполнения 

Мы будем обсуждать оптимизации на уровнях 3-5. <br>
Однако оптимизации на уровне 1-2 тоже важны. <br>
Более того у них больший потенциал для ускорения, но в тоже время они наиболее сложные.

В целом оптимизация - это не только про скорость, но еще и:
* Память
* Диск (место, I\O)
* Сеть
* Потребление энергии
* И многое другое

Мы обсудим только скорость работы и память.


Оптимизация - может быть сложной.

1. На оптимизацию тратится время. Кроме того не факт что ваши оптимизации что-то то дадут
1. Скорее всего система в целом станет сложнее, а код непонятнее
1. Не любые оптимизации полезны: можно выиграть скорость, но существенно проиграть память

## Часть 2. Пишем хороший Python код

Будем оптимизировать 3 уровень - реализацию (код).

### Совет 1. Используй builtins

Посчитаем количество элементов в списке:


```python
one_million_elements = [i for i in range(1000000)]

def calc_total(elements):
    total = 0
    for item in elements:
        total += 1
    
%timeit calc_total(one_million_elements)
```

    31.6 ms ± 404 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit len(one_million_elements)
```

    43.6 ns ± 1.03 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)


Пример выше - игрушечный. <br>
Однако в большинстве случаев вместо того, чтобы писать что-то свое лучше использовать готовую функцию из `builtins.`

### Совет 2. Правильная фильтрация

Попробум получить новый список, отфильтровав только нечетные элементы. <br>
Кроме того воспользуемся предыдущим советом и будем использовать `filter` из `builtins`.


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

    45.6 ms ± 344 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit my_filter2(one_million_elements)
```

    76.8 ms ± 780 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Q: Почему код стал медленнее?

A: Потому что у нас есть накладные расходы на создание генератора, а потом превращения генератора в список.

Давайте напишим код, который лучше отражает наши намеренья и будет сразу создавать нужный список:


```python
def my_filter3(elements):
    return [item for item in elements if item % 2]

%timeit my_filter3(one_million_elements)
```

    40.3 ms ± 1.01 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)



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

    55.3 ms ± 244 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit str_filter2(one_million_elements_str)
```

    49.8 ms ± 166 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Мораль: Не всегда использование `builtins` и генераторов делает код быстрее. <br>
Стоит проверять конкретно ваш случай.

### Совет 3. Правильная проверка вхождений

Напишим код, проверяющий наличие элемента:


```python
def check_in1(elements, number):
    for item in elements:
        if item == number:
            return True
    return False

%timeit check_in1(one_million_elements, 500000)
```

    9.02 ms ± 34.1 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit 500000 in one_million_elements
```

    5.65 ms ± 21.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Однако, время поиска зависит от того, где именно находится элемент


```python
%timeit 42 in one_million_elements
```

    492 ns ± 2.24 ns per loop (mean ± std. dev. of 7 runs, 1,000,000 loops each)


В Python есть `set` - стандартный инструмент для такой задачи


```python
one_million_elements_set = set(one_million_elements)
%timeit 500000 in one_million_elements_set
```

    37.3 ns ± 0.345 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)



```python
%timeit 42 in one_million_elements_set
```

    23.5 ns ± 0.223 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)


Однако, конечно же, мы проиграем время при создании множества:


```python
%timeit set(one_million_elements)
```

    46.7 ms ± 358 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Кроме того, конечно же мы проиграли память.

### Совет 4. Сортировка


```python
%timeit sorted(one_million_elements)
```

    16.9 ms ± 819 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit one_million_elements.sort()
```

    8.52 ms ± 700 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Мораль: inplace сортировка заметно быстрее. При возможности пользуйтесь именно ей.

### Совет 5. Условия if

Условия в конструкции if можно писать по разному:


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

При этом эти варианты работают разное время:


```python
%timeit check_false1(True)
```

    3.7 ms ± 31.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_false2(True)
```

    2.6 ms ± 9.39 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_false3(True)
```

    2.14 ms ± 13.9 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Попробуем угадать какой способ проверки на пустоту быстрее:
1. `if len(elements) == 0:`
2. `if elements == []:`
3. `if not element:`


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

    5.98 ms ± 38.9 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_empty2(one_million_elements)
```

    5.54 ms ± 53.1 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_empty2_new(one_million_elements)
```

    8.73 ms ± 33.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_empty3(one_million_elements)
```

    2.97 ms ± 43 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Мораль: пользуйтесь самым быстрым способом. Кроме производительности этот способ более Python-way.

### Совет 6. Спрашивать разрешения или обрабатывать последствия

Предпололжим мы хотим написать код, который будет обрабатывать объекты как имеющие некоторый аттрибут, так и нет.


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

Какой способ быстрее?


```python
%timeit check_attr1(foo)
```

    8.42 ms ± 70.3 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_attr2(foo)
```

    4.63 ms ± 29.5 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Разница станет еще большей, если нужно будет проверять несколько аттрибутов.

Где подвох?

Предположим, что у объектов в основном нет нужного аттрибута.


```python
class Bar:
    pass

bar = Bar()
```


```python
%timeit check_attr1(bar)
```

    5.91 ms ± 74.3 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_attr2(bar)
```

    59.5 ms ± 897 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Мораль: думайте какая ситуация чаще встречается и исходя из этого выбирайте из двух вариантов. <br>

Этот принцип работает для всех ситуаций, например, при создании запроса по сети.

### Совет 7. Особенности определения словаря и списка

В Python можно по разному объявлять словарь и список:


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
```

При этом способы через `[]` и `{}` быстрее `list()` и `dict()` соответственно: 


```python
%timeit create_list1()
```

    4.12 ms ± 127 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit create_list2()
```

    7.16 ms ± 164 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit create_dict1()
```

    4.04 ms ± 93.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit create_dict2()
```

    7.82 ms ± 115 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Q: Почему есть разница?

A: Обращение к имени занимает время. Интерпретатору нужно найти на что указывает имя. Можно посмотреть на код через модуль `dis` и убедиться, что код разный.


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

Если есть возможность не вызывать функцию - лучше это сделать. <br>
Вызов функции и создание frame требует значительного количества времени.


```python
def square(num):
    return num ** 2
```


```python
%timeit [square(num) for num in range(10000)]
```

    1.05 ms ± 6.03 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)



```python
%timeit [num ** 2 for num in range(10000)]
```

    694 μs ± 6.45 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


### Совет 9. Избегайте активной работы с глобальными переменными


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

    6.98 ms ± 56.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit work_with_local()
```

    4.16 ms ± 41.8 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



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

    4.14 ms ± 75.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


### Совет 10. Для математики используйте соответвующие библиотеки

Не надо пытаться писать математические вычисления на Python. <br>
Используйте готовые библиотеки, которые написаны на C и Fortran


```python
def list_slow():
    a = range(10000)
    return [i ** 2 for i in a]

%timeit list_slow()
```

    658 μs ± 4.81 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)



```python
import numpy as np

def list_fast():
    a = np.arange(10000)
    return a ** 2

%timeit list_fast()
```

    10.4 μs ± 32.3 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)


### <font color=red>Danger zone warning</font>
Используйте советы ниже только если это действительно даст какой-то сущетсвенный выигрыш

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

    616 μs ± 5.26 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)



```python
%timeit create_variables2()
```

    503 μs ± 8.69 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


Объявление переменных на одной строчки работает действительно быстрее, но не стоит так делать

### Совет 12. Поиск функций и аттрибутов

В Python поиск аттрибута сложная операция. Вызывается `__getattr__` и `__getattribute__`. <br>
Можно найти аттрибут один раз и сохранить его, чтобы не искать повторно:


```python
def squares1(elements):
    result = []
    for item in elements:
        result.append(item)

def squares2(elements):
    result = []
    append = result.append
    for item in elements:
        append(item)
```


```python
%timeit squares1(one_million_elements)
```

    24.6 ms ± 255 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit squares2(one_million_elements)
```

    29 ms ± 367 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


### Прочее

Проекты, заслуживающего внимания:
1. <a href="https://github.com/yglukhov/nimpy">nimpy</a> - Используем функции на языке Nim из Python
2. <a href="https://pythran.readthedocs.io/en/latest/">Pythran</a> - Другой подход к компиляции кода
3. <a href="https://github.com/pyston/pyston">Pyston</a> - еще один интерпретатор с JIT-компилятором

# Оптимизируем память

## Замеряем память

Замерять память в Python - довольно сложно.


```python
import sys

print(sys.getsizeof([i for i in range(1000000)]))
print(sys.getsizeof([i for i in range(100000)]))
```

    8448728
    800984


Кажется, что все работает как надо. Однако:


```python
class SomeClass:
    def __init__(self, i):
        self.i = i
        self.j = i * 2
        
sys.getsizeof([SomeClass(i) for i in range(1000000)])
```




    8448728



Почему-то список из `SomeClass` занимает столько же места как и список целых чисел. <br>
По факту `sys.getsizeof` хорошо работает только для простых типов и встроенных структур.

Q: Что делать? 
A: Использовать профилировщик памяти!


```python
%load_ext memory_profiler
%memit
```

    peak memory: 625.96 MiB, increment: 0.00 MiB


Этот подход тоже не идеален. Он замеряет лишь потребление памяти в один конкретный момент времени. <br>
Поэтому он не может все учитывать, а его результаты будут заметно плавать.


```python
%memit [n for n in range(10000000)]
```

    peak memory: 1007.02 MiB, increment: 377.12 MiB



```python
%memit [n for n in range(1000000)]
```

    peak memory: 632.71 MiB, increment: 0.07 MiB


## Можно ли получить memory-leakage в Python

Зависит от того, что считать memory-leakage. Как в C++ - только если явно работать со счетчиком ссылок, так как есть Garbage collection.

Немного подробнее: https://rushter.com/blog/python-garbage-collector/

Однако, можно получить долго-живущие "бесполезные" объекты.

Плюс есть особенности старых версий Python (2.7, до 3.4)


```python
def mutable_argument(arr=[]):
    arr.append(42)
    return a
```


```python
def unused_variable_in_long_process(arg1, arg2, arg3, unused_variable):
    pass
```


```python
class ClassCaching:
    cache = {}

    def calc(arg):
        result = cache.get(arg)
        if result is not None:
            return result
        result = do_calc(arg)
        cache[arg] = result
        return result
```

## Array

`array` позволяет более компактно хранить объекты примитвных типов.


```python
import array

%memit array.array('q', range(10000000))
```

    peak memory: 702.93 MiB, increment: 70.22 MiB


Подробнее про типы: https://docs.python.org/3/library/array.html

## np.array

`np.array` так же хранит объекты определенных типов и занимает меньше места, чем стандартный `list`.


```python
%memit np.arange(10000000)
```

    peak memory: 632.75 MiB, increment: 0.00 MiB


## tuple vs list


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



## Slots

Использование `__slots__` позволяет заметно сократить объем занимаемой памяти:


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
%memit [SomeClass(i) for i in range(1000000)]
```

    peak memory: 880.38 MiB, increment: 247.62 MiB



```python
class SomeClassSlots:
    __slots__ = ('a', 'b', 'c', 'd', 'e',)
    def __init__(self, i):
        self.a = i
        self.b = 2 * i
        self.c = 3 * i
        self.d = 4 * i
        self.e = 5 * i
                
%memit [SomeClassSlots(i) for i in range(1000000)]
```

    peak memory: 853.01 MiB, increment: 217.66 MiB


Кроме того у `__slots__` есть дополнительный плюс - ускорение времени обращения к аттрибуту


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

    824 μs ± 20.2 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)



```python
%timeit attr_work(d2)
```

    845 μs ± 7.76 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


Однако со `__slots__` не очень удобно работать при наследовании - необходимо его указывать в каждом классе иерархии.

## bitarray

bitarray - пакет для эффективного хранения набора булевских значений. <br>
Подробнее: https://github.com/ilanschnell/bitarray


```python
import bitarray.util as bu

%memit bu.zeros(10000000)
```

    peak memory: 634.12 MiB, increment: 0.00 MiB



```python
%memit [False for i in range(10000000)]
```

    peak memory: 701.93 MiB, increment: 67.81 MiB


Однако нужно понимать, что на обращение к элементу тратится время.

## range - вычисление вместо хранения


```python
a = range(1, 100000, 3)
print(a[10])
print(len(a))
```

    31
    33333


Такой же подход можно использовать и для более сложных последовательностей. <br>
Можно использовать смешанный подход с кешированием результата вычислений.

## Другой полезный инструментарий

1. https://github.com/mgedmin/objgraph
2. https://github.com/zhuyifei1999/guppy3


```python

```
