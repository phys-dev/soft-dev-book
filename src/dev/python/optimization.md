# Почему Python не очень быстрый

Python — очень гибкий язык, и эта самая гибкость закрывает дорогу многим оптимизациям. Всякая оптимизация опирается на предположения и ограничения. Чем меньше компилятору позволено считать заранее известным, тем меньше у него простора. Разберём три главные причины, по которым Python платит за удобство скоростью.

## 1. Динамическая типизация

Тип значения становится известен только во время исполнения, и отсюда две беды. Во-первых, интерпретатор проверяет типы на каждом шаге, а это время. Во-вторых, он не знает заранее, с чем работает, и потому обязан исполнять весь код буквально. Выбросить заведомо ненужную ветку или посчитать выражение заранее он не вправе.

## 2. Изменяемость всего и вся

Менять в Python можно почти всё, причём на ходу — встроенные имена, тело уже определённой функции, даже локальные переменные чужого кадра стека. Несколько примеров:


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
    # берём объект предыдущего кадра стека у вызывающей стороны
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

Пример рассчитан на Python до 3.12 включительно. Начиная с 3.13 действует PEP 667:
`f_locals` стал прокси, пишущим прямо в переменные кадра, поэтому строчки
с `ctypes` больше не нужно — а функции `PyFrame_LocalsToFast` в C API уже и нет,
и обращение к ней даст `AttributeError`. Сам фокус при этом никуда не делся,
записать в чужой кадр по-прежнему можно, только короче.

Отсюда следствие. Интерпретатор обязан выполнять написанное слово в слово. Он не может вынести проверку `i == 0` из цикла, потому что не знает, не поменяется ли `a`, `i` или сам `range` по дороге. Такую оптимизацию приходится делать руками.


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

Третья причина — сама эталонная реализация языка.

1. CPython — старый проект, написанный задолго до многоядерных процессоров.
2. Производительность никогда не была его главной целью.
3. Приходится сохранять совместимость с C API, а это связывает руки при изменении внутреннего устройства.

Но есть и хорошее. Начиная с версии 3.11 CPython заметно ускорился: об этом [обзор нововведений](https://docs.python.org/3/whatsnew/3.11.html#summary-release-highlights) и отдельный раздел [Faster CPython](https://docs.python.org/3/whatsnew/3.11.html#faster-cpython). Работа продолжается — за ней можно следить в проекте [faster-cpython](https://github.com/faster-cpython/), а отдельная линия, [Multithreaded Python without the GIL](https://docs.google.com/document/d/18CXhDb1ygxg-YXNBJNzfzZsDFosB5e6BfnXLlejd9l0/edit#), метит в ту самую глобальную блокировку, о которой пойдёт речь в главе про GIL.

## Когда оптимизировать

Прежде чем разбираться, как оптимизировать, стоит договориться, когда за это вообще стоит браться.

## *Premature optimization is the root of all evil*

Знаменитую фразу Кнута обычно понимают так: сначала пишем работающий код, а быстрым сделаем потом, когда функциональность готова. Звучит разумно, но следствие получается неприятное. Производительность останется ровно такой, какая вышла случайно, пока кто-нибудь не наткнётся на легко исправимое место, которое ускорит программу без переделки половины кода. Может повезти, а может и не повезти.

Поэтому, если тебе нужна быстрая программа, думай о скорости сразу. Прототип должен быть быстрым — иногда даже быстрее финальной версии. Начать с производительного решения и поддерживать его дешевле, чем надеяться разогнать медленное.

Обратная крайность известна не хуже — «большой комок грязи», архитектура, которой не случилось:
```
If you think good architecture is expensive, try bad architecture.
```


Подробнее — в [эссе Фута и Йодера](http://www.laputan.org/mud/mud.html) и в [статье Википедии](https://ru.wikipedia.org/wiki/%D0%91%D0%BE%D0%BB%D1%8C%D1%88%D0%BE%D0%B9_%D0%BA%D0%BE%D0%BC%D0%BE%D0%BA_%D0%B3%D1%80%D1%8F%D0%B7%D0%B8).

## Мантра оптимизаций

1. Не делай
2. Делай это позже
3. Делай это оптимально

Противоречия с предыдущим разделом здесь нет. Думать о производительности стоит с самого начала, а вот *переписывать* готовый код ради скорости — только когда измерения показали, что это действительно нужно. Первый пункт не шутка. Самая быстрая оптимизация — та, которую не пришлось делать, потому что программа и так укладывается в отведённое время.

## Как оптимизировать

> Программисты тратят чудовищно много времени, размышляя о скорости некритичных частей программы, и эти попытки ускорения оказываются вредны, если учесть отладку и сопровождение. Про мелкую эффективность надо забыть в 97 % случаев: **преждевременная оптимизация — корень всех зол**. Но нельзя упускать возможности в тех критических 3 %.
>
> *Д. Кнут, [Structured Programming with go to Statements](https://dl.acm.org/doi/10.1145/356635.356640), ACM Computing Surveys, 1974*


Главное — найти то место, куда стоит прикладывать усилия. На это работают два правила.

## Правило 1. Профилируй код

Допустим, ты ускорил функцию в десять раз. Вот только исполняется она в одном проценте случаев, и общий выигрыш выходит мизерным.

Гадать, какая часть программы работает дольше всего, бесполезно. Профилировщик отвечает на этот вопрос точно, а интуиция — почти никогда.


## Правило 2. Не забывай про корректность

Оптимизация легко ломает код, причём тихо. Результат остаётся правдоподобным, но неверным. Прежде чем переписывать кусок ради скорости, покрой его тестами — иначе ускорение будет не с чем сверить.

## Профилирование

Базовый набор почти весь входит в стандартную поставку: `cProfile` собирает профиль, `pstats` его разбирает и сортирует, а SnakeViz рисует результат картинкой в браузере.

Отдельно стоит знать ещё два инструмента:

1. [py-spy](https://github.com/benfred/py-spy) — снимает профиль с уже работающей программы, не требуя менять её код. Незаменим, когда расчёт идёт третьи сутки и перезапускать его никак нельзя.
2. [line_profiler](https://github.com/pyutils/line_profiler) — профилирование построчное: показывает, сколько времени провела каждая строка.

## Измерение времени

Иногда полноценный профиль не нужен, надо просто замерить время одной функции. Для этого в стандартной библиотеке есть модуль `timeit`.


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



Функция `timeit` замеряет время по `time.perf_counter`, на время измерения отключает сборщик мусора и возвращает суммарное время `N` запусков, а не среднее.

Почему всё передаётся строками? Внутри `timeit` устроен как [шаблонная строка](https://github.com/python/cpython/blob/master/Lib/timeit.py#L69), в которую подставляются твои параметры, — так из замера уходят накладные расходы на вызов функции-обёртки. Настоящие функции `timeit` тоже принимает, просто в замер тогда попадёт и их вызов.

В IPython для того же есть магическая команда `%timeit`. В отличие от функции, она выводит среднее время и стандартное отклонение.


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


## Оптимизация

Дальше — практическая часть: что вообще поддаётся оптимизации и как писать на Python так, чтобы не тормозило.

## Часть 1. Что оптимизировать

Оптимизация — не только правка кода. Уровней, на которых можно ускорять программу, несколько.

### 1. Общая архитектура

То, как система устроена целиком: какие данные она обрабатывает, каким способом, в каком объёме и где их хранит.

### 2. Алгоритмы и структуры данных

Выбор алгоритма и структуры данных под конкретную обработку.

### 3. Реализация (код)

То, как выбранный алгоритм записан на языке.

### 4. Оптимизации во время компиляции

То, что компилятор или JIT способен сделать за тебя.

### 5. Оптимизации во время исполнения

То, что можно подкрутить в уже работающей программе: кеши, ленивые вычисления, специализация под горячий путь.

Дальше речь пойдёт об уровнях 3–5. Это не значит, что первые два менее важны. Как раз у них потенциал ускорения наибольший, и цена ошибки тоже — переделывать архитектуру посреди работы дорого.

Оптимизировать, кстати, можно не только скорость. Столь же осмысленно бороться за память, за место на диске и число обращений к нему, за сетевой трафик, за потребление энергии. Мы разберём только скорость и память.

И помни, что за оптимизацию всегда приходится платить:

1. Она отнимает твоё время, и нет никакой гарантии, что что-то даст.
1. Система в целом станет сложнее, а код — непонятнее.
1. Не всякая оптимизация полезна — легко выиграть в скорости и крупно проиграть в памяти.

## Часть 2. Пишем хороший Python код

Займёмся третьим уровнем — самой реализацией. Ниже дюжина советов, и каждый с замером. Выигрыш дают не все.

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


Пример игрушечный, но мораль общая. Если нужное уже есть в `builtins`, почти всегда быстрее взять готовое, чем писать своё. Встроенные функции реализованы на C, цикла на уровне интерпретатора в них нет.

### Совет 2. Правильная фильтрация

Отберём из списка нечётные элементы. Заодно воспользуемся предыдущим советом и возьмём встроенный `filter`.


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


Почему стало медленнее? Появились накладные расходы. `filter` создаёт итератор, к каждому элементу применяется Python-функция `lambda`, а потом итератор ещё нужно превратить в список.

Запишем то же самое так, чтобы нужный список создавался сразу:


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


Итак, `builtins` и генераторы не ускоряют код сами по себе. Стоило заменить `lambda` на готовый метод `str.isdigit`, и картина стала обратной, `filter` выиграл. Проверяй свой случай замером.

### Совет 3. Правильная проверка вхождений

Напишем код, проверяющий наличие элемента:


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


Но время поиска зависит от того, где именно лежит элемент:


```python
%timeit 42 in one_million_elements
```

    492 ns ± 2.24 ns per loop (mean ± std. dev. of 7 runs, 1,000,000 loops each)


Для такой задачи в Python есть множество — `set`. Проверка вхождения в него идёт по хешу, то есть за \\(O(1)\\) вместо \\(O(n)\\):


```python
one_million_elements_set = set(one_million_elements)
%timeit 500000 in one_million_elements_set
```

    37.3 ns ± 0.345 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)



```python
%timeit 42 in one_million_elements_set
```

    23.5 ns ± 0.223 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)


Само собой, за это приходится платить временем на построение множества:


```python
%timeit set(one_million_elements)
```

    46.7 ms ± 358 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


И памятью. Множество держит хеш-таблицу с запасом, а не просто элементы подряд. Строить его ради одной проверки бессмысленно, ради миллиона — обязательно.

### Совет 4. Сортировка


```python
import random

data = [random.random() for _ in range(1_000_000)]
%timeit sorted(data)
```

    120.7 ms ± 3.1 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit (lambda a: a.sort())(data[:])
```

    108.5 ms ± 2.8 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)


Данные здесь взяты случайные, и это принципиально. На уже отсортированном списке Timsort вырождается в один линейный проход, оба замера дают около 4 мс, и разницы между ними нет вовсе — мерился бы не порядок, а копирование. На случайных данных `sort` выигрывает около 10 %: ровно столько стоит лишняя копия. Если исходный порядок не нужен, пользуйся ей.

### Совет 5. Условия if

Условие в `if` можно записать по-разному:


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

И работают эти варианты разное время:


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


Попробуй угадать, какая из проверок на пустоту быстрее:
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


Самый быстрый вариант здесь заодно и самый идиоматичный — `if not elements`. Так бывает нечасто, но приятно.

### Совет 6. Спрашивать разрешения или обрабатывать последствия

Предположим, код должен работать и с объектами, у которых нужный атрибут есть, и с теми, у которых его нет.


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


Разница станет ещё больше, если атрибутов надо проверить несколько.

Где подвох?

Предположим, что у объектов в основном нет нужного атрибута.


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


Мораль: исключение дёшево бросить один раз и дорого — миллион. Выбирай между `hasattr` и `try/except` по тому, какая ситуация встречается чаще.

### Совет 7. Особенности определения словаря и списка

Словарь и список можно объявить двумя способами:


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


Откуда разница? Обращение к имени стоит времени — интерпретатору нужно выяснить, на что указывает `list`. Литерал же компилируется в одну инструкцию. Разберём байт-код модулем `dis` и убедимся, что он и правда разный:


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

Если функцию можно не вызывать — лучше не вызывать. На каждый вызов создаётся кадр стека, а это заметное время.


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


### Совет 9. Избегай активной работы с глобальными переменными


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


### Совет 10. Для математики используй соответствующие библиотеки

Не пиши численные расчёты циклами на Python. Для этого есть библиотеки на C и Фортране, и разница получается в десятки раз:


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


### Опасная зона

Дальше идут уловки, которые ухудшают читаемость кода ради нескольких процентов. Применяй их, только если профилировщик показал, что эти проценты действительно нужны.

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


Объявление в одну строку и правда быстрее — распаковка кортежа обходится дешевле десяти отдельных присваиваний. Но читать такой код невозможно, и выигрыш в сотню микросекунд того не стоит.

### Совет 12. Поиск функций и атрибутов

Поиск атрибута в Python — операция не бесплатная. За ней стоит `__getattribute__`, а если тот ничего не нашёл, то и `__getattr__`. Напрашивается очевидное: найти атрибут один раз и сохранить в локальную переменную, чтобы не искать заново на каждой итерации.


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


И вот результат: совет, который годами кочует по подборкам об оптимизации, здесь проигрывает. Начиная с версии 3.11 CPython специализирует вызов метода прямо в байт-коде, и обычный `result.append(item)` оказывается быстрее заранее сохранённой ссылки.

Проверяй такие рекомендации замером на своей версии интерпретатора.

### Прочее

За пределами CPython тоже кое-что происходит, и три проекта заслуживают внимания:

1. [nimpy](https://github.com/yglukhov/nimpy) — вызов функций на языке Nim из Python.
2. [Pythran](https://pythran.readthedocs.io/en/latest/) — ещё один подход к компиляции Python-кода.
3. [Pyston](https://github.com/pyston/pyston) — альтернативный интерпретатор с JIT-компилятором.

## Оптимизируем память

Скорость — не единственный дефицитный ресурс. Расчёт, который не помещается в оперативную память, не спасёт никакая векторизация. Он просто не запустится.

## Замеряем память

Замерять память в Python неожиданно трудно.


```python
import sys

print(sys.getsizeof([i for i in range(1000000)]))
print(sys.getsizeof([i for i in range(100000)]))
```

    8448728
    800984


Кажется, всё работает как надо. Но:


```python
class SomeClass:
    def __init__(self, i):
        self.i = i
        self.j = i * 2
        
sys.getsizeof([SomeClass(i) for i in range(1000000)])
```




    8448728



Список объектов `SomeClass` занимает столько же, сколько список целых чисел. Ничего загадочного — `sys.getsizeof` меряет размер самого списка, то есть массива указателей, а не то, на что эти указатели ведут. Надёжно он работает только для простых типов и встроенных структур.

Что делать? Брать профилировщик памяти.


```python
%load_ext memory_profiler
%memit
```

    peak memory: 625.96 MiB, increment: 0.00 MiB


Этот подход тоже не идеален. Он смотрит на потребление памяти процессом в отдельные моменты времени, поэтому учитывает не всё, а результаты заметно плавают от запуска к запуску.


```python
%memit [n for n in range(10000000)]
```

    peak memory: 1007.02 MiB, increment: 377.12 MiB



```python
%memit [n for n in range(1000000)]
```

    peak memory: 632.71 MiB, increment: 0.07 MiB


## Можно ли получить memory-leakage в Python

Зависит от того, что считать утечкой. В смысле C++ — почти нет. За освобождением следит сборщик мусора, и потерять память по-настоящему можно разве что напортив со счётчиком ссылок в расширении на C. Подробнее — в [разборе устройства сборщика](https://rushter.com/blog/python-garbage-collector/).

А вот долгоживущие бесполезные объекты получить легко, и на практике утечкой обычно называют как раз их. Три классических способа — изменяемый аргумент по умолчанию, забытая переменная, которая живёт всё время работы длинной функции, и кеш в атрибуте класса, из которого ничего никогда не удаляется:


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
        self.cache[arg] = result    # растёт вечно: удалять отсюда некому
        return result
```

## Array

Отдельная история — старые версии Python (2.7 и всё до 3.4). Там сборщик не умел разбирать циклические ссылки между объектами с `__del__`, и такие циклы жили до конца работы программы.

Теперь о том, как памяти тратить меньше. Модуль `array` хранит числа примитивных типов подряд, без отдельного объекта на каждый элемент:


```python
import array

%memit array.array('q', range(10000000))
```

    peak memory: 702.93 MiB, increment: 70.22 MiB


[Полный список кодов типов](https://docs.python.org/3/library/array.html) — в документации.

## np.array

`np.array` устроен так же — фиксированный тип, элементы подряд, и памяти занимает существенно меньше стандартного списка. Вдобавок, в отличие от `array`, он умеет считать.


```python
np.arange(10000000).nbytes / 2**20
```

    76.29

Здесь `%memit` не годится, и на этом стоит остановиться. Он меряет прирост
потребления процессом, а интерпретатор с аллокатором держат уже освобождённые
страницы про запас и охотно кладут новый массив в них. В таком случае `%memit`
покажет `increment: 0.00 MiB` для восьмидесяти мегабайт данных — и это не
экономия, а несостоявшееся измерение. У NumPy размер известен точно и без
всяких замеров: `nbytes` возвращает ровно `len * itemsize`.


## tuple vs list

Кортеж чуть компактнее списка — ему не нужен запас под рост. Разница невелика, зато хорошо видно, во что обходится списковое включение: созданный им список несёт с собой место под будущие `append`:


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

Атрибут `__slots__` отменяет у экземпляров словарь `__dict__` и раскладывает поля по фиксированным ячейкам. Память это экономит:


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


Обычно `__slots__` заодно ускоряет и обращение к атрибуту. Обычно, но не всегда:


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


Здесь разница ушла в шум — современный CPython кеширует поиск атрибута и в обычном `__dict__`. Ещё один повод не верить советам на слово.

А вот с наследованием со `__slots__` неудобно, ведь указывать его приходится в каждом классе иерархии, иначе `__dict__` вернётся и вся экономия пропадёт.

## bitarray

Пакет [bitarray](https://github.com/ilanschnell/bitarray) хранит булевы значения по одному биту на элемент, а не по указателю на объект. На десяти миллионах флагов разница уже заметна:


```python
import bitarray.util as bu

bu.zeros(10000000).nbytes / 2**20
```

    1.19



```python
%memit [False for i in range(10000000)]
```

    peak memory: 701.93 MiB, increment: 67.81 MiB


Плата — время. Чтобы достать один флаг, его надо ещё вынуть из байта.

## range — вычисление вместо хранения

Иногда последовательность вообще не нужно хранить. `range` не держит элементы в памяти — он вычисляет нужный по индексу, а `len` считает по формуле:


```python
a = range(1, 100000, 3)
print(a[10])
print(len(a))
```

    31
    33333


Тот же ход — считать вместо того, чтобы хранить, — работает и для более сложных последовательностей. Промежуточный вариант — считать, но кешировать то, что запрашивают чаще всего.

## Другой полезный инструментарий

Если дело дошло до серьёзных разбирательств с памятью, пригодятся ещё два инструмента:

1. [objgraph](https://github.com/mgedmin/objgraph) — рисует граф ссылок и помогает понять, кто держит объект живым.
2. [guppy3](https://github.com/zhuyifei1999/guppy3) — подробная статистика по куче.


## Резюме

* Оптимизировать имеет смысл только то, что измерено. Интуиция о том, где программа проводит время, врёт систематически — сначала профилировщик, потом правки.
* Оптимизация всегда что-то стоит: время разработки, читаемость кода, иногда корректность. Прежде чем ускорять, стоит убедиться, что медленная работа действительно составляет проблему.
* Самый дешёвый выигрыш обычно даёт не микрооптимизация, а смена структуры данных или алгоритма: замена списка на множество в проверке вхождения меняет \\(O(n)\\) на \\(O(1)\\).
* Для памяти работают свои средства: `__slots__`, `array`, генераторы вместо списков — они не ускоряют код, но позволяют обработать данные, которые иначе не поместились бы.
* И главное правило: **сначала правильно, потом быстро**. Ускоренный неверный расчёт остаётся неверным.
