# Сложность операций с коллекциями

Понимание временной сложности операций — ключ к написанию эффективных программ. В нотации **O-большое** мы описываем, как время выполнения алгоритма растет с ростом размера входных данных.

## Почему сложность важна?

```python
from timeit import timeit
import random

# Сравним поиск в списке и множестве
large_list = list(range(1000000))
large_set = set(large_list)

# Ищем случайный элемент
target = random.randint(0, 1000000)

# Время поиска в списке (O(n))
list_time = timeit(lambda: target in large_list, number=1000)
# Время поиска в множестве (O(1))
set_time = timeit(lambda: target in large_set, number=1000)

print(f"Поиск в списке: {list_time:.4f} сек")
print(f"Поиск в множестве: {set_time:.4f} сек")
```

Результат будет поразительным — поиск в множестве в тысячи раз быстрее!

## Сложность операций со списками

### O(1) — Константное время
```python
my_list = [1, 2, 3, 4, 5]

# Эти операции выполняются за постоянное время
my_list.append(6)      # Добавление в конец
last = my_list.pop()   # Удаление с конца
element = my_list[2]   # Доступ по индексу
length = len(my_list)  # Получение длины
```

**Почему O(1)**: Python хранит указатель на последний элемент, поэтому добавление/удаление с конца не требует перемещения других элементов.

### O(n) — Линейное время
```python
my_list = [1, 2, 3, 4, 5]

# Эти операции требуют обхода или сдвига элементов
my_list.insert(0, 0)   # Вставка в начало → сдвиг всех элементов
my_list.remove(3)      # Поиск и удаление элемента
element in my_list     # Поиск элемента
my_list.index(4)       # Поиск индекса элемента
```

**Почему O(n)**: При вставке в начало все последующие элементы должен быть сдвинуты на одну позицию.

### Практический пример: неэффективный vs эффективный код

```python
# НЕЭФФЕКТИВНО: O(n²)
def remove_duplicates_slow(data):
    result = []
    for item in data:
        if item not in result:  # O(n) для каждого элемента!
            result.append(item)
    return result

# ЭФФЕКТИВНО: O(n)
def remove_duplicates_fast(data):
    seen = set()
    result = []
    for item in data:
        if item not in seen:    # O(1) проверка!
            seen.add(item)
            result.append(item)
    return result

# Тестируем
data = [1, 2, 2, 3, 4, 4, 5] * 1000

slow_time = timeit(lambda: remove_duplicates_slow(data), number=1)
fast_time = timeit(lambda: remove_duplicates_fast(data), number=1)

print(f"Медленная версия: {slow_time:.4f} сек")
print(f"Быстрая версия: {fast_time:.4f} сек")
```

## Сложность операций с множествами

Множества реализованы как хэш-таблицы, поэтому большинство операций имеют сложность O(1).

```python
my_set = {1, 2, 3, 4, 5}

# O(1) операции
my_set.add(6)           # Добавление
my_set.remove(3)        # Удаление
4 in my_set             # Проверка вхождения
len(my_set)             # Длина

# O(min(len(s1), len(s2))) операции
s1 = {1, 2, 3}
s2 = {3, 4, 5}
union = s1 | s2         # Объединение
intersection = s1 & s2  # Пересечение
difference = s1 - s2    # Разность
```

**Интересный факт**: Худший случай для операций с множествами — O(n), когда происходят коллизии хэшей, но на практике это редкая ситуация.

## Сложность операций со словарями

Словари также используют хэш-таблицы, поэтому основные операции имеют сложность O(1).

```python
my_dict = {'a': 1, 'b': 2, 'c': 3}

# O(1) операции
my_dict['d'] = 4        # Вставка/обновление
value = my_dict['a']    # Доступ
del my_dict['b']        # Удаление
'a' in my_dict          # Проверка ключа

# O(n) операции
list(my_dict.keys())    # Создание списка ключей
list(my_dict.values())  # Создание списка значений
'value' in my_dict.values()  # Поиск по значениям
```

## Как вычислять сложность на практике

### Метод 1: Анализ вложенных циклов

```python
# O(n²) — квадратичная сложность
def find_pairs_quadratic(items):
    pairs = []
    for i in range(len(items)):          # O(n)
        for j in range(i + 1, len(items)):  # O(n)
            pairs.append((items[i], items[j]))  # O(1)
    return pairs

# O(n) — линейная сложность  
def find_pairs_linear(items):
    pairs = []
    seen = set()
    for i, item in enumerate(items):     # O(n)
        if item not in seen:             # O(1)
            seen.add(item)
            # некоторая логика
    return pairs
```

### Метод 2: Учет дорогостоящих операций

```python
def process_data(data):
    result = []
    
    # Сортировка: O(n log n)
    sorted_data = sorted(data)           # O(n log n)
    
    # Поиск каждого элемента: O(n) × O(log n) = O(n log n)
    for target in sorted_data:           # O(n)
        # Бинарный поиск: O(log n)
        # (предположим, что у нас есть реализация)
        index = binary_search(sorted_data, target)
        result.append(index)
    
    return result

# Общая сложность: O(n log n) + O(n log n) = O(n log n)
```

### Метод 3: Практическое измерение

```python
import time
import matplotlib.pyplot as plt

def measure_complexity():
    sizes = [1000, 2000, 4000, 8000, 16000]
    times = []
    
    for size in sizes:
        data = list(range(size))
        
        start = time.time()
        # Тестируемая операция
        _ = data.insert(0, -1)  # O(n) операция
        end = time.time()
        
        times.append(end - start)
    
    # Строим график для визуальной оценки
    plt.plot(sizes, times)
    plt.xlabel('Размер данных')
    plt.ylabel('Время выполнения')
    plt.show()

# measure_complexity()  # График покажет линейный рост для O(n)
```

## Практические правила для выбора коллекций

### Когда использовать списки
- Нужен последовательный доступ к элементам
- Частые операции с концом списка (append/pop)
- Элементы могут дублироваться
- **Избегайте**: частых insert(0)/pop(0) на больших данных

### Когда использовать множества
- Проверка принадлежности (x in collection)
- Удаление дубликатов
- Математические операции (объединение, пересечение)
- **Избегайте**: сохранения порядка или хранения нехэшируемых объектов

### Когда использовать словари
- Ассоциативное хранение данных (ключ→значение)
- Быстрый поиск по ключу
- Группировка данных
- **Избегайте**: частого поиска по значениям (используй обратный словарь)

### Оптимизация на практике

```python
# ПЛОХО: O(n²)
def find_common_elements_slow(list1, list2):
    result = []
    for item in list1:           # O(n)
        if item in list2:        # O(m) - линейный поиск!
            result.append(item)
    return result

# ХОРОШО: O(n + m)
def find_common_elements_fast(list1, list2):
    set2 = set(list2)            # O(m) - создание множества
    result = []
    for item in list1:           # O(n)
        if item in set2:         # O(1) - поиск в хэш-таблице!
            result.append(item)
    return result
```

## Некоторые правила сложности

1. **O(1) < O(log n) < O(n) < O(n log n) < O(n²)** — запомни эту иерархию
2. **Избегайте вложенных циклов** — они часто приводят к O(n²)
3. **Используй правильные структуры данных** — множества и словари для поиска, списки для последовательностей

Помни: преждевременная оптимизация может быть вредна, но понимание сложности операций поможет тебе избежать грубых ошибок в дизайне алгоритмов.